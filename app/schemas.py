from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class VendorCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    tax_id: str | None = Field(default=None, max_length=30)


class VendorOut(VendorCreate):
    id: int


class OrderLine(BaseModel):
    sku: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=300)
    quantity: float = Field(gt=0)
    unit_price: float = Field(ge=0)


class PurchaseOrderCreate(BaseModel):
    po_number: str = Field(min_length=1, max_length=50)
    vendor_id: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    lines: list[OrderLine] = Field(min_length=1, max_length=500)

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()


class ReceiptLine(BaseModel):
    sku: str = Field(min_length=1, max_length=80)
    quantity: float = Field(gt=0)


class ReceiptCreate(BaseModel):
    purchase_order_id: int = Field(gt=0)
    received_at: datetime
    reference: str = Field(min_length=1, max_length=80)
    lines: list[ReceiptLine] = Field(min_length=1, max_length=500)


class InvoiceLine(BaseModel):
    sku: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=300)
    quantity: float = Field(gt=0)
    unit_price: float = Field(ge=0)


class InvoiceCreate(BaseModel):
    invoice_number: str = Field(min_length=1, max_length=80)
    vendor_id: int = Field(gt=0)
    purchase_order_id: int | None = Field(default=None, gt=0)
    currency: str = Field(min_length=3, max_length=3)
    invoice_date: date
    lines: list[InvoiceLine] = Field(min_length=1, max_length=500)

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()


class ReconciliationResult(BaseModel):
    invoice_id: int
    status: Literal["matched", "exception"]
    exceptions: list[dict[str, str]]
    checks: dict[str, bool]


class ExceptionOut(BaseModel):
    id: int
    invoice_id: int
    code: str
    severity: str
    message: str
    resolved: bool


class HealthOut(BaseModel):
    status: str
    service: str
