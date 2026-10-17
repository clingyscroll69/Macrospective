"""Single entry point for every LLM call made BEFORE the runs (plan: "Chalk thinks before the runs").

Every pre-run call goes through `complete_json()`: hour-0 weights, instigator casts, rumour scoring
and large-account playbooks. Two backends:

  LLM_BACKEND=chalk      -> Chalk P.completion (cached per (prompt, input) pair, logged for backtests)
  LLM_BACKEND=anthropic  -> Anthropic Messages API directly (default; what this repo was tested with,
                            via Sonnet subagents)

The engine never calls an LLM. Everything written here is frozen to JSON before the Daytona sweep.

------------------------------------------------------------------------------------------------
CHALK INTEGRATION (TODO: fill in from https://docs.chalk.ai/docs/chalk-for-ai-engineers)
------------------------------------------------------------------------------------------------
I could not verify Chalk's Python signatures, so `_chalk_complete` is a marked stub. What it must do:
  1. Store region facts and company-type settings as Chalk features (plan §"Hour 0": region facts come
     from data, never from an LLM). Pass them in as `inputs`, not pasted into the prompt by hand.
  2. Call P.completion with the prompt template + inputs + a JSON output schema.
  3. Cache on (template_name, sha256(inputs)) so each (rumour, region) pair is scored once and reused.
  4. Log prompt version + model per call, so backtests can attribute error to prompt/model versions.
Ask at the Chalk table for hackathon access; the plan notes it blocks other work.
"""
import hashlib, json, os, pathlib
import anthropic

MODEL = os.environ.get("LLM_MODEL", "claude-sonnet-5-5")   # the runs in results/ used Sonnet
CACHE_DIR = pathlib.Path(os.environ.get("LLM_CACHE_DIR", ".llm_cache"))
_client = None


def _cache_key(template: str, inputs: dict, sample: int) -> str:
    blob = json.dumps({"t": template, "i": inputs, "s": sample}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:24]


def _anthropic_complete(system: str, user: str, max_tokens: int) -> str:
    global _client
    _client = _client or anthropic.Anthropic()          # credentials from env / `ant auth login`
    # Streaming because playbooks (27 agents x 36 states) produce long JSON.
    # Server-side fallback ("default" form) re-runs a refused request on another model.
    with _client.beta.messages.stream(
        model=MODEL,
        max_tokens=max_tokens,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "medium"},
        system=system,
        messages=[{"role": "user", "content": user}],
    ) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason == "refusal":
        raise RuntimeError(f"LLM refused: {msg.stop_details}")
    if msg.stop_reason == "max_tokens":
        raise RuntimeError("LLM output truncated; raise max_tokens")
    return "".join(b.text for b in msg.content if b.type == "text")


def _chalk_complete(template_name: str, system: str, user: str, inputs: dict, max_tokens: int) -> str:
    # TODO(Chalk): replace with P.completion(...) per Chalk docs. Keep the same return contract:
    # the raw model text, which must contain one JSON object.
    raise NotImplementedError("Wire Chalk P.completion here (see module docstring).")


def _extract_json(text: str):
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1])


def complete_json(template_name: str, system: str, user: str, inputs: dict,
                  sample: int = 0, max_tokens: int = 64000):
    """Return parsed JSON from one LLM call. `sample` separates independent samples (plan: 3-5 per region)."""
    CACHE_DIR.mkdir(exist_ok=True)
    path = CACHE_DIR / f"{template_name}_{_cache_key(template_name, inputs, sample)}.json"
    if path.exists():
        return json.loads(path.read_text())
    backend = os.environ.get("LLM_BACKEND", "anthropic")
    text = (_chalk_complete(template_name, system, user, inputs, max_tokens) if backend == "chalk"
            else _anthropic_complete(system, user, max_tokens))
    out = _extract_json(text)
    path.write_text(json.dumps(out))
    return out
