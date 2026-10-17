"""Pre-run LLM stage: everything an LLM writes, produced and scored BEFORE any simulation run.

    python -m pipeline.pre_run data/<scenario> [--samples 3] [--casts 5] [--skip playbooks]

Writes into the scenario directory:
    hour0_weights.json      one call per region x samples (plan: 3-5 samples; spread feeds the runs)
    instigators.json        one call per storyline (5 casts x 7 instigators, sampling on)
    rumour_scores.json      one call per region scoring all messages (batched: see caveat below)
    large_accounts_v2.json  one call writing all large-account playbooks (spec: playbook_spec_v2.md)

Inputs you provide first (Droid intake fills these; see droid_analyst.py):
    scenario.json, bank_config.json (incl. response_schedule with the company's ACTUAL statements and
    their times), and for playbooks a facts file with the large-account share and archetypes.

Rules carried over from the plan and from what we learned running it:
  * Instigators' own alarm/calm label is never trusted; the scorer judges every text independently.
  * Official messages (actual statements, counterfactual responses) are scored exactly like rumours.
  * Backtests: every prompt carries an "as of <time>, no hindsight" instruction. Blindness also means
    freezing engine.py (sha256) and writing the prediction before anyone researches the outcome.
  * Caveat (plan): batching a whole region's messages into one scoring call risks the evaluator
    judging rumours against each other. Accepted for the hackathon; note it in your README.
  * Ask for hand judgments, not formulas: one subagent once spread base scores across regions with
    a script plus noise, which made the regional detail partly mechanical.
"""
import argparse, json, pathlib
from concurrent.futures import ThreadPoolExecutor
from .llm import complete_json

SYSTEM = ("You are a careful analyst inside a bank-run / boycott contagion simulator. "
          "Return exactly one JSON object and nothing else.")

HOUR0 = """Score this base rumour for ONE region, as the hour-0 evaluator.
Judge only from information available at: {as_of}. Do not use hindsight about how this ended.
Company type: {company_type}. Question for this type: {question}
Base rumour: {rumour}
Region: {region}. Region facts (data, not opinion): {facts}
Reference region (b=h=0): {reference}
Return {{"b": -1..1 believability vs reference, "h": -1..1 shareability vs reference,
         "a": 0..1 alarm (push toward acting), "reason": "one line"}}"""

INSTIGATORS = """Write storyline #{k} of instigators who post at hour 1 (sim starts {as_of}; no hindsight).
Scenario: {scenario}
Cast: 2 arsonist (alarming, large X account), 2 mutator (alarming, group chats, twist the rumour),
1 bot_farm (alarming, low believability, high volume, posts 03:00 local), 1 local_debunker (calming,
group chats, very believable at home), 1 sceptical_journalist (calming, feeds, far reach).
Do NOT include the company's official response; calming instigators are organic.
Valid regions: {regions}. Channels: x, group_chat, feed. Vary home regions, wording, tone, timing.
Return {{"cast": {k}, "instigators": [{{"id": "c{k}_i0", "persona": "...", "home": "...", "intended": "alarm|calm",
  "channel": "...", "text": "1-3 sentences", "target_regions": [...], "post_hour_local": 0-23,
  "reposts": int, "audience_size": int}}, ... 7 total]}}"""

SCORE = """Score every message below for readers in ONE region, as the independent rumour evaluator.
Judge as of {as_of}, no hindsight. IGNORE any intended label: judge the text (a clumsy denial can alarm).
Official company statements are scored the same way as rumours.
Region: {region}. Facts: {facts}. Reference region (b=h=0): {reference}
Messages (id: text): {messages}
Give TWO independent samples per message. Make each judgment yourself, not from a formula.
Return {{"<id>": [{{"sign": 1 or -1, "a": 0..1, "b": -1..1, "h": -1..1}}, {{...}}], ...}}"""

PLAYBOOKS = """Write large-account agent playbooks following this spec exactly:
{spec}
Company and moment: {scenario} (judge as of {as_of}, no hindsight).
Facts: {facts}
Large accounts hold {share} of total deposits; deposit_share across agents must sum to that.
Make {n_groups} archetype/region groups x 3 instances (cautious/typical/sticky).
Valid regions: {regions}.
Return {{"agents": [{{"id": "la0", "archetype": "...", "instance": "...", "region": "...",
  "deposit_share": float, "reason": "...", "review_every_hours": int, "works_after_hours": bool,
  "approval_lag_hours": int, "playbook": {{"<official|adopt|cash|sent>": {{"action": "stay|reduce|pull",
  "fraction": 0..1}}, ... all 36 keys}}}}]}}
Judge each archetype's real incentives by hand; do not generate actions from a formula."""

QUESTION = {"bank": "How believable is this here, and how strongly does it push a depositor to withdraw?",
            "brand": "How much does this make someone here want to stop buying?"}


def _load(d, name):
    p = d / name
    return json.loads(p.read_text()) if p.exists() else None


def run(d: pathlib.Path, samples=3, casts=5, skip=()):
    sc, cfg = _load(d, "scenario.json"), _load(d, "bank_config.json") or {}
    regions = list(sc["regions"])
    ref, as_of = regions[-1] if "Rest_of_US" in regions else regions[0], sc["start"]
    pool = ThreadPoolExecutor(16)

    if "hour0" not in skip:
        jobs = {(r, s): pool.submit(complete_json, "hour0", SYSTEM, HOUR0.format(
            as_of=as_of, company_type=sc["company_type"], question=QUESTION.get(sc["company_type"], QUESTION["bank"]),
            rumour=sc["base_rumour"], region=r, facts=sc["regions"][r], reference=ref),
            {"r": r, "rumour": sc["base_rumour"]}, s) for r in regions for s in range(samples)}
        out = {r: {"samples": [jobs[(r, s)].result() for s in range(samples)]} for r in regions}
        (d / "hour0_weights.json").write_text(json.dumps(out, indent=1))

    if "instigators" not in skip:
        futs = [pool.submit(complete_json, "instigators", SYSTEM, INSTIGATORS.format(
            k=k, as_of=as_of, scenario=json.dumps(sc), regions=", ".join(regions)), {"k": k, "sc": sc}, k)
            for k in range(casts)]
        (d / "instigators.json").write_text(json.dumps({"casts": [f.result() for f in futs]}, indent=1))

    if "scoring" not in skip:
        inst = _load(d, "instigators.json")
        msgs = {m["id"]: m["text"] for c in inst["casts"] for m in c["instigators"]}
        for resp, items in (cfg.get("response_schedule") or {}).items():
            for it in items:   # actual statements: put their text in scenario.json["official_texts"][id]
                msgs[it["id"]] = sc.get("official_texts", {}).get(it["id"], sc["responses"].get(it["id"], it["id"]))
        futs = {r: pool.submit(complete_json, "score", SYSTEM, SCORE.format(
            as_of=as_of, region=r, facts=sc["regions"][r], reference=ref, messages=json.dumps(msgs)),
            {"r": r, "m": msgs}) for r in regions}
        by_region = {r: f.result() for r, f in futs.items()}
        scores = {mid: {r: by_region[r][mid] for r in regions} for mid in msgs}
        for r0 in ("R0_silence",):  # silence = no message; engine never reads it, kept for completeness
            scores[r0] = {r: [dict(sign=1, a=0, b=0, h=0)] * 2 for r in regions}
        (d / "rumour_scores.json").write_text(json.dumps({"messages": scores}, indent=1))

    if "playbooks" not in skip:
        facts = _load(d, "large_account_facts.json") or _load(d, "bank_facts.json") or {}
        share = facts.get("large_share", {}).get("best") if isinstance(facts.get("large_share"), dict) else cfg.get("large_account_share")
        if share:
            spec = (pathlib.Path(__file__).parent / "playbook_spec_v2.md").read_text()
            out = complete_json("playbooks", SYSTEM, PLAYBOOKS.format(
                spec=spec, scenario=json.dumps(sc), as_of=as_of, facts=json.dumps(facts), share=share,
                n_groups=8, regions=", ".join(regions)), {"facts": facts, "share": share}, max_tokens=128000)
            assert all(len(a["playbook"]) == 36 for a in out["agents"]), "every agent needs all 36 states"
            (d / "large_accounts_v2.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario_dir"); ap.add_argument("--samples", type=int, default=3)
    ap.add_argument("--casts", type=int, default=5); ap.add_argument("--skip", nargs="*", default=[])
    a = ap.parse_args()
    run(pathlib.Path(a.scenario_dir), a.samples, a.casts, set(a.skip))
