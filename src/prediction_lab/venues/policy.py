from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExecutionPolicy:
    terms_allow: bool = False
    jurisdiction_verified: bool = False
    adapter_tested: bool = False
    user_enabled: bool = False

    @property
    def blockers(self) -> tuple[str, ...]:
        gates = (
            ("terms", self.terms_allow),
            ("jurisdiction", self.jurisdiction_verified),
            ("adapter", self.adapter_tested),
            ("user", self.user_enabled),
        )
        return tuple(name for name, enabled in gates if not enabled)

    @property
    def can_execute(self) -> bool:
        return not self.blockers


@dataclass(frozen=True)
class VenueCandidate:
    venue_id: str
    operator: str
    role: str
    chains: tuple[int, ...]
    terms_url: str
    execution_policy: ExecutionPolicy = field(default_factory=ExecutionPolicy)
