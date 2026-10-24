"""Модели результата анализа (docs/05, docs/08 § 6). Поля совпадают с Pydantic-схемами API
(`app.schemas.analysis`): `app` превращает их в ответы через ``model_validate(asdict(...))``."""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.analysis.metrics import Metrics


@dataclass(slots=True)
class Contribution:
    node_id: str
    factor: str
    why: str


@dataclass(slots=True)
class ComplexityEstimate:
    current: str
    confidence: str  # exact | heuristic
    contributions: list[Contribution] = field(default_factory=list)
    after: str | None = None
    reason: str | None = None


@dataclass(slots=True)
class FindingLocation:
    file: str
    start_line: int
    end_line: int
    node_id: str | None = None
    method_id: str | None = None


@dataclass(slots=True)
class EvidenceItem:
    kind: str
    text: str
    node_id: str | None = None


@dataclass(slots=True)
class Evidence:
    static: list[EvidenceItem] = field(default_factory=list)
    dynamic: None = None


@dataclass(slots=True)
class Precondition:
    name: str
    passed: bool
    reason: str | None = None


@dataclass(slots=True)
class FixAvailability:
    fix_id: str  # OPT-02, FIX-01, …
    available: bool
    behavior_preserving: bool
    preconditions: list[Precondition] = field(default_factory=list)


@dataclass(slots=True)
class Finding:
    id: str
    rule_id: str
    severity: str  # high | medium | low
    category: str  # PERF | BUG | MAINT
    title: str
    location: FindingLocation
    explanation: str
    defect: str
    risk: str
    recommendation: str
    evidence: Evidence
    complexity: ComplexityEstimate | None = None
    fix: FixAvailability | None = None


@dataclass(slots=True)
class AnalysisSummary:
    total: int
    by_severity: dict[str, int]
    by_category: dict[str, int]
    fixable: int


@dataclass(slots=True)
class ComplexityPair:
    current: str
    optimized: str | None = None


@dataclass(slots=True)
class AnalysisResult:
    findings: list[Finding]
    summary: AnalysisSummary
    complexity: ComplexityPair
    metrics: Metrics
