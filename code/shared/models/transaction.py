"""FR-2.1 transaction screening input schema. Validation failures must name
the offending field (FR-2.1 acceptance criteria), which pydantic gives us
for free via its structured ValidationError -> handled in
backend/app's exception handler into a named-field 400.
"""

from pydantic import BaseModel, Field, field_validator

from shared.enums import CustomerType, KycStatus, TransactionType


class TransactionPayload(BaseModel):
    transaction_id: str | None = None
    amount: float = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    counterparty: str
    counterparty_kyc_status: KycStatus = KycStatus.UNKNOWN
    jurisdictions: list[str] = Field(min_length=1)
    instrument_type: str
    customer_type: CustomerType
    transaction_type: TransactionType
    is_appropriateness_assessed: bool | None = None  # MiFID II, FR-2 scenario 3
    is_priority_sector: bool | None = None  # RBI, FR-2 scenario 4
    counterparty_jurisdiction_risk: str | None = None  # "high" | "standard" | None=unknown

    @field_validator("currency")
    @classmethod
    def currency_upper(cls, v: str) -> str:
        return v.upper()

    @field_validator("jurisdictions")
    @classmethod
    def jurisdictions_upper(cls, v: list[str]) -> list[str]:
        return [j.upper() for j in v]
