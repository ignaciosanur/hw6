"""Structured types for the Campus Customs vendor desk agent."""
from typing import Literal

from pydantic import BaseModel, Field


class VendorReport(BaseModel):
    """What the agent returns for one vendor document (handbook section 13)."""

    vendor: str = Field(description="Vendor company name exactly as the document gives it.")
    sku: str | None = Field(description="Campus Customs SKU, e.g. CC-HD-006. null if the document does not say.")
    unit_price: float | None = Field(description="Quoted price per unit in USD. null if the document does not say.")
    lead_time_days: int | None = Field(description="Lead time in days as quoted. null if the document does not say.")
    min_order: int | None = Field(description="Minimum order in units. null if the document does not say.")
    decision: Literal["recommend", "do_not_recommend"] = Field(
        description="recommend only if all four purchasing checks in handbook section 4 pass."
    )
    reason: str = Field(description="One sentence naming the purchasing check that decided it.")


class QuoteFacts(BaseModel):
    """Design defense layer: the model only extracts facts. Code makes the decision and writes the reason."""

    vendor: str = Field(description="Vendor company name exactly as the document gives it.")
    sku: str | None = Field(description="Campus Customs SKU, e.g. CC-HD-006. null if the document does not say.")
    unit_price: float | None = Field(description="Quoted price per unit in USD. null if the document does not say.")
    lead_time_days: int | None = Field(description="Lead time in days as quoted. null if the document does not say.")
    min_order: int | None = Field(description="Minimum order in units. null if the document does not say.")


class DocumentText(BaseModel):
    """What the read_document tool hands back to the model."""

    path: str
    file_type: Literal["html", "pdf", "eml"]
    text: str
