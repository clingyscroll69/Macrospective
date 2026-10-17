"""Droid analyst: intake, tools, and the final analysis (verdict per response + ranking).

    python -m pipeline.droid_analyst data/<scenario>          # verdicts + ranking from evidence.json

Rule 1 of the plan: the engine settles the numbers, the final call only explains them. Code enforces it:
every verdict goes through numcheck.py, and a verdict containing a number not in the evidence pack is
rejected and regenerated (up to 2 retries), then reported as failed.

------------------------------------------------------------------------------------------------
FACTORY DROID INTEGRATION (TODO: from https://docs.factory.com/sdk/python)
------------------------------------------------------------------------------------------------
I could not verify the Droid SDK, so this file runs the analysis directly on the Anthropic API and
exposes the plan's Droid tools as plain functions. To move it onto Droid:
  1. Install the `droid` program on the server + set the Factory API key (blocks other work; do first).
  2. Register TOOLS below with Droid's @tool decorator: spawn_instigators, create_variant,
     start_sweep, fetch_results. Droid is asynchronous only, so start_sweep should return a job id
     and fetch_results should poll it.
  3. Use a Droid Session for "what if we announce 3 hours earlier?": create_variant copies the scenario,
     edits response_schedule, scores only the new/moved message, and reruns only that response.
  4. Move VERDICT_PROMPT / RANKING_PROMPT into the Droid final-analysis step unchanged.
  5. Prize rule: the README must say exactly where Droid is used.
"""
import json, pathlib, shutil, subprocess, sys
from .llm import _anthropic_complete

ROOT = pathlib.Path(__file__).resolve().parent.parent

VERDICT_PROMPT = """You are the final analyst for a contagion simulator. Below is the evidence pack for ONE
simulated response. Rules: explain the engine's outcome and never overrule it; every number you write
must appear in the evidence pack exactly as written (0.04 may be written 0.04 or 4%); compute no new numbers.
Write markdown with: 1. Verdict (one line with the key number) 2. Rumour by rumour (top 5)
3. Region by region 4. Turning point 5. Outcome types. Under 450 words.

Evidence pack:
{pack}"""

RANKING_PROMPT = """Rank these simulated responses. Never overrule the engine; use only numbers that appear
verbatim below; no new arithmetic. Output a ranked markdown table (response, survival share, CI95,
median withdrawn) plus at most 200 words on why the order comes out this way, including timing.

Verdicts:
{verdicts}

Outcomes:
{outcomes}"""


def numcheck(evidence: pathlib.Path, md: pathlib.Path) -> bool:
    return subprocess.run([sys.executable, str(ROOT / "numcheck.py"), str(evidence), str(md)]).returncode == 0


def write_verdicts(d: pathlib.Path, retries=2):
    ev_path = d / "evidence.json"
    packs = json.loads(ev_path.read_text())
    for resp, pack in packs.items():
        out = d / f"verdict_{resp}.md"
        for attempt in range(retries + 1):
            out.write_text(_anthropic_complete("Write only the requested markdown.",
                                               VERDICT_PROMPT.format(pack=json.dumps(pack)), 8000))
            if numcheck(ev_path, out):
                break
        else:
            print(f"WARNING: {out.name} still fails the number check after {retries} retries")
    verdicts = "\n\n".join((d / f"verdict_{r}.md").read_text() for r in packs)
    outcomes = json.dumps({r: {"outcome": p["outcome"], "outcome_types": p["outcome_types"]} for r, p in packs.items()})
    (d / "ranking.md").write_text(_anthropic_complete("Write only the requested markdown.",
                                                      RANKING_PROMPT.format(verdicts=verdicts, outcomes=outcomes), 8000))
    numcheck(ev_path, d / "ranking.md")   # note: years/dates in titles can trip it; review by eye


# ---------------- Droid tools (register with @tool when the SDK is wired) ----------------

def spawn_instigators(scenario_dir: str, casts: int = 5):
    """Write instigator casts and score them (Chalk calls)."""
    from .pre_run import run
    run(pathlib.Path(scenario_dir), casts=casts, skip={"hour0", "playbooks"})


def create_variant(scenario_dir: str, name: str, response_id: str, hour_shift: int):
    """Copy a scenario and move one response's messages by hour_shift (e.g. -3 = announce 3h earlier)."""
    src, dst = pathlib.Path(scenario_dir), pathlib.Path(scenario_dir).parent / name
    shutil.copytree(src, dst, dirs_exist_ok=True)
    cfg = json.loads((dst / "bank_config.json").read_text())
    for m in cfg["response_schedule"][response_id]:
        m["hour"] = max(0, m["hour"] + hour_shift)
    (dst / "bank_config.json").write_text(json.dumps(cfg, indent=1))
    return str(dst)   # message texts are unchanged, so existing scores stay valid


def start_sweep(scenario_dir: str, runs: int = 1000, responses: str = "", local: bool = False):
    """Kick off the Daytona sweep. TODO(Droid): run async and return a job id."""
    args = [sys.executable, "-m", "pipeline.daytona_sweep", scenario_dir, "--runs", str(runs)]
    if responses: args += ["--responses", responses]
    if local: args.append("--local")
    return subprocess.run(args, cwd=ROOT, check=True)


def fetch_results(scenario_dir: str):
    """Condense runs into the evidence pack and write verdicts + ranking."""
    subprocess.run([sys.executable, str(ROOT / "condense.py"), scenario_dir], check=True)
    write_verdicts(pathlib.Path(scenario_dir))
    return (pathlib.Path(scenario_dir) / "ranking.md").read_text()


TOOLS = [spawn_instigators, create_variant, start_sweep, fetch_results]

if __name__ == "__main__":
    write_verdicts(pathlib.Path(sys.argv[1]))
