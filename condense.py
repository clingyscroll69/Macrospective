"""Condense runs.json into one evidence pack per response (code only, no LLM)."""
import json, sys
import numpy as np
from collections import Counter

D = sys.argv[1]
import os
_cfg = json.load(open(f"{D}/bank_config.json")) if os.path.exists(f"{D}/bank_config.json") else {}
REG = _cfg.get("regions", ["SF_Bay_Area", "New_York", "Boston", "Austin_Seattle_LA", "London_UK", "Israel", "India", "Rest_of_US"])
START, START_WD = _cfg.get("start_hour_ref", 17), _cfg.get("start_weekday", 2)
REF_TZ = _cfg.get("ref_clock_label", "PT" if "regions" not in _cfg else "ref")
runs = json.load(open(f"{D}/runs.json"))
casts = {m["id"]: m for c in json.load(open(f"{D}/instigators.json"))["casts"] for m in c["instigators"]}
scores = json.load(open(f"{D}/rumour_scores.json"))["messages"]
scen = json.load(open(f"{D}/scenario.json"))

def pt(t):  # sim hour -> "Thu 06:00 <ref clock>"
    h = t + START
    return f"{['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][(START_WD + h // 24) % 7]} {h % 24:02d}:00 {REF_TZ}"

def r2(x): return round(float(x), 2)

def pattern(x):
    if x["fail"] is None: return "contained (bank survives 72h)"
    wd = np.array(x["wd_region"]); top = REG[int(wd.argmax())]
    when = f"at {pt(x['fail'])}"
    return f"fails {when}, led by {top}"

packs = {}
for resp in scen["responses"]:
    rr = [x for x in runs if x["resp"] == resp]
    n = len(rr); surv = np.mean([x["fail"] is None for x in rr])
    ci = 1.96 * np.sqrt(surv * (1 - surv) / n)
    fh = [x["fail"] for x in rr if x["fail"] is not None]
    # per-message aggregation across runs that contain it
    agg = {}
    for x in rr:
        pop = np.array(x["region_pop"])
        for j, mid in enumerate(x["ids"]):
            a = agg.setdefault(mid, dict(n=0, reached=np.zeros(len(REG)), conv=np.zeros(len(REG)), shr=np.zeros(len(REG)), peak=[]))
            a["n"] += 1; a["reached"] += np.array(x["reached"][j])
            a["conv"] += np.array(x["conv"][j]) / pop; a["shr"] += np.array(x["shr"][j]) / pop
            a["peak"].append(x["peak"][j])
    rumours = []
    for mid, a in agg.items():
        meta = casts.get(mid, {})
        sc = scores.get(mid)
        rumours.append(dict(
            id=mid, persona=meta.get("persona", "base_rumour" if mid == "BASE" else "official_response"),
            text=meta.get("text", scen["base_rumour"] if mid == "BASE" else scen["responses"].get(mid, "")),
            runs_present=a["n"],
            scored_alarm_by_region=({r: r2(np.mean([s["sign"] * s["a"] for s in sc[r]])) for r in REG} if sc else "see hour0 weights"),
            reach_share=dict(zip(REG, map(r2, a["reached"] / a["n"]))),
            converted_share=dict(zip(REG, [round(float(v), 4) for v in a["conv"] / a["n"]])),
            sharer_share=dict(zip(REG, [round(float(v), 4) for v in a["shr"] / a["n"]])),
            median_peak_hour_by_region=dict(zip(REG, [pt(int(v)) for v in np.median(np.array(a["peak"]), 0)]))))
    rumours.sort(key=lambda d: -sum(d["converted_share"].values()))
    rumours = rumours[:12]
    inter = {}
    for i, r in enumerate(REG):
        fr = [x["first_reas"][i] for x in rr if x["first_reas"][i] >= 0]
        ar = np.mean([x["alarm_read"][i] for x in rr]); rs = np.mean([x["reas_read"][i] for x in rr])
        top = Counter()
        for x in rr:
            for j, mid in enumerate(x["ids"]): top[mid] += x["conv"][j][i]
        inter[r] = dict(first_reassurance=pt(int(np.median(fr))) if fr else "never",
                        base_alarm_peak=pt(int(np.median([x["alarm_peak"][0] for x in rr]))),
                        alarm_to_reassurance_ratio=r2(ar / max(rs, 1e-9)),
                        top_converter=top.most_common(1)[0][0],
                        median_withdrawn_share_of_deposits=round(float(np.median([x["wd_region"][i] for x in rr])), 3))
    pats = Counter(pattern(x) for x in rr)
    packs[resp] = dict(
        response=resp, response_text=scen["responses"][resp], runs=n,
        outcome=dict(survival_share=r2(surv), ci95_points=r2(ci),
                     typical_failure_hour=pt(int(np.median(fh))) if fh else "none",
                     median_withdrawn_before_stop=r2(np.median([x["withdrawn"] for x in rr]))),
        outcome_types={k: r2(v / n) for k, v in pats.most_common(5)},
        interaction=inter, rumour_sheet=rumours)
json.dump(packs, open(f"{D}/evidence.json", "w"), indent=1)
for k, v in packs.items(): print(k, v["outcome"])
