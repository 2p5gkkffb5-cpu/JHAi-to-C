import re
from collections.abc import Iterable
from pathlib import Path

PROMPT_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
DEFAULT_PROMPT_ROOT = Path(__file__).with_name("templates")


class InvalidPromptNameError(ValueError):
    """Raised when a prompt name is unsafe or malformed."""


class PromptNotFoundError(FileNotFoundError):
    """Raised when a named prompt resource does not exist."""


class EmptyPromptError(ValueError):
    """Raised when a prompt resource contains no usable text."""


def validate_prompt_name(prompt_name: str) -> str:
    if not PROMPT_NAME_PATTERN.fullmatch(prompt_name):
        raise InvalidPromptNameError(f"invalid prompt name: {prompt_name!r}")
    return prompt_name


class PromptLoader:
    """Load UTF-8 Markdown prompt resources by validated logical name."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or DEFAULT_PROMPT_ROOT).resolve()
        self._cache: dict[str, str] = {}

    def load(self, prompt_name: str) -> str:
        validate_prompt_name(prompt_name)

        if prompt_name in self._cache:
            return self._cache[prompt_name]

        prompt_path = self.root / f"{prompt_name}.md"
        try:
            prompt = prompt_path.read_text(encoding="utf-8").strip()
        except FileNotFoundError as exc:
            raise PromptNotFoundError(prompt_name) from exc

        if not prompt:
            raise EmptyPromptError(f"prompt is empty: {prompt_name}")

        self._cache[prompt_name] = prompt
        return prompt

    def load_many(self, prompt_names: Iterable[str]) -> dict[str, str]:
        return {prompt_name: self.load(prompt_name) for prompt_name in prompt_names}
