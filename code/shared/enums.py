"""Controlled vocabularies shared across ingestion, retrieval, agent, and API layers.

Keeping these as enums (not free strings) is what makes RAG-3.3 payload
filtering and FR-2.2/AGENT-1.4 cross-framework matching reliable.
"""

from enum import Enum


class Framework(str, Enum):
    BASEL_III = "basel_iii"
    MIFID_II = "mifid_ii"
    RBI = "rbi"


class Jurisdiction(str, Enum):
    IN = "IN"
    EU = "EU"
    US = "US"
    GLOBAL = "GLOBAL"


class DocType(str, Enum):
    MASTER_DIRECTION = "master_direction"
    CIRCULAR = "circular"
    AMENDMENT = "amendment"
    DIRECTIVE = "directive"
    REGULATION = "regulation"


class RiskRating(str, Enum):
    """Ordering matters: FR-2.3 / AGENT-1.5 compare ratings by severity."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @property
    def severity(self) -> int:
        return {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}[self.value]

    @classmethod
    def max(cls, *ratings: "RiskRating") -> "RiskRating":
        return max(ratings, key=lambda r: r.severity)


class CustomerType(str, Enum):
    RETAIL = "retail"
    INSTITUTIONAL = "institutional"
    INTRA_GROUP = "intra_group"


class TransactionType(str, Enum):
    CROSS_BORDER_PAYMENT = "cross_border_payment"
    DERIVATIVE_TRADE = "derivative_trade"
    INVESTMENT = "investment"
    LENDING = "lending"


class KycStatus(str, Enum):
    VERIFIED = "verified"
    PENDING = "pending"
    NOT_VERIFIED = "not_verified"
    UNKNOWN = "unknown"


class QueryIntent(str, Enum):
    """LLM-2.1 router-tier classification output."""

    QA = "qa"
    TRANSACTION_SCREENING = "transaction_screening"
    REPORT_GENERATION = "report_generation"
    OFF_TOPIC = "off_topic"


class UserRole(str, Enum):
    """SEC-2.2 RBAC roles."""

    COMPLIANCE_OFFICER = "compliance_officer"
    COMPLIANCE_HEAD = "compliance_head"
    INTERNAL_AUDITOR = "internal_auditor"
    PLATFORM_ADMIN = "platform_admin"


class AssessmentStatus(str, Enum):
    COMPLETED = "completed"
    NEEDS_REVIEW = "needs_review"  # AGENT-2.4 human-in-the-loop interrupt
    DEGRADED = "degraded"  # AGENT-3.1 / AGENT-3.4
