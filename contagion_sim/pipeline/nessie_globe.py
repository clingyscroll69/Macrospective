"""Globe playback + Capital One Nessie link (bank demo only; drop if you pitch a brand).

    python -m pipeline.nessie_globe data/<scenario> --response R1_actual --run 0 [--post]

Picks one run, writes globe_run.json (hour x region withdrawals as shares of deposits, plus the
official messages and their hours) for the globe coder, and with --post replays each hour's
withdrawals as Nessie withdrawals so the cash gauge reads from the "bank".

NESSIE INTEGRATION (verify at http://api.nessieisreal.com/documentation):
  * export NESSIE_KEY=... ; create one demo customer + account per region beforehand and put the
    account ids in NESSIE_ACCOUNTS as JSON: {"SF_Bay_Area": "<account_id>", ...}
  * Simulated amounts are SHARES of deposits; DEMO_DEPOSITS scales them into dollars for display only.
  * The plan's live LLM calls for the globe run (hour-by-hour narrative) belong in droid_analyst.py;
    this file only replays numbers the engine already produced.
"""
import argparse, json, os, pathlib, time
import requests

API = "http://api.nessieisreal.com"
DEMO_DEPOSITS = float(os.environ.get("DEMO_DEPOSITS", 1_000_000))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario_dir"); ap.add_argument("--response", required=True)
    ap.add_argument("--run", type=int, default=0); ap.add_argument("--post", action="store_true")
    ap.add_argument("--seconds-per-hour", type=float, default=1.0)
    a = ap.parse_args()
    d = pathlib.Path(a.scenario_dir)
    cfg = json.loads((d / "bank_config.json").read_text())
    regions = cfg.get("regions") or json.loads((d / "scenario.json").read_text())["regions"].keys()
    regions = list(regions)
    run = next(x for x in json.loads((d / "runs.json").read_text()) if x["resp"] == a.response and x["k"] == a.run)
    globe = {"regions": regions, "fail_hour": run["fail"], "hourly": run["wd_hourly_region"],
             "official": cfg.get("response_schedule", {}).get(a.response, [])}
    (d / "globe_run.json").write_text(json.dumps(globe))
    print(f"wrote {d / 'globe_run.json'} (fail hour: {run['fail']})")
    if not a.post:
        return
    key, accounts = os.environ["NESSIE_KEY"], json.loads(os.environ["NESSIE_ACCOUNTS"])
    for t, row in enumerate(run["wd_hourly_region"]):
        for r, share in zip(regions, row):
            if share > 0 and r in accounts:
                requests.post(f"{API}/accounts/{accounts[r]}/withdrawals", params={"key": key}, json={
                    "medium": "balance", "status": "completed", "amount": round(share * DEMO_DEPOSITS, 2),
                    "description": f"sim hour {t} {r}"}, timeout=10).raise_for_status()
        time.sleep(a.seconds_per_hour)


if __name__ == "__main__":
    main()
