"""Contagion engine (Daytona stand-in): one shared network, per-rumour counters, bank damage model.
Usage: python engine.py <sim_dir> [runs_per_response]
All LLM outputs (hour0_weights, instigators, rumour_scores) are frozen inputs read from <sim_dir>.
"""
import json, sys, os
import numpy as np
import scipy.sparse as sp
from multiprocessing import Pool

D = sys.argv[1]
RUNS = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
H = 72
N = 4000
INS_LIMIT = 250_000

REG = ["SF_Bay_Area", "New_York", "Boston", "Austin_Seattle_LA", "London_UK", "Israel", "India", "Rest_of_US"]
SHARE = np.array([.35, .12, .10, .13, .08, .07, .05, .10])        # region facts: share of SVB customers
TZ = np.array([0, 3, 3, 1, 8, 10, 13.5, 2])                        # offset from PT
HOMOPHILY = np.array([.85, .7, .75, .65, .8, .9, .85, .6])
# response timing in sim hours (hour 0 = 17:00 PT Mar 8)
RESP_HOUR = {"R0_silence": None, "R1_ceo_call_next_day": 18, "R2_early_vc_coalition": 4,
             "R3_full_backstop": 2, "R4_regulator_guarantee": 3}

scen = json.load(open(f"{D}/scenario.json"))
W0 = json.load(open(f"{D}/hour0_weights.json"))
CASTS = json.load(open(f"{D}/instigators.json"))["casts"]
SC = json.load(open(f"{D}/rumour_scores.json"))["messages"]
RESPONSES = list(scen["responses"])

def activity(local_h):
    h = local_h % 24
    if h < 6: return .02
    if h < 8: return .25
    if h < 12: return .55
    if h < 17: return .4
    if h < 23: return .5
    return .15

ACT = np.array([[activity(t + 17 + TZ[r]) for r in range(8)] for t in range(H)])  # H x regions

def draw_scores(rng, samples_by_region):
    """returns signed alarm (+) / reassurance (-) magnitude, believability factor, share factor per region"""
    a, b, h = np.zeros(8), np.zeros(8), np.zeros(8)
    for j, r in enumerate(REG):
        ss = samples_by_region[r]
        s = ss[rng.integers(len(ss))]
        sd = np.std([x["a"] for x in ss]) + .03
        sign = s.get("sign", 1)
        a[j] = sign * max(0, s["a"] + rng.normal(0, sd))
        b[j] = np.clip(s["b"] + rng.normal(0, .05), -1, 1)
        h[j] = np.clip(s["h"] + rng.normal(0, .05), -1, 1)
    return a, (1 + b) / 2, (1 + h) / 2

def build_world(rng):
    reg = rng.choice(8, N, p=SHARE)
    # network: group chats (clustered, same region) + X follows (heavy-tailed)
    rows, cols = [], []
    for r in range(8):
        idx = np.where(reg == r)[0]
        rng.shuffle(idx)
        for g in np.array_split(idx, max(1, len(idx) // 12)):
            for i in g:
                for j in g:
                    if i != j and rng.random() < .5: rows.append(i); cols.append(j)
    pop = rng.pareto(1.5, N) + 1
    pop_p = pop / pop.sum()
    for i in range(N):
        k = rng.poisson(6)
        same = rng.random(k) < HOMOPHILY[reg[i]]
        for s in same:
            if s:
                cand = np.where(reg == reg[i])[0]
                j = rng.choice(cand, p=pop_p[cand] / pop_p[cand].sum())
            else:
                j = rng.choice(N, p=pop_p)
            if j != i: rows.append(j); cols.append(i)   # i follows j -> j's shares reach i
    A = sp.csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(N, N))
    A.data[:] = 1
    deg = np.asarray(A.sum(1)).ravel()
    # balances: lognormal below limit, Pareto tail above; rank-correlated with connectivity
    big = rng.random(N) < .30
    bal = np.where(big, INS_LIMIT * (rng.pareto(1.1, N) + 1), np.minimum(rng.lognormal(np.log(60_000), 1, N), INS_LIMIT))
    rho = rng.uniform(.2, .6)
    score = rho * (deg.argsort().argsort() / N) + (1 - rho) * rng.random(N)
    bal = np.sort(bal)[score.argsort().argsort()]
    return reg, A.T.tocsr(), bal   # transposed: deliveries = AT @ sharers

def run(args):
    k, resp = args
    rng = np.random.default_rng(1000 + k)          # common random numbers across responses
    reg, AT, bal = build_world(rng)
    cast = CASTS[k % 5]["instigators"]
    # remove the instigators' sampled host customers from the population
    alive = np.ones(N, bool)
    msgs = [{"id": "BASE"}] + [dict(m) for m in cast] + ([{"id": resp}] if RESP_HOUR[resp] is not None else [])
    M = len(msgs)
    a = np.zeros((M, 8)); bf = np.zeros((M, 8)); hf = np.zeros((M, 8))
    base = {r: [dict(sign=1, **s) for s in W0[r]["samples"]] for r in REG}
    a[0], bf[0], hf[0] = draw_scores(rng, base)
    for m in range(1, M):
        a[m], bf[m], hf[m] = draw_scores(rng, SC[msgs[m]["id"]])
    eff = a * bf                                    # signed per-read push, per message x region

    theta = rng.lognormal(np.log(2.2), .6, N)       # action threshold
    w_reas = rng.uniform(.8, 1.4)                   # weight of reassurance vs alarm
    share_p = rng.uniform(.10, .18)
    alpha_u, alpha_i = rng.uniform(.75, 1.0), rng.uniform(.1, .35)
    out_i = alpha_u * np.maximum(bal - INS_LIMIT, 0) + alpha_i * np.minimum(bal, INS_LIMIT)
    total = bal.sum()
    C = .10 * total
    L = {16: .08 * total, 40: .07 * total}          # FHLB / repo raised next business mornings

    inbox = np.zeros((N, M)); sharers = np.zeros((N, M))
    Aacc = np.zeros(N); Racc = np.zeros(N)
    acted = np.zeros(N, bool); shared = np.zeros(N, bool); converter = -np.ones(N, int)
    reached = np.zeros((M, 8)); conv = np.zeros((M, 8)); shr = np.zeros((M, 8))
    reads_by_h = np.zeros((H, M, 8)); withdraw_h = np.zeros((H, 8))
    alarm_read = np.zeros(8); reas_read = np.zeros(8); first_reas = np.full(8, -1)
    ever = np.zeros((N, M), bool)
    fail_hour = None
    queue = 0.0

    # hour 0: base rumour seeded in Bay Area VC group chats + press coverage
    seed = rng.random(N) < np.where(reg == 0, .04, .008)
    inbox[seed, 0] += 1
    # instigator posts (outside events)
    posts = []
    for j, m in enumerate(msgs[1:], 1):
        if m["id"] in RESP_HOUR:
            posts.append((RESP_HOUR[m["id"]], j, None, 1.0)); continue
        home = REG.index(m["home"]) if m.get("home") in REG else 0
        t = (m.get("post_hour_local", 18) - TZ[home] - 17) % 24
        t = max(1, int(round(t)))
        tg = [REG.index(x) for x in m.get("target_regions", [m.get("home")]) if x in REG] or [home]
        frac = min(.5, m.get("audience_size", 10000) / 2e6 * (1 + np.log1p(m.get("reposts", 0)) / 5))
        if m["persona"] == "bot_farm": frac = min(.6, frac * 2)
        if m["persona"] in ("mutator", "local_debunker"): frac = max(frac, .05)
        posts.append((t, j, tg, frac))
    alive[rng.choice(N, len(cast), replace=False)] = False

    for t in range(H):
        for (pt, j, tg, frac) in posts:
            if pt == t:
                if tg is None:   # official response: email/app push to every customer + press
                    inbox[:, j] += (rng.random(N) < .85)
                else:
                    inbox[np.isin(reg, tg) & (rng.random(N) < frac), j] += 1
        if sharers.any():
            inbox += AT @ sharers
            sharers[:] = 0
        act_p = ACT[t, reg][:, None]
        read = rng.binomial(inbox.astype(np.int64), np.broadcast_to(act_p, inbox.shape)).astype(float)
        read[~alive] = 0
        inbox -= read
        hit = read > 0
        if hit.any():
            push = eff[:, reg].T * np.minimum(read, 3)          # N x M, diminishing repeats
            Aacc += np.clip(push, 0, None).sum(1); Racc += -np.clip(push, None, 0).sum(1)
            for r in range(8):
                mr = reg == r
                reads_by_h[t, :, r] = read[mr].sum(0)
                alarm_read[r] += np.clip(push[mr], 0, None).sum(); reas_read[r] += -np.clip(push[mr], None, 0).sum()
                if first_reas[r] < 0 and (push[mr] < 0).any(): first_reas[r] = t
            newly = hit & ~ever; ever |= hit
            for r in range(8): reached[:, r] += newly[reg == r].sum(0)
            # sharing: once per person, the message that hit them hardest (by |push| x shareability)
            cand = hit.any(1) & ~shared & alive
            strength = np.abs(push) * hf[:, reg].T
            best = strength.argmax(1)
            sp_ = cand & (rng.random(N) < share_p * 2 * strength.max(1).clip(0, 1) + .02 * cand)
            shared |= sp_
            sharers[np.where(sp_)[0], best[sp_]] = 1
            for i in np.where(sp_)[0]: shr[best[i], reg[i]] += 1
            # acting: alarm minus weighted reassurance crosses threshold
            go = ~acted & alive & (Aacc - w_reas * Racc > theta)
            if go.any():
                acted |= go
                cbest = np.clip(push, 0, None).argmax(1)
                converter[go] = cbest[go]
                for i in np.where(go)[0]: conv[cbest[i], reg[i]] += 1
                withdraw_h[t] = np.bincount(reg[go], weights=out_i[go], minlength=8)
        queue += withdraw_h[t].sum()
        C += L.get(t, 0)
        if 6 <= (t + 17) % 24 < 18:                 # wires settle only in PT business hours
            C -= queue; queue = 0.0
        if C < 0 and fail_hour is None:
            fail_hour = t
            break
    peak = reads_by_h.argmax(0)
    return dict(k=k, resp=resp, fail=fail_hour, withdrawn=float(withdraw_h.sum() / total),
                wd_region=(withdraw_h.sum(0) / total).tolist(), ids=[m["id"] for m in msgs],
                reached=(reached / np.bincount(reg, minlength=8)).tolist(), conv=conv.tolist(), shr=shr.tolist(),
                peak=peak.tolist(), alarm_read=alarm_read.tolist(), reas_read=reas_read.tolist(),
                first_reas=first_reas.tolist(), alarm_peak=reads_by_h[:, 0:1].sum(1).argmax(0).tolist(),
                region_pop=np.bincount(reg, minlength=8).tolist())

if __name__ == "__main__":
    jobs = [(k, r) for r in RESPONSES for k in range(RUNS)]
    with Pool(os.cpu_count()) as p:
        res = p.map(run, jobs, chunksize=10)
    json.dump(res, open(f"{D}/runs.json", "w"))
    for r in RESPONSES:
        rr = [x for x in res if x["resp"] == r]
        s = np.mean([x["fail"] is None for x in rr])
        print(r, f"survival={s:.3f}", "median_withdrawn=%.3f" % np.median([x["withdrawn"] for x in rr]))
