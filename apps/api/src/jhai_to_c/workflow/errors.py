class InvalidReferenceSubsetError(ValueError):
    code = "invalid_reference_subset"

    def __init__(
        self,
        *,
        internal_agent: str,
        invalid_ids: list[str],
        duplicate_ids: list[str],
        allowed_ids: list[str],
    ) -> None:
        self.details = {
            "internal_agent": internal_agent,
            "invalid_ids": invalid_ids,
            "duplicate_ids": duplicate_ids,
            "allowed_ids": allowed_ids,
        }
        super().__init__(self.code)


class CapabilityUnavailableError(RuntimeError):
    code = "capability_unavailable"

    def __init__(self, capability: str) -> None:
        self.capability = capability
        self.details = {"capability": capability}
        super().__init__(f"{capability} capability is not available")
