"""Compiled kernels from the Population-Scale Multiplex Contagion spec, §7 (reference implementation).

Transcribed from the spec. Additions are marked "ADDED" and are bookkeeping only: per-message x region
counters the pipeline's evidence pack needs. They never change a random draw or a state transition.
"""
import numpy as np
from numba import njit, prange

# State codes
ST_U, ST_E, ST_B, ST_S, ST_R = 0, 1, 2, 3, 4
# posted_mask bits: one per channel, used by the repeat discount
BIT_1A, BIT_GROUP, BIT_BCAST = 0, 4, 5   # directed layers use bits 1, 2, 3


@njit(cache=True)
def seed_engine(seed):
    """Seed Numba's own generator. np.random.seed called from Python does NOT
    reach compiled code, so call this before every run you want reproducible."""
    np.random.seed(seed)


# ---------------------------------------------------------------------------------
# 1. O(1) Walker's alias table
# ---------------------------------------------------------------------------------
@njit(cache=True)
def build_alias_table(weights):
    K = len(weights)
    prob = np.zeros(K, dtype=np.float32)
    alias = np.zeros(K, dtype=np.int32)
    total = np.sum(weights)
    if total <= 0.0:
        prob[:] = 1.0
        for i in range(K):
            alias[i] = i
        return prob, alias
    scaled = (weights / total) * K
    small = np.empty(K, dtype=np.int32)
    large = np.empty(K, dtype=np.int32)
    s_head, l_head = 0, 0
    for i in range(K):
        if scaled[i] < 1.0:
            small[s_head] = i
            s_head += 1
        else:
            large[l_head] = i
            l_head += 1
    while s_head > 0 and l_head > 0:
        s_head -= 1
        l_head -= 1
        s_idx = small[s_head]
        l_idx = large[l_head]
        prob[s_idx] = scaled[s_idx]
        alias[s_idx] = l_idx
        scaled[l_idx] = (scaled[l_idx] + scaled[s_idx]) - 1.0
        if scaled[l_idx] < 1.0:
            small[s_head] = l_idx
            s_head += 1
        else:
            large[l_head] = l_idx
            l_head += 1
    while l_head > 0:
        l_head -= 1
        prob[large[l_head]] = 1.0
    while s_head > 0:
        s_head -= 1
        prob[small[s_head]] = 1.0
    return prob, alias


@njit(inline='always')
def sample_alias(prob, alias):
    K = len(prob)
    idx = np.random.randint(0, K)
    if np.random.random() < prob[idx]:
        return idx
    return alias[idx]


# ---------------------------------------------------------------------------------
# 2. Source-major CSR generator (dissemination orientation for directed layers)
# ---------------------------------------------------------------------------------
@njit(parallel=True, cache=True)
def generate_source_major_csr(N, cell_id, cell_offsets, fitness_src,
                              node_alias_prob, node_alias_idx,
                              interaction_cells, interaction_prob, interaction_alias,
                              cell_rate_multiplier, deg_cap):
    raw_degrees = np.zeros(N, dtype=np.int64)
    for i in prange(N):
        lam = fitness_src[i] * cell_rate_multiplier[cell_id[i]]
        raw_degrees[i] = min(np.random.poisson(lam), deg_cap)
    indptr = np.zeros(N + 1, dtype=np.int64)
    indptr[1:] = np.cumsum(raw_degrees)
    indices = np.empty(indptr[-1], dtype=np.uint32)
    counts = np.zeros(N, dtype=np.int32)
    for i in prange(N):
        k = raw_degrees[i]
        if k == 0:
            continue
        c = cell_id[i]
        row_start = indptr[i]
        buf = np.empty(k, dtype=np.uint32)
        valid = 0
        for _ in range(k):
            list_idx = sample_alias(interaction_prob[c], interaction_alias[c])
            target_cell = interaction_cells[c, list_idx]
            c_start = cell_offsets[target_cell]
            c_end = cell_offsets[target_cell + 1]
            if c_end <= c_start:
                continue
            local_j = sample_alias(node_alias_prob[c_start:c_end], node_alias_idx[c_start:c_end])
            j = c_start + local_j
            if j != i:
                buf[valid] = np.uint32(j)
                valid += 1
        if valid > 0:
            srt = np.sort(buf[:valid])
            indices[row_start] = srt[0]
            w = 1
            for t in range(1, valid):
                if srt[t] != srt[t - 1]:
                    indices[row_start + w] = srt[t]
                    w += 1
            counts[i] = w
    return indptr, indices, counts


@njit(cache=True)
def symmetrize_csr(N, indptr, indices, counts):
    """A <- A U A^T for the undirected layer 1a (generate it at half intensity)."""
    deg = np.zeros(N, dtype=np.int64)
    for i in range(N):
        s = indptr[i]
        for e in range(counts[i]):
            deg[i] += 1
            deg[indices[s + e]] += 1
    new_ptr = np.zeros(N + 1, dtype=np.int64)
    new_ptr[1:] = np.cumsum(deg)
    fill = new_ptr[:-1].copy()
    new_idx = np.empty(new_ptr[N], dtype=np.uint32)
    for i in range(N):
        s = indptr[i]
        for e in range(counts[i]):
            j = indices[s + e]
            new_idx[fill[i]] = j
            fill[i] += 1
            new_idx[fill[j]] = np.uint32(i)
            fill[j] += 1
    out_counts = np.zeros(N, dtype=np.int32)
    for i in range(N):
        a = new_ptr[i]
        b = new_ptr[i + 1]
        if b > a:
            row = np.sort(new_idx[a:b])
            w = 0
            for t in range(b - a):
                if t == 0 or row[t] != row[t - 1]:
                    new_idx[a + w] = row[t]
                    w += 1
            out_counts[i] = w
    return new_ptr, new_idx, out_counts


# ---------------------------------------------------------------------------------
# 3. Contagion step
# ---------------------------------------------------------------------------------
@njit(inline='always')
def _deliver(v, amt, m, cell_id, region_of_cell, b_table,
             inbox_pos, inbox_neg, msg_id, in_pending, pending, n_pend,
             seen, deliv_mr, t_now):
    r = region_of_cell[cell_id[v]]
    amt *= b_table[m, r]                     # believability in v's region
    if amt > 0.0:
        inbox_pos[v] += amt
        msg_id[v] = m                        # last alarming variant delivered
    elif amt < 0.0:
        inbox_neg[v] -= amt
    else:
        return n_pend
    # ADDED: per-message x region reach and delivery-by-hour counters
    if seen[v, m] == 0:
        seen[v, m] = 1
    deliv_mr[t_now, m, r] += 1.0
    if in_pending[v] == 0:
        in_pending[v] = 1
        pending[n_pend] = v
        n_pend += 1
    return n_pend


@njit(cache=True)
def step_multiplex_contagion(
    frontier,                         # uint32[:]  S(t)
    state, posted_mask, msg_id,       # uint8[N] (msg_id int32 here: >255 variants allowed)
    phi_pos, phi_neg,                 # float32[N] read alarm / reassurance
    inbox_pos, inbox_neg,             # float32[N] delivered, unread
    threshold, spread_prop,           # float32[N] theta_i, s_i
    cell_id, cell_offsets,            # int32[N], int64[M+1]
    activity_cell,                    # float32[M] a_c(t) in [0,1] for this step
    q_table,                          # float32[V] signed base intensity per variant
    region_of_cell,                   # int32[M] region r of each cell
    b_table, h_table,                 # float32[V, R] believability, shareability
    indptr_1a, indices_1a, counts_1a, beta_1a, w_1a,
    indptr_d, indices_d, counts_d, layer_d, beta_d, w_d,
    u2g_indptr, u2g_indices, g2u_indptr, g2u_indices, beta_g, w_g,
    U_b, V_b, phi_b, w_b, cons_alias_prob, cons_alias_idx,
    ev_ptr, ev_targets, ev_msg, ev_w,
    inj_pos, inj_neg, inj_msg_pos, inj_msg_neg,
    nu_post, kappa_read, kappa_neg, beta_simple, eps_repeat,
    alpha_stifle, mu_decay,
    in_pending, pending, n_pend,
    seen, deliv_mr, t_now,            # ADDED bookkeeping
):
    M = U_b.shape[0]
    rank = U_b.shape[1]
    n_front = len(frontier)
    stifle = np.zeros(n_front, dtype=np.uint8)
    v_pos = inj_pos.copy()
    v_neg = inj_neg.copy()
    var_mass = np.zeros(len(q_table), dtype=np.float64)
    var_mass_neg = np.zeros(len(q_table), dtype=np.float64)
    if inj_msg_pos >= 0:
        var_mass[inj_msg_pos] += inj_pos.sum()
    if inj_msg_neg >= 0:
        var_mass_neg[inj_msg_neg] += inj_neg.sum()

    # ---- A. spreaders post (snapshot of S(t)) ----
    for idx in range(n_front):
        u = frontier[idx]
        if state[u] != ST_S:
            continue
        a_u = activity_cell[cell_id[u]]
        m = msg_id[u]
        q = q_table[m]
        h_u = h_table[m, region_of_cell[cell_id[u]]]      # shareability where u lives
        if np.random.random() >= 1.0 - np.exp(-nu_post * h_u * a_u):
            # asleep or quiet: only spontaneous decay applies
            if np.random.random() < mu_decay:
                stifle[idx] = 1
            continue
        n_known = 0
        # layer 1a: realised contacts transmit or stifle
        disc = 1.0 if (posted_mask[u] >> BIT_1A) & 1 == 0 else eps_repeat
        s = indptr_1a[u]
        for e in range(counts_1a[u]):
            if np.random.random() < beta_1a:
                v = indices_1a[s + e]
                if state[v] >= ST_B:
                    n_known += 1
                else:
                    n_pend = _deliver(v, w_1a * disc * q, m, cell_id, region_of_cell, b_table,
                                      inbox_pos, inbox_neg, msg_id, in_pending, pending, n_pend,
                                      seen, deliv_mr, t_now)
        posted_mask[u] |= np.uint8(1 << BIT_1A)
        # layers 2-4: u's audience (followers) may see the post
        s = indptr_d[u]
        for e in range(counts_d[u]):
            l = layer_d[s + e]
            if np.random.random() < beta_d[l]:
                v = indices_d[s + e]
                if state[v] < ST_B:
                    bit = 1 + l
                    disc = 1.0 if (posted_mask[u] >> bit) & 1 == 0 else eps_repeat
                    n_pend = _deliver(v, w_d[l] * disc * q, m, cell_id, region_of_cell, b_table,
                                      inbox_pos, inbox_neg, msg_id, in_pending, pending, n_pend,
                                      seen, deliv_mr, t_now)
        for l in range(len(beta_d)):
            posted_mask[u] |= np.uint8(1 << (1 + l))
        # layer 1b: groups
        disc = 1.0 if (posted_mask[u] >> BIT_GROUP) & 1 == 0 else eps_repeat
        for gp in range(u2g_indptr[u], u2g_indptr[u + 1]):
            if np.random.random() < beta_g:
                g = u2g_indices[gp]
                for mp in range(g2u_indptr[g], g2u_indptr[g + 1]):
                    v = g2u_indices[mp]
                    if v != u and state[v] < ST_B:
                        n_pend = _deliver(v, w_g * disc * q, m, cell_id, region_of_cell, b_table,
                                          inbox_pos, inbox_neg, msg_id, in_pending, pending, n_pend,
                                          seen, deliv_mr, t_now)
        posted_mask[u] |= np.uint8(1 << BIT_GROUP)
        # broadcast source mass
        disc = 1.0 if (posted_mask[u] >> BIT_BCAST) & 1 == 0 else eps_repeat
        mass = phi_b[u] * a_u * disc
        if q >= 0.0:
            v_pos[cell_id[u]] += mass * q
            var_mass[m] += mass * q
        else:
            v_neg[cell_id[u]] -= mass * q
            var_mass_neg[m] -= mass * q
        posted_mask[u] |= np.uint8(1 << BIT_BCAST)
        # Maki-Thompson: decay or stifling by realised contacts who already know
        p_r = 1.0 - (1.0 - mu_decay) * (1.0 - alpha_stifle) ** n_known
        if np.random.random() < p_r:
            stifle[idx] = 1

    # ---- B. instigator events (exogenous source term) ----
    for ev in range(len(ev_msg)):
        m = ev_msg[ev]
        amt = ev_w[ev] * q_table[m]
        for p in range(ev_ptr[ev], ev_ptr[ev + 1]):
            v = ev_targets[p]
            if state[v] < ST_B:
                n_pend = _deliver(v, amt, m, cell_id, region_of_cell, b_table,
                                  inbox_pos, inbox_neg, msg_id, in_pending, pending, n_pend,
                                  seen, deliv_mr, t_now)

    # ---- C. algorithmic broadcast: h = U (V^T v), separate signs ----
    m_dom = np.argmax(var_mass)
    m_dom_neg = np.argmax(var_mass_neg)
    for sign in range(2):
        src = v_pos if sign == 0 else v_neg
        z = np.zeros(rank, dtype=np.float64)
        for c in range(M):
            if src[c] != 0.0:
                for k in range(rank):
                    z[k] += V_b[c, k] * src[c]
        for c in range(M):
            h = 0.0
            for k in range(rank):
                h += U_b[c, k] * z[k]
            if h <= 1e-6:
                continue
            c0 = cell_offsets[c]
            c1 = cell_offsets[c + 1]
            if c1 <= c0:
                continue
            for _ in range(np.random.poisson(h)):
                v = c0 + sample_alias(cons_alias_prob[c0:c1], cons_alias_idx[c0:c1])
                if state[v] < ST_B:
                    amt = w_b if sign == 0 else -w_b
                    m_b = m_dom if sign == 0 else m_dom_neg
                    n_pend = _deliver(v, amt, m_b, cell_id, region_of_cell, b_table,
                                      inbox_pos, inbox_neg, msg_id, in_pending, pending, n_pend,
                                      seen, deliv_mr, t_now)

    # ---- D. apply S -> R (synchronous) ----
    for idx in range(n_front):
        if stifle[idx] == 1:
            state[frontier[idx]] = ST_R

    # ---- E. reading + adoption over the pending set ----
    adopted = np.empty(n_pend, dtype=np.uint32)
    n_adopt = 0
    new_spreaders = np.empty(n_pend, dtype=np.uint32)
    n_new = 0
    keep = 0
    for p in range(n_pend):
        v = pending[p]
        if state[v] >= ST_B:                 # already acted: drop
            inbox_pos[v] = 0.0
            inbox_neg[v] = 0.0
            in_pending[v] = 0
            continue
        frac = 1.0 - np.exp(-kappa_read * activity_cell[cell_id[v]])
        x_pos = inbox_pos[v] * frac
        x_neg = inbox_neg[v] * frac
        inbox_pos[v] -= x_pos
        inbox_neg[v] -= x_neg
        phi_pos[v] += x_pos
        phi_neg[v] += x_neg
        if x_pos > 0.0 or x_neg > 0.0:
            if state[v] == ST_U:
                state[v] = ST_E
            eff = phi_pos[v] - kappa_neg * phi_neg[v]
            x_eff = max(0.0, x_pos - kappa_neg * x_neg)
            adopt = eff >= threshold[v]
            if not adopt and x_eff > 0.0:
                adopt = np.random.random() < 1.0 - (1.0 - beta_simple) ** x_eff
            if adopt:
                adopted[n_adopt] = v
                n_adopt += 1
                h_v = h_table[msg_id[v], region_of_cell[cell_id[v]]]
                if np.random.random() < min(1.0, spread_prop[v] * h_v):
                    state[v] = ST_S
                    new_spreaders[n_new] = v
                    n_new += 1
                else:
                    state[v] = ST_B
                inbox_pos[v] = 0.0
                inbox_neg[v] = 0.0
                in_pending[v] = 0
                continue
        if inbox_pos[v] + inbox_neg[v] > 1e-4:
            pending[keep] = v
            keep += 1
        else:
            inbox_pos[v] = 0.0
            inbox_neg[v] = 0.0
            in_pending[v] = 0
    n_pend = keep

    # ---- F. next frontier ----
    nxt = np.empty(n_front + n_new, dtype=np.uint32)
    k = 0
    for idx in range(n_front):
        if state[frontier[idx]] == ST_S:
            nxt[k] = frontier[idx]
            k += 1
    for idx in range(n_new):
        nxt[k] = new_spreaders[idx]
        k += 1
    return nxt[:k], adopted[:n_adopt], n_pend


# ---------------------------------------------------------------------------------
# 4. Per-run draw of regional multipliers (caller side, plain NumPy)
# ---------------------------------------------------------------------------------
def draw_regional_multipliers(score_mean, score_sd, lam, rng):
    s = np.clip(rng.normal(score_mean, score_sd), -1.0, 1.0)
    return np.exp(lam * s).astype(np.float32)
