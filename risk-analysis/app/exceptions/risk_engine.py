"""Exceptions raised by the Risk Engine."""


class RiskEngineError(Exception):
    """Base class for Risk Engine errors."""


class InvalidRiskWeightsError(RiskEngineError):
    """Raised when config/risk_rules.yaml weights are missing or invalid."""

    def __init__(self, detail: str):
        super().__init__(f"Invalid risk weights configuration: {detail}")


class MissingMetricError(RiskEngineError):
    """
    Raised when a risk rule needs a metric that the Metrics Engine did not
    produce (e.g. because its data source was in `missing_sources`). The
    Risk Engine catches this per-category and lowers that category's
    confidence rather than failing the whole report.
    """

    def __init__(self, metric_name: str, category: str):
        self.metric_name = metric_name
        self.category = category
        super().__init__(f"Metric '{metric_name}' unavailable for category '{category}'")
