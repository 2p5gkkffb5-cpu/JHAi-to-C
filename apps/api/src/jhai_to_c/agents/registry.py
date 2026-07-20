from collections.abc import Iterable, Iterator

from .config import DEFAULT_AGENT_CONFIGS, AgentConfig, AgentName


class DuplicateAgentError(ValueError):
    """Raised when an agent identity is registered more than once."""


class UnknownAgentError(KeyError):
    """Raised when an agent identity is not registered."""


class AgentRegistry:
    """Explicit registry for immutable agent configuration."""

    def __init__(self, configs: Iterable[AgentConfig] = ()) -> None:
        self._configs: dict[AgentName, AgentConfig] = {}
        for config in configs:
            self.register(config)

    def register(self, config: AgentConfig) -> None:
        if config.name in self._configs:
            raise DuplicateAgentError(f"agent already registered: {config.name}")
        self._configs[config.name] = config

    def get(self, name: AgentName | str) -> AgentConfig:
        try:
            normalized_name = AgentName(name)
        except ValueError as exc:
            raise UnknownAgentError(str(name)) from exc

        try:
            return self._configs[normalized_name]
        except KeyError as exc:
            raise UnknownAgentError(normalized_name.value) from exc

    def __contains__(self, name: object) -> bool:
        try:
            normalized_name = AgentName(name)
        except (TypeError, ValueError):
            return False
        return normalized_name in self._configs

    def __iter__(self) -> Iterator[AgentConfig]:
        return iter(self._configs.values())

    def __len__(self) -> int:
        return len(self._configs)

    @property
    def names(self) -> tuple[AgentName, ...]:
        return tuple(self._configs)


def build_default_agent_registry() -> AgentRegistry:
    """Return a fresh registry so callers cannot mutate shared global state."""

    return AgentRegistry(DEFAULT_AGENT_CONFIGS)
