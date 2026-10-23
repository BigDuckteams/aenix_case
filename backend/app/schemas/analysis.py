"""Диагностика, Big O и метрики (docs/08-api.md § 6, docs/05-analysis.md)."""

from __future__ import annotations

from typing import Literal

from app.schemas.common import ApiModel, SourceRange

Severity = Literal["high", "medium", "low"]
Category = Literal["PERF", "BUG", "MAINT"]
Confidence = Literal["exact", "heuristic"]


class Contribution(ApiModel):
    """Из чего сложилась оценка: узел, множитель и причина."""

    node_id: str
    factor: str  # «n», «log n», «m»…
    why: str


class ComplexityEstimate(ApiModel):
    current: str  # «O(n²)»
    after: str | None = None
    confidence: Confidence
    contributions: list[Contribution]
    reason: str | None = None  # почему оценка эвристическая


class FindingLocation(ApiModel):
    file: str
    start_line: int
    end_line: int
    node_id: str | None = None
    method_id: str | None = None


class Precondition(ApiModel):
    name: str
    passed: bool
    reason: str | None = None


class FixAvailability(ApiModel):
    fix_id: str  # OPT-01, FIX-02, …
    available: bool
    behavior_preserving: bool
    preconditions: list[Precondition]


class EvidenceItem(ApiModel):
    kind: str  # «loop», «call», «collection», «literal»…
    text: str
    node_id: str | None = None


class DynamicSample(ApiModel):
    size: int
    time_ms: float
    hits: int | None = None


class DynamicEvidence(ApiModel):
    """Результат «Проверить»: прогон на размерах N, 2N, 4N, 8N."""

    run_id: int
    samples: list[DynamicSample]
    growth_k: float | None = None  # наклон в логарифмических координатах
    verdict: str | None = None  # «k ≈ 1.97 → ~O(n²)»


class Evidence(ApiModel):
    static: list[EvidenceItem]
    dynamic: DynamicEvidence | None = None


class Finding(ApiModel):
    id: str  # «PERF-01:Main.java#…/for[0]»
    rule_id: str
    severity: Severity
    category: Category
    title: str
    location: FindingLocation
    explanation: str
    defect: str
    risk: str
    recommendation: str
    complexity: ComplexityEstimate | None = None
    fix: FixAvailability | None = None
    evidence: Evidence


class AnalysisSummary(ApiModel):
    total: int
    by_severity: dict[str, int]
    by_category: dict[str, int]
    fixable: int


class MethodMetrics(ApiModel):
    method_id: str
    name: str
    file: str
    lines: int
    cyclomatic: int
    cognitive: int
    max_nesting: int
    params: int
    complexity: str | None = None


class TypeMetrics(ApiModel):
    type_id: str
    name: str
    file: str
    lines: int
    methods: int
    fields: int
    lcom4: float  # число компонент связности «методы — поля»


class MetricsTotals(ApiModel):
    lines: int
    code_lines: int
    files: int
    types: int
    methods: int
    cyclomatic_avg: float
    cyclomatic_max: int
    duplication_percent: float
    lcom4_avg: float


class Metrics(ApiModel):
    totals: MetricsTotals
    methods: list[MethodMetrics]
    types: list[TypeMetrics]


class MetricsResponse(ApiModel):
    version_id: int
    metrics: Metrics
    compare_to_version_id: int | None = None
    compare_to: Metrics | None = None  # метрики версии сравнения («до»)


class ComplexityPair(ApiModel):
    current: str
    optimized: str | None = None


class AnalysisResponse(ApiModel):
    version_id: int
    findings: list[Finding]
    summary: AnalysisSummary
    complexity: ComplexityPair  # итоговая сложность программы: сейчас и после оптимизаций
    metrics: Metrics


class FindingsResponse(ApiModel):
    version_id: int
    findings: list[Finding]


class ComplexityResponse(ApiModel):
    node_id: str | None = None
    range: SourceRange | None = None
    estimate: ComplexityEstimate
