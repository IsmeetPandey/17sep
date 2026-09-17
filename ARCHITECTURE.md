# InvoiceGuard architecture

## Problem

Small businesses often receive invoices from suppliers while purchase orders and goods receipts live in separate records. The resulting manual comparison consumes finance time and allows duplicate invoices, quantity overbilling, price variance, and missing-receipt issues to reach payment workflows.

## Product boundary

InvoiceGuard is a deterministic exception-control layer. It accepts structured supplier, purchase-order, goods-receipt, and invoice records, then performs a repeatable three-way reconciliation:

`purchase order -> goods received -> supplier invoice -> exception queue`

It does not move money, approve payments, provide tax advice, or replace an accounting system.

## Components

- `app/main.py`: HTTP boundary, authentication dependency, validation/error mapping.
- `app/schemas.py`: Pydantic contracts and input constraints.
- `app/db.py`: SQLite schema, foreign keys, and connection lifecycle.
- `app/services.py`: domain operations, invoice fingerprinting, and reconciliation rules.
- `tests/`: business-rule and API boundary tests.
- `.github/workflows/ci.yml`: lint, strict type checking, compilation, and tests.

## Data model

Vendors own purchase orders. Purchase orders contain line items. Receipts belong to purchase orders and contain received quantities. Invoices reference a vendor and optionally a purchase order. Invoice lines are reconciled against purchase-order lines and accumulated receipt quantities. Exceptions are immutable evidence of a reconciliation result until a future resolution workflow is added. Audit events record important state transitions.

## Matching rules

1. The invoice vendor must exist and match the purchase order vendor.
2. A referenced purchase order must exist and use the same currency.
3. Every invoice SKU must exist on the purchase order.
4. Invoice quantity cannot exceed ordered quantity.
5. Invoice unit price must remain within the configured percentage tolerance.
6. Invoice quantity must be supported by received quantity.
7. An exact invoice fingerprint cannot be ingested twice.

A failed rule creates a typed exception rather than silently rejecting the business record. This keeps the system useful as an exception queue.

## Security boundaries

- API-key authentication is optional for local development and can be required through `INVOICEGUARD_API_KEY`.
- Secrets are read from environment variables rather than committed files.
- SQLite foreign keys are enabled on every connection.
- Pydantic constrains lengths and numeric ranges before domain logic runs.
- SQL values are always passed as parameters; dynamic SQL is limited to fixed internal table/column names.
- The application does not fetch arbitrary URLs or execute uploaded content.
- Production deployments should place the API behind TLS and an authenticated gateway with rate limiting.

## Deliberate non-goals

OCR, bank connectivity, payment execution, tax calculation, autonomous payment approval, and vendor-facing email automation are intentionally outside the first product boundary. They add integration and compliance complexity that would obscure the core reconciliation problem.
