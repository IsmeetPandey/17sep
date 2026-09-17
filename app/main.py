from __future__ import annotations

import secrets
import sqlite3
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query

from app.config import settings
from app.db import connect, initialize
from app.schemas import (
    ExceptionOut,
    HealthOut,
    InvoiceCreate,
    PurchaseOrderCreate,
    ReceiptCreate,
    ReconciliationResult,
    VendorCreate,
    VendorOut,
)
from app.services import create_invoice, create_purchase_order, create_receipt, create_vendor, reconcile_invoice


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize(settings.database_path)
    yield


app = FastAPI(title="InvoiceGuard", version="0.1.0", lifespan=lifespan)


def db() -> sqlite3.Connection:
    connection = connect(settings.database_path)
    try:
        yield connection
    finally:
        connection.close()


def auth(x_api_key: Annotated[str | None, Header()] = None) -> None:
    if settings.api_key and not (x_api_key and secrets.compare_digest(x_api_key, settings.api_key)):
        raise HTTPException(status_code=401, detail="invalid_api_key")


Connection = Annotated[sqlite3.Connection, Depends(db)]
Authenticated = Annotated[None, Depends(auth)]


@app.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut(status="ok", service="invoiceguard")


@app.post("/vendors", response_model=VendorOut, status_code=201, dependencies=[Depends(auth)])
def add_vendor(payload: VendorCreate, connection: Connection) -> VendorOut:
    try:
        vendor_id = create_vendor(connection, payload.name, payload.tax_id)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="vendor_creation_failed") from exc
    return VendorOut(id=vendor_id, **payload.model_dump())


@app.post("/purchase-orders", status_code=201, dependencies=[Depends(auth)])
def add_purchase_order(payload: PurchaseOrderCreate, connection: Connection) -> dict[str, int | str]:
    try:
        order_id = create_purchase_order(connection, payload)
    except ValueError as exc:
        status = 404 if str(exc.value) == "vendor_not_found" else 409
        raise HTTPException(status_code=status, detail=str(exc.value)) from exc
    return {"id": order_id, "status": "created"}


@app.post("/receipts", status_code=201, dependencies=[Depends(auth)])
def add_receipt(payload: ReceiptCreate, connection: Connection) -> dict[str, int | str]:
    try:
        receipt_id = create_receipt(connection, payload)
    except ValueError as exc:
        status = 404 if str(exc.value) == "purchase_order_not_found" else 409
        raise HTTPException(status_code=status, detail=str(exc.value)) from exc
    return {"id": receipt_id, "status": "created"}


@app.post("/invoices", status_code=201, dependencies=[Depends(auth)])
def add_invoice(payload: InvoiceCreate, connection: Connection) -> dict[str, int | str]:
    try:
        invoice_id = create_invoice(connection, payload)
    except ValueError as exc:
        detail = str(exc.value)
        status = 404 if detail in {"vendor_not_found", "purchase_order_not_found"} else 409
        raise HTTPException(status_code=status, detail=detail) from exc
    return {"id": invoice_id, "status": "pending"}


@app.post("/invoices/{invoice_id}/reconcile", response_model=ReconciliationResult, dependencies=[Depends(auth)])
def reconcile(
    invoice_id: int,
    connection: Connection,
    tolerance_pct: float = Query(default=settings.price_tolerance_pct, ge=0, le=100),
) -> ReconciliationResult:
    try:
        status, exceptions, checks = reconcile_invoice(connection, invoice_id, tolerance_pct)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc.value)) from exc
    return ReconciliationResult(
        invoice_id=invoice_id,
        status=status,
        checks=checks,
        exceptions=[{"code": item.code, "severity": item.severity, "message": item.message} for item in exceptions],
    )


@app.get("/exceptions", response_model=list[ExceptionOut], dependencies=[Depends(auth)])
def list_exceptions(
    connection: Connection,
    unresolved_only: bool = Query(default=True),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[ExceptionOut]:
    query = "SELECT id, invoice_id, code, severity, message, resolved FROM exceptions"
    params: list[object] = []
    if unresolved_only:
        query += " WHERE resolved = 0"
    query += " ORDER BY created_at DESC, id DESC LIMIT ?"
    params.append(limit)
    rows = connection.execute(query, params).fetchall()
    return [ExceptionOut(**dict(row), resolved=bool(row["resolved"])) for row in rows]
