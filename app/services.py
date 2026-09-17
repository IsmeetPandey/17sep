from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from app.schemas import InvoiceCreate, PurchaseOrderCreate, ReceiptCreate


@dataclass(frozen=True, slots=True)
class ExceptionItem:
    code: str
    severity: str
    message: str


def money(value: float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def fingerprint(invoice: InvoiceCreate) -> str:
    canonical = {
        "invoice_number": invoice.invoice_number.strip().casefold(),
        "vendor_id": invoice.vendor_id,
        "currency": invoice.currency,
        "date": invoice.invoice_date.isoformat(),
        "lines": sorted(
            [
                {
                    "sku": line.sku.strip().casefold(),
                    "quantity": str(line.quantity),
                    "unit_price": str(line.unit_price),
                }
                for line in invoice.lines
            ],
            key=lambda item: (item["sku"], item["quantity"], item["unit_price"]),
        ),
    }
    return hashlib.sha256(json.dumps(canonical, sort_keys=True).encode("utf-8")).hexdigest()


def create_vendor(connection: sqlite3.Connection, name: str, tax_id: str | None) -> int:
    cursor = connection.execute(
        "INSERT INTO vendors(name, tax_id) VALUES (?, ?)", (name.strip(), tax_id)
    )
    connection.commit()
    return int(cursor.lastrowid)


def create_purchase_order(connection: sqlite3.Connection, order: PurchaseOrderCreate) -> int:
    vendor = connection.execute("SELECT id FROM vendors WHERE id = ?", (order.vendor_id,)).fetchone()
    if vendor is None:
        raise ValueError("vendor_not_found")
    try:
        with connection:
            cursor = connection.execute(
                "INSERT INTO purchase_orders(po_number, vendor_id, currency) VALUES (?, ?, ?)",
                (order.po_number.strip(), order.vendor_id, order.currency),
            )
            order_id = int(cursor.lastrowid)
            connection.executemany(
                "INSERT INTO purchase_order_lines(purchase_order_id, sku, description, quantity, unit_price) VALUES (?, ?, ?, ?, ?)",
                [
                    (order_id, line.sku.strip(), line.description.strip(), line.quantity, line.unit_price)
                    for line in order.lines
                ],
            )
            connection.execute(
                "INSERT INTO audit_events(entity_type, entity_id, action, details) VALUES (?, ?, ?, ?)",
                ("purchase_order", order_id, "created", json.dumps({"po_number": order.po_number})),
            )
            return order_id
    except sqlite3.IntegrityError as exc:
        raise ValueError("purchase_order_already_exists") from exc


def create_receipt(connection: sqlite3.Connection, receipt: ReceiptCreate) -> int:
    order = connection.execute(
        "SELECT id FROM purchase_orders WHERE id = ?", (receipt.purchase_order_id,)
    ).fetchone()
    if order is None:
        raise ValueError("purchase_order_not_found")
    try:
        with connection:
            cursor = connection.execute(
                "INSERT INTO receipts(purchase_order_id, received_at, reference) VALUES (?, ?, ?)",
                (receipt.purchase_order_id, receipt.received_at.isoformat(), receipt.reference.strip()),
            )
            receipt_id = int(cursor.lastrowid)
            connection.executemany(
                "INSERT INTO receipt_lines(receipt_id, sku, quantity) VALUES (?, ?, ?)",
                [(receipt_id, line.sku.strip(), line.quantity) for line in receipt.lines],
            )
            connection.execute(
                "INSERT INTO audit_events(entity_type, entity_id, action, details) VALUES (?, ?, ?, ?)",
                ("receipt", receipt_id, "created", json.dumps({"reference": receipt.reference})),
            )
            return receipt_id
    except sqlite3.IntegrityError as exc:
        raise ValueError("receipt_reference_already_exists") from exc


def create_invoice(connection: sqlite3.Connection, invoice: InvoiceCreate) -> int:
    vendor = connection.execute("SELECT id FROM vendors WHERE id = ?", (invoice.vendor_id,)).fetchone()
    if vendor is None:
        raise ValueError("vendor_not_found")
    if invoice.purchase_order_id is not None:
        order = connection.execute(
            "SELECT id, vendor_id, currency FROM purchase_orders WHERE id = ?",
            (invoice.purchase_order_id,),
        ).fetchone()
        if order is None:
            raise ValueError("purchase_order_not_found")
        if order["vendor_id"] != invoice.vendor_id:
            raise ValueError("purchase_order_vendor_mismatch")
        if order["currency"] != invoice.currency:
            raise ValueError("purchase_order_currency_mismatch")

    total = sum((money(line.quantity) * money(line.unit_price) for line in invoice.lines), Decimal("0"))
    digest = fingerprint(invoice)
    try:
        with connection:
            cursor = connection.execute(
                "INSERT INTO invoices(invoice_number, vendor_id, purchase_order_id, currency, invoice_date, total, fingerprint) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    invoice.invoice_number.strip(), invoice.vendor_id, invoice.purchase_order_id,
                    invoice.currency, invoice.invoice_date.isoformat(), float(total), digest,
                ),
            )
            invoice_id = int(cursor.lastrowid)
            connection.executemany(
                "INSERT INTO invoice_lines(invoice_id, sku, description, quantity, unit_price) VALUES (?, ?, ?, ?, ?)",
                [
                    (invoice_id, line.sku.strip(), line.description.strip(), line.quantity, line.unit_price)
                    for line in invoice.lines
                ],
            )
            connection.execute(
                "INSERT INTO audit_events(entity_type, entity_id, action, details) VALUES (?, ?, ?, ?)",
                ("invoice", invoice_id, "created", json.dumps({"invoice_number": invoice.invoice_number})),
            )
            return invoice_id
    except sqlite3.IntegrityError as exc:
        raise ValueError("duplicate_invoice") from exc


def _line_totals(connection: sqlite3.Connection, table: str, key: str, key_value: int) -> dict[str, float]:
    rows = connection.execute(
        f"SELECT sku, quantity FROM {table} WHERE {key} = ?", (key_value,)
    ).fetchall()
    totals: dict[str, float] = defaultdict(float)
    for row in rows:
        totals[row["sku"]] += float(row["quantity"])
    return dict(totals)


def reconcile_invoice(
    connection: sqlite3.Connection,
    invoice_id: int,
    price_tolerance_pct: float = 2.0,
) -> tuple[str, list[ExceptionItem], dict[str, bool]]:
    invoice = connection.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if invoice is None:
        raise ValueError("invoice_not_found")

    exceptions: list[ExceptionItem] = []
    checks = {"vendor": True, "purchase_order": False, "quantity": False, "price": False, "receipt": False}
    po_id = invoice["purchase_order_id"]
    if po_id is None:
        exceptions.append(ExceptionItem("missing_purchase_order", "high", "Invoice has no purchase order reference."))
    else:
        po = connection.execute("SELECT * FROM purchase_orders WHERE id = ?", (po_id,)).fetchone()
        if po is None:
            exceptions.append(ExceptionItem("purchase_order_not_found", "high", "Referenced purchase order does not exist."))
        else:
            checks["purchase_order"] = True
            if po["vendor_id"] != invoice["vendor_id"]:
                checks["vendor"] = False
                exceptions.append(ExceptionItem("vendor_mismatch", "high", "Invoice vendor does not match the purchase order."))
            invoice_lines = connection.execute(
                "SELECT sku, quantity, unit_price FROM invoice_lines WHERE invoice_id = ?", (invoice_id,)
            ).fetchall()
            po_lines = connection.execute(
                "SELECT sku, quantity, unit_price FROM purchase_order_lines WHERE purchase_order_id = ?", (po_id,)
            ).fetchall()
            po_by_sku = {row["sku"]: row for row in po_lines}
            quantity_ok = True
            price_ok = True
            for line in invoice_lines:
                reference = po_by_sku.get(line["sku"])
                if reference is None or float(line["quantity"]) > float(reference["quantity"]) + 1e-9:
                    quantity_ok = False
                    exceptions.append(ExceptionItem("quantity_over_po", "high", f"SKU {line['sku']} exceeds ordered quantity."))
                    continue
                reference_price = money(reference["unit_price"])
                actual_price = money(line["unit_price"])
                if reference_price == 0:
                    price_delta_pct = 0 if actual_price == 0 else 100
                else:
                    price_delta_pct = abs(actual_price - reference_price) / reference_price * 100
                if price_delta_pct > Decimal(str(price_tolerance_pct)):
                    price_ok = False
                    exceptions.append(ExceptionItem("price_variance", "medium", f"SKU {line['sku']} exceeds the configured price tolerance."))
            checks["quantity"] = quantity_ok
            checks["price"] = price_ok
            received = _line_totals(connection, "receipt_lines", "receipt_id", po_id) if False else {}
            receipt_ids = connection.execute("SELECT id FROM receipts WHERE purchase_order_id = ?", (po_id,)).fetchall()
            received = defaultdict(float)
            for receipt_row in receipt_ids:
                for sku, quantity in _line_totals(connection, "receipt_lines", "receipt_id", receipt_row["id"]).items():
                    received[sku] += quantity
            receipt_ok = True
            for line in invoice_lines:
                if received.get(line["sku"], 0.0) + 1e-9 < float(line["quantity"]):
                    receipt_ok = False
                    exceptions.append(ExceptionItem("missing_receipt_quantity", "high", f"SKU {line['sku']} is not fully received."))
            checks["receipt"] = receipt_ok

    with connection:
        connection.execute("DELETE FROM exceptions WHERE invoice_id = ?", (invoice_id,))
        connection.executemany(
            "INSERT INTO exceptions(invoice_id, code, severity, message) VALUES (?, ?, ?, ?)",
            [(invoice_id, item.code, item.severity, item.message) for item in exceptions],
        )
        status = "matched" if not exceptions else "exception"
        connection.execute("UPDATE invoices SET status = ? WHERE id = ?", (status, invoice_id))
        connection.execute(
            "INSERT INTO audit_events(entity_type, entity_id, action, details) VALUES (?, ?, ?, ?)",
            ("invoice", invoice_id, "reconciled", json.dumps({"status": status, "exception_count": len(exceptions)})),
        )
    return status, exceptions, checks
