"""World + multiplex network builder (spec §1-§2, Algorithm 1 at hackathon scale).

Built ONCE per scenario (plan: "the scenario's network saved to one file shared by every run")
with central prior values, cached as <scenario>/network.npz. Runs vary only dynamics, regional
draws and their seed, so every response faces the same network (common random numbers).

Spec-faithful parts: H3 cells, d_aa = 0.51*sqrt(A_a), mid-rank r_a(b), per-capita normalised
distance/rank kernels mixed by omega, symmetrised 1a kernel, LogNormal fitness truncated and
renormalised, lambda_{j->i} = lambda g_j f_i K(b_i, b_j), source-major alias generation,
1a at half intensity + symmetrize_csr, coupled online layers via shared affinity z_ij with
Jaccard-calibrated copy probability, independent online edges at (1 - rho) lambda.

Choices the spec leaves open (marked ASSUMPTION):
  * region hubs: people are placed around real hub coordinates per region (REGION_HUBS / config).
  * stratum d: a single stratum, so H == 1 (spec: lambda equals mean degree exactly when H == 1).
  * layer 1b groups: generated from a home cell with members drawn through the 1a kernel.
  * layers 5-6: U V^T is a rank-r nonnegative factorisation of a weak-decay (alpha=0.5) kernel.
"""
import hashlib, json, math, os
import numpy as np
import h3
from scipy.special import ndtri
from .kernels import build_alias_table, generate_source_major_csr, symmetrize_csr, seed_engine

H3_RES = 5          # ~250 km^2 cells; keeps M in the hundreds at hackathon scale (spec: dense M x M)
D0_KM = 1.0         # kernel regulariser d0

# ASSUMPTION: hub coordinates (lat, lon, spread_km, weight) for the regions used in data/.
REGION_HUBS = {
    "SF_Bay_Area": [(37.77, -122.42, 15, 3), (37.44, -122.16, 12, 2), (37.34, -121.89, 15, 2)],
    "New_York": [(40.73, -73.99, 12, 1)],
    "Boston": [(42.36, -71.06, 12, 2), (42.37, -71.11, 6, 1)],
    "Austin_Seattle_LA": [(30.27, -97.74, 15, 1), (47.61, -122.33, 15, 1), (34.05, -118.24, 25, 1)],
    "London_UK": [(51.51, -0.13, 15, 1)],
    "Israel": [(32.08, 34.78, 12, 2), (31.77, 35.21, 10, 1)],
    "India": [(12.97, 77.59, 20, 2), (19.08, 72.88, 20, 1), (28.61, 77.21, 20, 1)],
    "Rest_of_US": [(41.88, -87.63, 40, 1), (29.76, -95.37, 40, 1), (33.75, -84.39, 40, 1), (39.74, -104.99, 40, 1)],
    "Switzerland": [(47.37, 8.54, 15, 3), (46.20, 6.14, 12, 2), (46.95, 7.45, 12, 1), (47.56, 7.59, 10, 1)],
    "Europe_UK": [(51.51, -0.13, 20, 3), (50.11, 8.68, 15, 1), (48.86, 2.35, 15, 1), (45.46, 9.19, 15, 1)],
    "Middle_East": [(25.20, 55.27, 20, 2), (24.71, 46.68, 20, 1), (25.29, 51.53, 15, 1)],
    "Asia_Pacific": [(1.35, 103.82, 15, 2), (22.32, 114.17, 12, 2), (35.68, 139.69, 20, 1)],
    "Americas": [(40.73, -73.99, 15, 2), (25.76, -80.19, 15, 1), (-23.55, -46.63, 20, 1)],
    "Los_Angeles_SoCal": [(34.05, -118.24, 30, 3), (33.68, -117.83, 15, 1), (32.72, -117.16, 15, 1)],
    "Rest_of_California": [(38.58, -121.49, 30, 1), (36.74, -119.79, 30, 1), (35.37, -119.02, 25, 1)],
    "US_Venture_Hubs": [(40.73, -73.99, 12, 2), (42.36, -71.06, 12, 1), (30.27, -97.74, 15, 1), (47.61, -122.33, 15, 1)],
}

# Central prior values for the network (spec §8.1), used to build the shared network.
NET = dict(N=20000, k1a=30.0, m_groups=5.0, group_size=8.0,
           alpha_1a=1.5, alpha_on=0.65, eta=1.0, omega=0.35, sigma_1a=0.5, sigma_on=1.2,
           k_dir=(40.0, 50.0, 40.0), J=(0.30, 0.25, 0.30), delta=1.0,
           alpha_b=0.5, lam_b=20.0, rank=32, seed=7)


def _haversine(lat1, lon1, lat2, lon2):
    p = np.pi / 180
    a = np.sin((lat2 - lat1) * p / 2) ** 2 + np.cos(lat1 * p) * np.cos(lat2 * p) * np.sin((lon2 - lon1) * p / 2) ** 2
    return 12742.0 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def _fitness(rng, N, sigma, kmax_over_k):
    f = rng.lognormal(-sigma ** 2 / 2, sigma, N)
    f = np.minimum(f, kmax_over_k)          # truncated at f_max = k_max / <k>
    return (f / f.mean()).astype(np.float64)


def _kernel(d, n, rank_hat, alpha, eta, omega):
    """K(a,b) = omega K_dist + (1-omega) K_rank, each normalised so sum_b n_b K(a,b) = 1 (spec §2.1)."""
    kd = (d + D0_KM) ** (-alpha)
    kd /= (kd * n[None, :]).sum(1, keepdims=True)
    kr = (1.0 + rank_hat) ** (-eta)
    kr /= (kr * n[None, :]).sum(1, keepdims=True)
    return omega * kd + (1 - omega) * kr


def _alias_rows(W):
    """Per-cell alias tables over target cells for weight matrix W[a, b]."""
    M = W.shape[0]
    P = np.zeros((M, M), np.float32); A = np.zeros((M, M), np.int32)
    for a in range(M):
        P[a], A[a] = build_alias_table(W[a].astype(np.float64))
    return P, A


def _node_alias(cell_offsets, weights):
    prob = np.zeros(len(weights), np.float32); idx = np.zeros(len(weights), np.int32)
    for c in range(len(cell_offsets) - 1):
        s, e = cell_offsets[c], cell_offsets[c + 1]
        if e > s:
            prob[s:e], idx[s:e] = build_alias_table(weights[s:e].astype(np.float64))
    return prob, idx


def _gen_layer(N, cell_id, cell_offsets, src_fit, tgt_fit, K_src_view, lam, deg_cap):
    """Source-major generation. K_src_view[a, b] = kernel weight from source cell a to target cell b."""
    M = len(cell_offsets) - 1
    F = np.bincount(cell_id, weights=tgt_fit, minlength=M)          # target weight sum per cell
    W = K_src_view * F[None, :]
    rate = lam * W.sum(1)
    P, A = _alias_rows(W)
    cells = np.tile(np.arange(M, dtype=np.int32), (M, 1))
    nprob, nidx = _node_alias(cell_offsets, tgt_fit)
    return generate_source_major_csr(N, cell_id, cell_offsets, src_fit.astype(np.float64), nprob, nidx,
                                     cells, P, A, rate.astype(np.float64), deg_cap)


def _hash_unit(i, j, seed):
    with np.errstate(over="ignore"):   # wraparound is the point of the hash
        return _hash_unit_raw(i, j, seed)


def _hash_unit_raw(i, j, seed):
    x = (np.uint64(min(i, j)) * np.uint64(0x9E3779B97F4A7C15)) ^ (np.uint64(max(i, j)) + np.uint64(seed) * np.uint64(0xBF58476D1CE4E5B9))
    x ^= x >> np.uint64(31); x *= np.uint64(0x94D049BB133111EB); x ^= x >> np.uint64(29)
    return (float(x % np.uint64(2 ** 53)) + 0.5) / 2 ** 53


def _nmf(B, r, iters=300, seed=0):
    rng = np.random.default_rng(seed)
    U = rng.random((B.shape[0], r)) + 1e-3; V = rng.random((B.shape[1], r)) + 1e-3
    for _ in range(iters):
        U *= (B @ V) / (U @ (V.T @ V) + 1e-12)
        V *= (B.T @ U) / (V @ (U.T @ U) + 1e-12)
    return U.astype(np.float64), V.astype(np.float64)


def build(scn_dir, cfg, scen):
    regions = cfg.get("regions") or list(scen["regions"])
    share = np.array(cfg.get("region_share"), float); share /= share.sum()
    tz = np.array(cfg.get("tz_offset"), float)
    hubs_cfg = cfg.get("region_hubs", {})
    P = dict(NET, **cfg.get("network", {}))
    key = hashlib.sha256(json.dumps([regions, share.tolist(), tz.tolist(), hubs_cfg, P], sort_keys=True).encode()).hexdigest()[:16]
    path = os.path.join(scn_dir, "network.npz")
    if os.path.exists(path):
        z = np.load(path, allow_pickle=False)
        if str(z["key"]) == key:
            return {k: z[k] for k in z.files}
    rng = np.random.default_rng(P["seed"]); seed_engine(P["seed"])
    N = int(P["N"])

    # ---- population on the map -> H3 cells (sorted by cell, spec Algorithm 1 step 1) ----
    reg = rng.choice(len(regions), N, p=share)
    lat = np.empty(N); lon = np.empty(N)
    for r, name in enumerate(regions):
        hubs = hubs_cfg.get(name) or REGION_HUBS[name]
        idx = np.where(reg == r)[0]
        w = np.array([h[3] for h in hubs], float)
        pick = rng.choice(len(hubs), len(idx), p=w / w.sum())
        for k, (la, lo, sd, _) in enumerate(hubs):
            ii = idx[pick == k]
            lat[ii] = la + rng.normal(0, sd / 111.0, len(ii))
            lon[ii] = lo + rng.normal(0, sd / (111.0 * max(0.2, math.cos(math.radians(la)))), len(ii))
    cells_str = [h3.latlng_to_cell(float(a), float(b), H3_RES) for a, b in zip(lat, lon)]
    uniq = sorted(set(cells_str)); cmap = {c: i for i, c in enumerate(uniq)}
    cell_raw = np.array([cmap[c] for c in cells_str], np.int32)
    order = np.lexsort((rng.random(N), cell_raw))
    reg, cell_id, lat, lon = reg[order], cell_raw[order], lat[order], lon[order]
    M = len(uniq)
    n = np.bincount(cell_id, minlength=M).astype(float)
    cell_offsets = np.zeros(M + 1, np.int64); cell_offsets[1:] = np.cumsum(n).astype(np.int64)
    # each cell belongs to the region most of its people come from
    region_of_cell = np.array([np.bincount(reg[cell_offsets[c]:cell_offsets[c + 1]], minlength=len(regions)).argmax()
                               for c in range(M)], np.int32)
    tz_cell = tz[region_of_cell]

    # ---- distances and mid-rank (spec §2.1) ----
    cl = np.array([h3.cell_to_latlng(c) for c in uniq])
    d = _haversine(cl[:, 0][:, None], cl[:, 1][:, None], cl[:, 0][None, :], cl[:, 1][None, :])
    area = np.array([h3.cell_area(c, unit="km^2") for c in uniq])
    np.fill_diagonal(d, 0.51 * np.sqrt(area))
    d_cmp = d.copy(); np.fill_diagonal(d_cmp, 0.0)               # d_aa = 0 inside the comparison
    rank_hat = np.zeros((M, M))
    for a in range(M):
        o = np.argsort(d_cmp[a], kind="stable"); ds = d_cmp[a, o]; ns = n[o]
        cum = np.cumsum(ns) - ns
        # mid-rank: people strictly closer + half of those at equal distance
        uniq_d, start = np.unique(ds, return_index=True)
        for t, s0 in enumerate(start):
            e0 = start[t + 1] if t + 1 < len(start) else len(ds)
            rank_hat[a, o[s0:e0]] = cum[s0] + 0.5 * ns[s0:e0].sum()

    # ---- fitness (spec §2.2): 1a g = f; online f, g independent heavy-tailed ----
    f1a = _fitness(rng, N, P["sigma_1a"], 300.0 / P["k1a"])
    f_on = [_fitness(rng, N, P["sigma_on"], 5000.0 / k) for k in P["k_dir"]]
    g_on = [_fitness(rng, N, P["sigma_on"], 5000.0 / k) for k in P["k_dir"]]

    # ---- layer 1a: symmetric kernel, half intensity, symmetrise ----
    K1a = _kernel(d, n, rank_hat, P["alpha_1a"], P["eta"], P["omega"])
    K1a_sym = 0.5 * (K1a + K1a.T)
    ip, ix, ct = _gen_layer(N, cell_id, cell_offsets, f1a, f1a, K1a_sym, P["k1a"] / 2.0, 300)
    ip1, ix1, ct1 = symmetrize_csr(N, ip, ix, ct)

    # ---- layers 2-4: coupled copies of 1a + independent edges (spec §2.4) ----
    E1a = int(ct1.sum()) // 2
    src_l, dst_l, lay_l = [], [], []
    rows = np.repeat(np.arange(N), ct1); cols = np.concatenate([ix1[ip1[i]:ip1[i] + ct1[i]] for i in range(N)]) if N else np.array([])
    und = rows < cols
    pi, pj = rows[und], cols[und].astype(np.int64)
    z = ndtri(np.array([_hash_unit(int(a), int(b), P["seed"]) for a, b in zip(pi, pj)]))
    for l, (kl, J) in enumerate(zip(P["k_dir"], P["J"])):
        El = N * kl / 2.0
        J = min(J, E1a / El)                                         # feasibility cap
        pbar = J * (E1a + El) / (E1a * (1 + J))
        beta0 = math.log(pbar / (1 - pbar)) * math.sqrt(1 + math.pi * P["delta"] ** 2 / 8)
        pcopy = 1 / (1 + np.exp(-(beta0 + P["delta"] * z)))
        for a, b in ((pi, pj), (pj, pi)):
            keep = rng.random(len(pcopy)) < pcopy
            src_l.append(a[keep]); dst_l.append(b[keep]); lay_l.append(np.full(keep.sum(), l))
        rho = (P["k1a"] * pbar) / kl
        lam_ind = max(0.0, (1 - rho) * kl)
        Kl = _kernel(d, n, rank_hat, P["alpha_on"], P["eta"], P["omega"])
        # source-major uses the transposed kernel (follower's cell decides), source fitness = popularity g
        ipd, ixd, ctd = _gen_layer(N, cell_id, cell_offsets, g_on[l], f_on[l], Kl.T, lam_ind, 5000)
        s = np.repeat(np.arange(N), ctd); t = np.concatenate([ixd[ipd[i]:ipd[i] + ctd[i]] for i in range(N)])
        src_l.append(s); dst_l.append(t.astype(np.int64)); lay_l.append(np.full(len(s), l))
    S = np.concatenate(src_l); T = np.concatenate(dst_l); L = np.concatenate(lay_l)
    o = np.lexsort((L, T, S)); S, T, L = S[o], T[o], L[o]
    keep = np.ones(len(S), bool); keep[1:] = (S[1:] != S[:-1]) | (T[1:] != T[:-1]) | (L[1:] != L[:-1])
    S, T, L = S[keep], T[keep], L[keep]
    ctd = np.bincount(S, minlength=N).astype(np.int32)
    ipd = np.zeros(N + 1, np.int64); ipd[1:] = np.cumsum(ctd)

    # ---- layer 1b groups (ASSUMPTION: home cell + members via the 1a kernel) ----
    G = int(N * P["m_groups"] / P["group_size"])
    home = rng.choice(M, G, p=n / n.sum())
    F1 = np.bincount(cell_id, weights=f1a, minlength=M)
    members = []
    for g in range(G):
        size = 2 + rng.poisson(P["group_size"] - 2)
        w = K1a_sym[home[g]] * F1; tc = rng.choice(M, size, p=w / w.sum())
        mem = set()
        for c in tc:
            s0, e0 = cell_offsets[c], cell_offsets[c + 1]
            ff = f1a[s0:e0]; mem.add(int(s0 + rng.choice(e0 - s0, p=ff / ff.sum())))
        members.append(sorted(mem))
    g2u_indptr = np.zeros(G + 1, np.int64); g2u_indptr[1:] = np.cumsum([len(m) for m in members])
    g2u_indices = np.array([v for m in members for v in m], np.uint32)
    gu = np.repeat(np.arange(G), [len(m) for m in members]); o = np.argsort(g2u_indices, kind="stable")
    u2g_indices = gu[o].astype(np.uint32)
    u2g_indptr = np.zeros(N + 1, np.int64); u2g_indptr[1:] = np.cumsum(np.bincount(g2u_indices, minlength=N))

    # ---- layers 5-6 broadcast: rank-r nonnegative U V^T of a weak-decay kernel (ASSUMPTION) ----
    Kb = _kernel(d, n, rank_hat, P["alpha_b"], P["eta"], P["omega"])
    B = P["lam_b"] * (n[:, None] * Kb.T)          # B[c, a]: arrivals in c per unit source mass in a
    r = min(int(P["rank"]), M)
    U_b, V_b = _nmf(B, r)
    f_b = _fitness(rng, N, P["sigma_on"], 5000.0 / 20)
    phi_b = _fitness(rng, N, P["sigma_on"], 5000.0 / 20)
    cons_prob, cons_idx = _node_alias(cell_offsets, f_b)

    out = dict(key=np.array(key), N=np.array(N), M=np.array(M), regions=np.array(regions), region=reg.astype(np.int32),
               cell_id=cell_id, cell_offsets=cell_offsets, region_of_cell=region_of_cell, tz_cell=tz_cell,
               lat=lat, lon=lon, cell_lat=cl[:, 0], cell_lon=cl[:, 1],
               indptr_1a=ip1, indices_1a=ix1, counts_1a=ct1,
               indptr_d=ipd, indices_d=T.astype(np.uint32), counts_d=ctd, layer_d=L.astype(np.uint8),
               u2g_indptr=u2g_indptr, u2g_indices=u2g_indices, g2u_indptr=g2u_indptr, g2u_indices=g2u_indices,
               U_b=U_b, V_b=V_b, phi_b=phi_b.astype(np.float32), cons_alias_prob=cons_prob, cons_alias_idx=cons_idx,
               f1a=f1a, g_pop=np.mean(g_on, 0), degree=(ct1 + np.bincount(S, minlength=N)).astype(np.float64))
    np.savez_compressed(path, **out)
    return out
