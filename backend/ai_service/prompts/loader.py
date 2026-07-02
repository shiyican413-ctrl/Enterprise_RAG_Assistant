from functools import lru_cache
from pathlib import Path
from string import Template
from typing import Any


_PROMPT_DIR = Path(__file__).resolve().parent


@lru_cache(maxsize=32)
def _read_prompt(name: str) -> str:
    path = (_PROMPT_DIR / name).resolve()
    if _PROMPT_DIR not in path.parents:
        raise ValueError(f"Invalid prompt path: {name}")
    return path.read_text(encoding="utf-8")


def render_prompt(name: str, **variables: Any) -> str:
    values = {key: str(value) for key, value in variables.items()}
    return Template(_read_prompt(name)).safe_substitute(values)
