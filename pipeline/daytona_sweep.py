"""Monte Carlo sweep on Daytona: one sandbox per batch of ~50 runs, common seeds across responses.

    python -m pipeline.daytona_sweep data/<scenario> --runs 1000 --batch 50 [--local]

--local runs the exact same batches with a local process pool (no Daytona), useful to test the
orchestration. Results merge into <scenario>/runs.json, which condense.py turns into the evidence pack.

------------------------------------------------------------------------------------------------
DAYTONA INTEGRATION (docs: https://www.daytona.io/docs)
------------------------------------------------------------------------------------------------
SDK calls checked against the installed daytona package and run live (one 2-run batch).
  * pip install daytona ; export DAYTONA_API_KEY=...  (one key per account; you have 4 accounts)
  * Our org quota: 4 vCPU / 8 GiB RAM / 10 GiB disk in total, across all running sandboxes.
    Rate limits (50k req/min, 600 sandbox creations/min) are not the bottleneck; the quota is.
    So we run 4 sandboxes of 1 vCPU / 2 GiB / 2 GiB disk at once (engine.py is single-process).
  * Low tiers may restrict network access: bake numpy/scipy into the image; don't pip install at run time.
  * Cost at list price ~ $0.05/vCPU-h + ~$0.016/GiB-h; a 5 x 1000 bank sweep at N=4000 is ~2-3 vCPU-h.
  * Using several accounts: pass --api-keys k1,k2,k3,k4 and batches are spread round-robin across them;
    --max-parallel defaults to MAX_PARALLEL_PER_KEY x number of keys.
  * DAYTONA_API_KEY is read from the environment or from .env (see .env.example).
"""
import argparse, json, os, pathlib, subprocess, sys
from . import load_dotenv  # noqa: F401  (importing the package loads .env)
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parent.parent
FILES = ["engine.py"]
SCENARIO_FILES = ["network.npz", "scenario.json", "bank_config.json", "hour0_weights.json", "instigators.json",
                  "rumour_scores.json", "large_accounts.json", "large_accounts_v2.json"]
# Org quota: 4 vCPU, 8 GiB memory, 10 GiB storage shared by all live sandboxes.
CPU_PER_SANDBOX = 1
MEM_GIB_PER_SANDBOX = 2
DISK_GIB_PER_SANDBOX = 2
MAX_PARALLEL_PER_KEY = 4          # 4 x (1 vCPU, 2 GiB, 2 GiB) = 4 vCPU, 8 GiB, 8 GiB


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
    from daytona import Daytona, DaytonaConfig, CreateSandboxFromImageParams, Image, Resources
    daytona = Daytona(DaytonaConfig(api_key=api_key))
    image = Image.debian_slim("3.12").pip_install(["numpy==2.1.3", "scipy==1.15.3", "numba==0.68.0", "h3==4.5.0"])
    sb = daytona.create(CreateSandboxFromImageParams(image=image,
                        resources=Resources(cpu=CPU_PER_SANDBOX, memory=MEM_GIB_PER_SANDBOX,
                                            disk=DISK_GIB_PER_SANDBOX)), timeout=900)   # image build can exceed the 60 s default
    try:
        wd = sb.get_work_dir()
        sb.process.exec(f"mkdir -p {wd}/scn")
        sb.process.exec(f"mkdir -p {wd}/multiplex")
        sb.fs.upload_file((ROOT / "engine.py").read_bytes(), f"{wd}/engine.py")
        for f in (ROOT / "multiplex").glob("*.py"):      # v4 engine package
            sb.fs.upload_file(f.read_bytes(), f"{wd}/multiplex/{f.name}")
        for f in SCENARIO_FILES:
            if (d / f).exists():
                sb.fs.upload_file((d / f).read_bytes(), f"{wd}/scn/{f}")
        out = f"batch_{resp}_{a}.json"
        r = sb.process.exec(f"python engine.py {wd}/scn", cwd=wd, timeout=3600,
                            env={"RUN_KEYS": f"{a}:{b}", "RESPONSES": resp, "OUT_FILE": out})
        if r.exit_code != 0:
            raise RuntimeError(r.result)
        return json.loads(sb.fs.download_file(f"{wd}/scn/{out}"))
    finally:
        daytona.delete(sb)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario_dir"); ap.add_argument("--runs", type=int, default=1000)
    ap.add_argument("--batch", type=int, default=50); ap.add_argument("--local", action="store_true")
    ap.add_argument("--max-parallel", type=int, default=0, help="0 = MAX_PARALLEL_PER_KEY x keys")
    ap.add_argument("--api-keys", default=os.environ.get("DAYTONA_API_KEY", ""))
    ap.add_argument("--responses", default="")
    a = ap.parse_args()
    d = pathlib.Path(a.scenario_dir).resolve()
    sc = json.loads((d / "scenario.json").read_text())
    responses = a.responses.split(",") if a.responses else list(sc["responses"])
    keys = [k for k in a.api_keys.split(",") if k]
    if not a.local and not keys:
        sys.exit("No Daytona API key: set DAYTONA_API_KEY in .env or pass --api-keys")
    jobs = list(batches(responses, a.runs, a.batch))
    parallel = a.max_parallel or MAX_PARALLEL_PER_KEY * max(len(keys), 1)
    with ThreadPoolExecutor(1 if a.local else parallel) as pool:
        futs = [pool.submit(run_local, d, *j) if a.local else
                pool.submit(run_daytona, d, *j, keys[i % len(keys)]) for i, j in enumerate(jobs)]
        res = [x for f in futs for x in f.result()]
    (d / "runs.json").write_text(json.dumps(res))
    for f in d.glob("batch_*.json"):
        f.unlink()
    print(f"{len(res)} runs merged into {d / 'runs.json'}")


if __name__ == "__main__":
    main()
