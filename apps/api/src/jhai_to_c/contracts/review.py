from enum import StrEnum

from pydantic import Field

from .common import ContractModel


class ReviewStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"


class IssueSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ReviewIssue(ContractModel):
    issue_id: str = Field(min_length=1, max_length=128)
    severity: IssueSeverity
    category: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=1000)
    node: str = Field(min_length=1, max_length=100)
    field_path: str | None = Field(default=None, max_length=300)
    suggested_fix: str = Field(default="", max_length=1000)


class ReviewerOutput(ContractModel):
    status: ReviewStatus
    score: int = Field(ge=0, le=100)
    issues: list[ReviewIssue] = Field(default_factory=list, max_length=50)
    return_to: str | None = Field(default=None, max_length=100)
    required_changes: list[str] = Field(default_factory=list, max_length=20)
