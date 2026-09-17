from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from app.db import connect, initialize
from app.schemas import InvoiceCreate, InvoiceLine, PurchaseOrderCreate, OrderLine, ReceiptCreate, ReceiptLine
from app.services import create_invoice, create_purchase_order, create_receipt, create_vendor, reconcile_invoice


def connection(tmp_path: Path):
    path = str(tmp_path / "test.sqlite3")
    initialize(path)
    return connect(path)


def test_three_way_match_passes(tmp_path: Path) -> None:
    db = connection(tmp_path)
    vendor = create_vendor(db, "Acme Components", "GST-123")
    po = create_purchase_order(
        db,
        PurchaseOrderCreate(
            po_number="PO-100",
            vendor_id=vendor,
            currency="INR",
            lines=[OrderLine(sku="A-1", description="Widget", quantity=10, unit_price=100)],
        ),
    )
    create_receipt(
        db,
        ReceiptCreate(
            purchase_order_id=po,
            received_at=datetime(2026, 9, 17, tzinfo=timezone.utc),
            reference="GRN-1",
            lines=[ReceiptLine(sku="A-1", quantity=10)],
        ),
    )
    invoice = create_invoice(
        db,
        InvoiceCreate(
            invoice_number="INV-1",
            vendor_id=vendor,
            purchase_order_id=po,
            currency="INR",
            invoice_date=date(2026, 9, 17),
            lines=[InvoiceLine(sku="A-1", description="Widget", quantity=10, unit_price=100)],
        ),
    )
    status, exceptions, checks = reconcile_invoice(db, invoice)
    assert status == "matched"
    assert exceptions == []
    assert all(checks.values())


def test_quantity_overage_creates_exception(tmp_path: Path) -> None:
    db = connection(tmp_path)
    vendor = create_vendor(db, "Acme Components", None)
    po = create_purchase_order(
        db,
        PurchaseOrderCreate(
            po_number="PO-101", vendor_id=vendor, currency="INR",
            lines=[OrderLine(sku="A-1", description="Widget", quantity=5, unit_price=100)],
        ),
    )
    create_receipt(
        db,
        ReceiptCreate(
            purchase_order_id=po,
            received_at=datetime(2026, 9, 17, tzinfo=timezone.utc),
            reference="GRN-2", lines=[ReceiptLine(sku="A-1", quantity=5)],
        ),
    )
    invoice = create_invoice(
        db,
        InvoiceCreate(
            invoice_number="INV-2", vendor_id=vendor, purchase_order_id=po, currency="INR",
            invoice_date=date(2026, 9, 17),
            lines=[InvoiceLine(sku="A-1", description="Widget", quantity=6, unit_price=100)],
        ),
    )
    status, exceptions, checks = reconcile_invoice(db, invoice)
    assert status == "exception"
    assert "quantity_over_po" in {item.code for item in exceptions}
    assert checks["quantity"] is False


def test_duplicate_invoice_fingerprint_is_rejected(tmp_path: Path) -> None:
    db = connection(tmp_path)
    vendor = create_vendor(db, "Acme Components", None)
    payload = InvoiceCreate(
        invoice_number="INV-DUP", vendor_id=vendor, currency="INR", invoice_date=date(2026, 9, 17),
        lines=[InvoiceLine(sku="A-1", description="Widget", quantity=1, unit_price=100)],
    )
    create_invoice(db, payload)
    try:
        create_invoice(db, payload)
    except ValueError as exc:
        assert str(exc) == "duplicate_invoice"
    else:
        raise AssertionError("duplicate invoice was accepted")
