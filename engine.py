"""Contagion engine v4: Population-Scale Multiplex Contagion spec (multiplex/), wired to the pipeline.

Usage (unchanged from v3, so pipeline/daytona_sweep.py and condense.py keep working):
  python engine.py <scenario_dir> [runs_per_response]
  RUN_KEYS=0:50 RESPONSES=R1_actual OUT_FILE=batch_0.json python engine.py <scenario_dir>

What changed from v3 (engine_v3.py):
  * People live in H3 cells around real regional hubs; each cell has its own clock (spec §2.1, §3.1).
  * Six layers: 1a offline / face-to-face (physical word of mouth), 1b groups, 2-4 X / Instagram /
    Facebook (partly copied from offline ties), 5-6 algorithmic feeds (spec §1-§2). Built once per
    scenario and cached in <scenario>/network.npz.
  * Contagion is the spec's U-E-B-S-R step (multiplex/kernels.py, spec §7): inboxes, reading at local
    activity, threshold + simple adoption, silent actors (B) vs spreaders (S), Maki-Thompson stifling.
  * Regional scores enter only as b = 2^s_b (reader) and h = 2^s_h (sender) (spec §3.5).
Kept from v3: bank facts from bank_config.json, instigator casts, official response schedules,
large-account agents (playbooks v2), cash budget with wire hours, output schema.

Per-run settings are drawn from the spec §8.1 prior ranges. Where the spec gives no range, the
choice is marked ASSUMPTION below.
"""
import json, os, sys
import numpy as np
from multiprocessing import Pool
from multiplex import kernels as kx
from multiplex.network import build as build_network

D = sys.argv[1]
RUNS = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
H = 72
INS_LIMIT_DEFAULT = 250_000

_cfg_path = f"{D}/bank_config.json"
CFG = json.load(open(_cfg_path)) if os.path.exists(_cfg_path) else {}
scen = json.load(open(f"{D}/scenario.json"))
# v3 defaults for SVB (its config file only carries the response schedule)
CFG.setdefault("regions", ["SF_Bay_Area", "New_York", "Boston", "Austin_Seattle_LA", "London_UK", "Israel", "India", "Rest_of_US"])
CFG.setdefault("region_share", [.35, .12, .10, .13, .08, .07, .05, .10])
CFG.setdefault("tz_offset", [0, 3, 3, 1, 8, 10, 13.5, 2])
REG = CFG["regions"]; NR = len(REG)
INS_LIMIT = CFG.get("ins_limit", INS_LIMIT_DEFAULT)
START = CFG.get("start_hour_ref", 17)
START_WD = CFG.get("start_weekday", 2)
CLOSED_WD = set(CFG.get("closed_weekdays", []))
WIRE = CFG.get("wire_hours_ref", [6, 18])
BIG_FRAC = CFG.get("big_account_frac", .30)
SMALL_MED = CFG.get("small_balance_median", 60_000)
C0 = CFG.get("cash_share", .10)
LSCHED = {int(k): v for k, v in CFG.get("liquidity_schedule", {"16": .08, "40": .07}).items()}
CORE = CFG.get("core_region_index", 0)
SEED_CORE, SEED_OTHER = CFG.get("seed_share", [.04, .008])
RESPONSES = list(scen["responses"])
_RH = CFG.get("response_hour", {"R0_silence": None, "R1_ceo_call_next_day": 18, "R2_early_vc_coalition": 4,
                                "R3_full_backstop": 2, "R4_regulator_guarantee": 3})
SCHED = CFG.get("response_schedule") or {r: ([] if _RH.get(r) is None else [{"id": r, "hour": _RH[r], "type": "statement"}]) for r in RESPONSES}

W0 = json.load(open(f"{D}/hour0_weights.json"))
CASTS = json.load(open(f"{D}/instigators.json"))["casts"]
SC = json.load(open(f"{D}/rumour_scores.json"))["messages"]

_la_v2 = f"{D}/large_accounts_v2.json"
_la_path = _la_v2 if os.path.exists(_la_v2) else f"{D}/large_accounts.json"
LA = json.load(open(_la_path))["agents"] if os.path.exists(_la_path) else []
LA_V2 = _la_path == _la_v2
LA_SHARE = sum(a["deposit_share"] for a in LA)
OFF_RANK = {"statement": 1, "backstop": 2}
OFF_NAME = ["none", "statement", "backstop"]

NET = build_network(D, CFG, scen)            # shared by every run (cached network.npz)
N, M = int(NET["N"]), int(NET["M"])
reg = NET["region"]; cell_id = NET["cell_id"]; region_of_cell = NET["region_of_cell"]
region_pop = np.bincount(reg, minlength=NR)


def diurnal(h):
    """A(tau): floor ~0.05 overnight (01-07), peaks morning and evening (spec §3.1, §8.1)."""
    h = h % 24
    if 1 <= h < 7: return 0.05
    if 7 <= h < 9: return 0.6
    if 9 <= h < 12: return 0.85
    if 12 <= h < 17: return 0.65
    if 17 <= h < 22: return 1.0
    return 0.4


ACT = np.array([[diurnal(t + START + NET["tz_cell"][c]) for c in range(M)] for t in range(H)], np.float32)


def _score_stats(samples_by_region, key):
    mu = np.array([np.mean([s[key] for s in samples_by_region[r]]) for r in REG])
    sd = np.array([np.std([s[key] for s in samples_by_region[r]]) for r in REG])
    return mu, sd


def _q(samples_by_region):
    return float(np.mean([s.get("sign", 1) * s["a"] for r in REG for s in samples_by_region[r]]))


def _msg_rng(k, mid):
    return np.random.default_rng([1000 + k, int.from_bytes(mid.encode()[:16].ljust(16, b"_"), "little") % (2 ** 63)])


def _local_working(t, tz):
    lt = t + START + tz
    return 8 <= lt % 24 < 18 and (START_WD + int(lt // 24)) % 7 < 5


def run(args):
    k, resp = args
    rng = np.random.default_rng(1000 + k)       # common random numbers across responses
    kx.seed_engine(1000 + k)
    cast = CASTS[k % 5]["instigators"]

    # ---- variants: 0 = base rumour (q = 1), then instigators, then official messages ----
    msgs = [{"id": "BASE"}] + [dict(m) for m in cast] + [dict(m, official=True) for m in SCHED[resp]]
    V = len(msgs)
    q_table = np.zeros(V, np.float32); b_table = np.ones((V, NR), np.float32); h_table = np.ones((V, NR), np.float32)
    base = {r: W0[r]["samples"] for r in REG}
    for j, m in enumerate(msgs):
        src = base if j == 0 else SC[m["id"]]
        q_table[j] = 1.0 if j == 0 else _q(src)
        mb, sb = _score_stats(src, "b"); mh, sh = _score_stats(src, "h")
        # official messages draw from their own stream so the shared stream (thresholds, seeds,
        # hosts, balances) is identical under every response: common random numbers (spec §3.6)
        r_ = _msg_rng(k, m["id"]) if m.get("official") else rng
        b_table[j] = kx.draw_regional_multipliers(mb, sb, np.log(2), r_)
        h_table[j] = kx.draw_regional_multipliers(mh, sh, np.log(2), r_)

    # ---- per-run behavioural settings (spec §8.1 priors) ----
    threshold = rng.uniform(1.5, 3.0, N).astype(np.float32)
    nu_post = rng.uniform(0.8, 1.2)              # ~1 post per awake hour
    kappa_read = rng.uniform(1.0, 2.0)
    eps_repeat = rng.uniform(0.0, 0.2)
    kappa_neg = rng.uniform(0.5, 1.5)
    s_scale = rng.uniform(0.05, 0.3)
    g = NET["g_pop"]; spread_prop = np.clip(s_scale * np.sqrt(g / g.mean()), 0, 1).astype(np.float32)
    beta_simple = rng.uniform(0.0, 0.02)         # ASSUMPTION: small simple-contagion leak
    alpha_stifle = rng.uniform(0.1, 0.3)         # ASSUMPTION
    mu_decay = rng.uniform(0.01, 0.05)           # ASSUMPTION (per hour)
    beta_1a = rng.uniform(0.3, 0.6)              # ASSUMPTION: chance a close contact hears a given telling
    beta_g = rng.uniform(0.2, 0.4)               # ASSUMPTION
    beta_d = rng.uniform(0.02, 0.08, 3)          # ASSUMPTION: chance a follower sees a given post
    w_1a, w_g, w_b = 1.0, 0.8, 0.5               # ASSUMPTION: w_1a = 1 per spec §8.1 note
    w_d = np.array([0.5, 0.5, 0.5])

    # ---- balances (lognormal below limit, Pareto tail, rank-correlated with connectivity) ----
    big = rng.random(N) < BIG_FRAC
    bal = np.where(big, INS_LIMIT * (rng.pareto(1.1, N) + 1), np.minimum(rng.lognormal(np.log(SMALL_MED), 1, N), INS_LIMIT))
    rho = rng.uniform(.2, .6)
    score = rho * (NET["degree"].argsort().argsort() / N) + (1 - rho) * rng.random(N)
    bal = np.sort(bal)[score.argsort().argsort()]
    alpha_u, alpha_i = rng.uniform(.75, 1.0), rng.uniform(.1, .35)
    out_i = alpha_u * np.maximum(bal - INS_LIMIT, 0) + alpha_i * np.minimum(bal, INS_LIMIT)
    total = bal.sum() / (1 - LA_SHARE)
    C = C0 * total
    L = {kk: v * total for kk, v in LSCHED.items()}

    # ---- state ----
    state = np.zeros(N, np.uint8); posted = np.zeros(N, np.uint8); msg_id = np.zeros(N, np.int32)
    phi_pos = np.zeros(N, np.float32); phi_neg = np.zeros(N, np.float32)
    inbox_pos = np.zeros(N, np.float32); inbox_neg = np.zeros(N, np.float32)
    in_pending = np.zeros(N, np.uint8); pending = np.zeros(N, np.uint32); n_pend = 0
    seen = np.zeros((N, V), np.uint8); deliv = np.zeros((H, V, NR), np.float64)
    frontier = np.zeros(0, np.uint32)
    acted = np.zeros(N, bool)
    conv = np.zeros((V, NR)); shr = np.zeros((V, NR))
    withdraw_h = np.zeros((H, NR)); alarm_read = np.zeros(NR); reas_read = np.zeros(NR); first_reas = np.full(NR, -1)

    # ---- instigator hosts leave the population (spec §4.1 point 1) ----
    events = {}                                  # hour -> list of (targets, msg, weight) / broadcast injections
    gp = NET["g_pop"]; f1 = NET["f1a"]
    ipd, cd, ixd = NET["indptr_d"], NET["counts_d"], NET["indices_d"]
    ip1, c1, ix1 = NET["indptr_1a"], NET["counts_1a"], NET["indices_1a"]
    u2g, u2gi, g2u, g2ui = NET["u2g_indptr"], NET["u2g_indices"], NET["g2u_indptr"], NET["g2u_indices"]
    for j, m in enumerate(msgs[1:], 1):
        if m.get("official"):                    # official statement: email/app push to every customer
            tg = np.where(_msg_rng(k, m["id"] + "/reach").random(N) < .85)[0]
            events.setdefault(int(m["hour"]), []).append(("ev", tg, j, 1.0, OFF_RANK.get(m["type"], 1)))
            continue
        home = REG.index(m["home"]) if m.get("home") in REG else CORE
        pool = np.where((reg == home) & (state == kx.ST_U))[0]
        wts = (gp[pool] ** 2) if m["persona"] in ("arsonist", "sceptical_journalist", "bot_farm") else f1[pool]
        host = int(rng.choice(pool, p=wts / wts.sum()))
        state[host] = kx.ST_R                    # outside the state machine from now on
        t = int(max(1, round((m.get("post_hour_local", 18) - CFG["tz_offset"][home] - START) % 24)))
        tregs = [REG.index(x) for x in m.get("target_regions", [m.get("home")]) if x in REG] or [home]
        frac = min(.5, m.get("audience_size", 10000) / 2e6 * (1 + np.log1p(m.get("reposts", 0)) / 5))
        w = 1.0
        if m["persona"] in ("arsonist", "sceptical_journalist"):
            tg = ixd[ipd[host]:ipd[host] + cd[host]].astype(np.int64)
            events.setdefault(t, []).append(("ev", tg, j, w, 0))
        if m["persona"] in ("mutator", "local_debunker"):
            grp = [g2ui[g2u[g]:g2u[g + 1]] for g in u2gi[u2g[host]:u2g[host + 1]]]
            tg = np.unique(np.concatenate(grp + [ix1[ip1[host]:ip1[host] + c1[host]]])).astype(np.int64)
            events.setdefault(t, []).append(("ev", tg, j, w, 0))
        if m["persona"] in ("bot_farm", "sceptical_journalist"):
            inj = np.zeros(M); mask = np.isin(region_of_cell, tregs)
            ncell = np.diff(NET["cell_offsets"]).astype(float)
            inj[mask] = frac * ncell[mask] / 20.0     # arrivals ~ frac x target population (lam_b = 20)
            events.setdefault(t, []).append(("inj", inj, j, q_table[j], 0))
    seeds = np.where((rng.random(N) < np.where(reg == CORE, SEED_CORE, SEED_OTHER)) & (state == kx.ST_U))[0]
    events.setdefault(0, []).append(("ev", seeds, 0, 1.0, 0))

    # ---- large-account agents (playbooks v2, unchanged from v3) ----
    la_bal = np.array([a["deposit_share"] * total for a in LA]); la_reg = np.array([REG.index(a["region"]) for a in LA], int)
    la_wd = np.zeros(NR); la_committed = np.zeros(len(LA)); pending_la = []
    worked = np.array([a.get("review_every_hours", 6) for a in LA], float)
    ag_al = np.zeros(len(LA)); ag_re = np.zeros(len(LA)); official = 0
    tz = np.array(CFG["tz_offset"], float)

    fail_hour = None; queue = 0.0
    for t in range(H):
        ev_lists = []; ev_msg = []; ev_w = []
        inj_pos = np.zeros(M); inj_neg = np.zeros(M); inj_mp = -1; inj_mn = -1
        for item in events.get(t, []):
            kind, a, j, w, rank = item
            if kind == "ev":
                ev_lists.append(np.asarray(a, np.uint32)); ev_msg.append(j); ev_w.append(w)
                official = max(official, rank)
            else:                                # broadcast injection, split by sign
                if w >= 0: inj_pos += a; inj_mp = j
                else: inj_neg += a; inj_mn = j
        ev_ptr = np.zeros(len(ev_lists) + 1, np.int64); ev_ptr[1:] = np.cumsum([len(x) for x in ev_lists])
        ev_t = np.concatenate(ev_lists) if ev_lists else np.zeros(0, np.uint32)
        pp0 = np.bincount(reg, weights=phi_pos, minlength=NR); pn0 = np.bincount(reg, weights=phi_neg, minlength=NR)
        frontier, adopted, n_pend = kx.step_multiplex_contagion(
            frontier, state, posted, msg_id, phi_pos, phi_neg, inbox_pos, inbox_neg, threshold, spread_prop,
            cell_id, NET["cell_offsets"], ACT[t], q_table, region_of_cell, b_table, h_table,
            ip1, ix1, c1, beta_1a, w_1a,
            ipd, ixd, cd, NET["layer_d"], beta_d, w_d,
            u2g, u2gi, g2u, g2ui, beta_g, w_g,
            NET["U_b"], NET["V_b"], NET["phi_b"], w_b, NET["cons_alias_prob"], NET["cons_alias_idx"],
            ev_ptr, ev_t, np.array(ev_msg, np.int32), np.array(ev_w, np.float64),
            inj_pos, inj_neg, inj_mp, inj_mn,
            nu_post, kappa_read, kappa_neg, beta_simple, eps_repeat, alpha_stifle, mu_decay,
            in_pending, pending, n_pend, seen, deliv, t)
        d_al = np.bincount(reg, weights=phi_pos, minlength=NR) - pp0
        d_re = np.bincount(reg, weights=phi_neg, minlength=NR) - pn0
        alarm_read += d_al; reas_read += d_re
        first_reas[(first_reas < 0) & (d_re > 0)] = t
        if len(adopted):
            ad = adopted.astype(np.int64); acted[ad] = True
            np.add.at(conv, (msg_id[ad], reg[ad]), 1)
            sp = ad[state[ad] == kx.ST_S]; np.add.at(shr, (msg_id[sp], reg[sp]), 1)
            withdraw_h[t] += np.bincount(reg[ad], weights=out_i[ad], minlength=NR)

        if LA and LA_V2:                         # large accounts: business hours, approvals, official signal
            adopt = np.bincount(reg, weights=acted, minlength=NR) / np.maximum(region_pop, 1)
            cash_state = "safe" if C - queue >= .5 * C0 * total else "stressed"
            for i, ag in enumerate(LA):
                r = la_reg[i]
                if not (_local_working(t, tz[r]) or ag.get("works_after_hours")): continue
                worked[i] += 1
                if worked[i] < ag.get("review_every_hours", 6): continue
                worked[i] = 0
                key = "|".join([OFF_NAME[official], "low" if adopt[r] < .005 else ("med" if adopt[r] <= .03 else "high"),
                                cash_state, "alarmed" if alarm_read[r] - ag_al[i] > reas_read[r] - ag_re[i] else "calm"])
                ag_al[i] = alarm_read[r]; ag_re[i] = reas_read[r]
                dd = ag["playbook"][key]; exposure = la_bal[i] - la_committed[i]
                amt = 0.0 if dd["action"] == "stay" else (exposure if dd["action"] == "pull" else max(0.0, exposure - (1 - dd["fraction"]) * la_bal[i]))
                if amt > 0:
                    la_committed[i] += amt; pending_la.append((t + ag.get("approval_lag_hours", 0), i, amt))
            keep = []
            for (due, i, amt) in pending_la:
                if due <= t and _local_working(t, tz[la_reg[i]]):
                    la_wd[la_reg[i]] += amt; withdraw_h[t, la_reg[i]] += amt
                else:
                    keep.append((due, i, amt))
            pending_la = keep

        queue += withdraw_h[t].sum()
        C += L.get(t, 0)
        day = (START_WD + (t + START) // 24) % 7
        if WIRE[0] <= (t + START) % 24 < WIRE[1] and day not in CLOSED_WD:   # wires settle in business hours
            C -= queue; queue = 0.0
        if C < 0 and fail_hour is None:
            fail_hour = t
            break

    reached = np.zeros((V, NR))
    for r in range(NR):
        reached[:, r] = seen[reg == r].sum(0) / max(region_pop[r], 1)
    return dict(k=k, resp=resp, fail=fail_hour, withdrawn=float(withdraw_h.sum() / total),
                wd_region=(withdraw_h.sum(0) / total).tolist(), ids=[m["id"] for m in msgs],
                reached=reached.tolist(), conv=conv.tolist(), shr=shr.tolist(),
                peak=deliv.argmax(0).tolist(), alarm_read=alarm_read.tolist(), reas_read=reas_read.tolist(),
                first_reas=first_reas.tolist(), alarm_peak=[int(deliv[:, 0, :].sum(1).argmax())],
                region_pop=region_pop.tolist(), adopters=int(acted.sum()),
                la_withdrawn=float(la_wd.sum() / total), la_wd_region=(la_wd / total).tolist(),
                wd_hourly_region=(withdraw_h / total).round(6).tolist())


if __name__ == "__main__":
    keys = range(RUNS)
    if os.environ.get("RUN_KEYS"):
        a, b = map(int, os.environ["RUN_KEYS"].split(":"))
        keys = range(a, b)
    resps = os.environ["RESPONSES"].split(",") if os.environ.get("RESPONSES") else RESPONSES
    jobs = [(k, r) for r in resps for k in keys]
    with Pool(os.cpu_count()) as p:
        res = p.map(run, jobs, chunksize=4)
    json.dump(res, open(os.path.join(D, os.environ.get("OUT_FILE", "runs.json")), "w"))
    for r in resps:
        rr = [x for x in res if x["resp"] == r]
        s = np.mean([x["fail"] is None for x in rr])
        print(r, f"survival={s:.3f}", "median_withdrawn=%.3f" % np.median([x["withdrawn"] for x in rr]),
              "median_adopters=%d" % np.median([x["adopters"] for x in rr]))
