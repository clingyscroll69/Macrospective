"""Monte Carlo sweep on Daytona: one sandbox per batch of ~50 runs, common seeds across responses.

    python -m pipeline.daytona_sweep data/<scenario> --runs 1000 --batch 50 [--local]

--local runs the exact same batches with a local process pool (no Daytona), useful to test the
orchestration. Results merge into <scenario>/runs.json, which condense.py turns into the evidence pack.

------------------------------------------------------------------------------------------------
DAYTONA INTEGRATION: verify every SDK call against https://www.daytona.io/docs before the demo.
------------------------------------------------------------------------------------------------
I wrote the SDK calls from memory and did not run them against Daytona. Each one is marked VERIFY.
  * pip install daytona ; export DAYTONA_API_KEY=...  (one key per account; you have 4 accounts)
  * Tier limits are per organisation pool: Tier 1 = 10 vCPU, Tier 2 = 100 vCPU, Tier 3 = 250 vCPU.
    Size MAX_PARALLEL so (sandboxes x cpu per sandbox) stays under your tier's pool.
  * Low tiers may restrict network access: bake numpy/scipy into the image; don't pip install at run time.
  * Cost at list price ~ $0.05/vCPU-h + ~$0.016/GiB-h; a 5 x 1000 bank sweep at N=4000 is ~2-3 vCPU-h.
  * Using several accounts: pass --api-keys k1,k2,k3,k4 and batches are spread round-robin across them.
    At today's size one Tier-2 account is already limited by sandbox start-up, so this only helps
    once you raise N or run 30-day horizons.
"""
import argparse, json, os, pathlib, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parent.parent
FILES = ["engine.py"]
SCENARIO_FILES = ["scenario.json", "bank_config.json", "hour0_weights.json", "instigators.json",
                  "rumour_scores.json", "large_accounts.json", "large_accounts_v2.json"]
CPU_PER_SANDBOX = 4


def batches(responses, runs, size):
    for r in responses:
        for a in range(0, runs, size):
            yield r, a, min(a + size, runs)


def run_local(d, resp, a, b):
    out = f"batch_{resp}_{a}.json"
    env = dict(os.environ, RUN_KEYS=f"{a}:{b}", RESPONSES=resp, OUT_FILE=out)
    subprocess.run([sys.executable, str(ROOT / "engine.py"), str(d)], env=env, check=True, capture_output=True)
    return json.loads((d / out).read_text())


def run_daytona(d, resp, a, b, api_key):
    # VERIFY: names below follow the Daytona Python SDK as I remember it.
    from daytona import Daytona, DaytonaConfig, CreateSandboxFromImageParams, Image, Resources
    daytona = Daytona(DaytonaConfig(api_key=api_key))
    image = Image.debian_slim("3.12").pip_install(["numpy==2.1.3", "scipy==1.15.3"])     # VERIFY
    sb = daytona.create(CreateSandboxFromImageParams(image=image,
                        resources=Resources(cpu=CPU_PER_SANDBOX, memory=8)))           # VERIFY
    try:
        sb.fs.upload_file((ROOT / "engine.py").read_bytes(), "/work/engine.py")         # VERIFY
        for f in SCENARIO_FILES:
            if (d / f).exists():
                sb.fs.upload_file((d / f).read_bytes(), f"/work/scn/{f}")
        out = f"batch_{resp}_{a}.json"
        r = sb.process.exec(f"cd /work && RUN_KEYS={a}:{b} RESPONSES={resp} OUT_FILE={out} "
                            f"python engine.py /work/scn", timeout=3600)                 # VERIFY
        if r.exit_code != 0:
            raise RuntimeError(r.result)
        return json.loads(sb.fs.download_file(f"/work/scn/{out}"))                        # VERIFY
    finally:
        daytona.delete(sb)                                                                # VERIFY


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario_dir"); ap.add_argument("--runs", type=int, default=1000)
    ap.add_argument("--batch", type=int, default=50); ap.add_argument("--local", action="store_true")
    ap.add_argument("--max-parallel", type=int, default=24)
    ap.add_argument("--api-keys", default=os.environ.get("DAYTONA_API_KEY", ""))
    ap.add_argument("--responses", default="")
    a = ap.parse_args()
    d = pathlib.Path(a.scenario_dir).resolve()
    sc = json.loads((d / "scenario.json").read_text())
    responses = a.responses.split(",") if a.responses else list(sc["responses"])
    keys = [k for k in a.api_keys.split(",") if k]
    jobs = list(batches(responses, a.runs, a.batch))
    with ThreadPoolExecutor(1 if a.local else a.max_parallel) as pool:
        futs = [pool.submit(run_local, d, *j) if a.local else
                pool.submit(run_daytona, d, *j, keys[i % len(keys)]) for i, j in enumerate(jobs)]
        res = [x for f in futs for x in f.result()]
    (d / "runs.json").write_text(json.dumps(res))
    for f in d.glob("batch_*.json"):
        f.unlink()
    print(f"{len(res)} runs merged into {d / 'runs.json'}")


if __name__ == "__main__":
    main()
