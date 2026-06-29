from __future__ import annotations

from dataclasses import dataclass, field

from leadpilot.core.enums import GuardrailType


@dataclass(slots=True)
class GuardrailResult:
    ok: bool
    type: GuardrailType
    severity: str = "INFO"
    detail: dict = field(default_factory=dict)
    action_taken: str | None = None

    @classmethod
    def passed(cls, gtype: GuardrailType) -> GuardrailResult:
        return cls(ok=True, type=gtype)

    @classmethod
    def blocked(
        cls, gtype: GuardrailType, *, reason: str, severity: str = "WARN", action: str = "BLOCKED"
    ) -> GuardrailResult:
        return cls(ok=False, type=gtype, severity=severity,
                   detail={"reason": reason}, action_taken=action)
