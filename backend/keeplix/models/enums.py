"""枚举常量。引擎 id 约定见 docs/glossary.md。"""

from __future__ import annotations

from enum import StrEnum


class Acquisition(StrEnum):
    """引擎数据获取方式。"""

    api = "api"
    browser = "browser"
    stub = "stub"


class ProjectStatus(StrEnum):
    active = "active"
    paused = "paused"
    archived = "archived"


class PromptIntent(StrEnum):
    branded = "branded"
    category = "category"
    problem = "problem"
    comparison = "comparison"


class RunStatus(StrEnum):
    pending = "pending"
    running = "running"
    done = "done"
    partial = "partial"
    failed = "failed"


class Severity(StrEnum):
    high = "high"
    medium = "medium"
    low = "low"


class Sentiment(StrEnum):
    positive = "positive"
    neutral = "neutral"
    negative = "negative"


class DeliverableKind(StrEnum):
    audit_report = "audit_report"
    sov_report = "sov_report"
    content_plan = "content_plan"
