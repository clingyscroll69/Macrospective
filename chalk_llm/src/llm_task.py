"""Every pre-run LLM call in the contagion simulator runs as this one Chalk feature.

The caller (pipeline/llm.py) queries it with the task id, system text and prompt; Chalk runs
P.completion on its servers with the ANTHROPIC_API_KEY secret and returns the raw text.
"""
import chalk.functions as F
import chalk.prompts as P
from chalk.features import _, features


@features
class LlmTask:
    id: str                       # template name + hash of inputs + sample index (cache key)
    template: str                 # hour0 | instigators | score | playbooks
    system: str
    prompt: str
    result: P.PromptResponse = P.completion(
        model="claude-sonnet-5-5",
        model_provider="anthropic",
        messages=[
            P.message(role="system", content=F.jinja("{{LlmTask.system}}")),
            P.message(role="user", content=F.jinja("{{LlmTask.prompt}}")),
        ],
        max_tokens=64000,
        timeout_seconds=900,
        num_retries=2,
    )
    text: str = _.result.response
