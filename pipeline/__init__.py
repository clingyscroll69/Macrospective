"""Loads keys from the project's .env (never overrides variables already set in the shell)."""
import os, pathlib


def load_dotenv():
    p = pathlib.Path(__file__).resolve().parent.parent / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            k, sep, v = line.strip().partition("=")
            v = v.strip().strip('"').strip("'")
            # skip blanks: an empty ANTHROPIC_API_KEY would block the SDK's `ant auth login` fallback
            if sep and k and v and not k.startswith("#"):
                os.environ.setdefault(k.strip(), v)


load_dotenv()
