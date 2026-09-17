# InvoiceGuard

**Deterministic invoice intake and purchase-to-payment exception control for small businesses.**

InvoiceGuard targets a specific operational problem: finance teams often have to compare supplier invoices against purchase orders and goods-receipt records manually. That creates repetitive work and leaves room for duplicate invoices, quantity overbilling, price variance, and invoices unsupported by received goods.

Recent 2026 reporting on Indian SMBs points to manual invoice processing as a persistent accounting bottleneck, while other research highlights reconciliation and administrative work as recurring SMB pain points. citeturn1search3turn1search6turn1search2

## What it does

InvoiceGuard creates a controlled workflow around four records:

1. **Supplier** — who issued the invoice.
2. **Purchase order** — what was ordered and at what price.
3. **Goods receipt** — what was actually received.
4. **Invoice** — what the supplier is asking to be paid for.

The reconciliation engine then produces either `matched` or `exception` with explicit reasons.

### Current controls

- Duplicate invoice fingerprinting.
- Vendor and purchase-order consistency checks.
- Purchase-order line matching.
- Quantity-over-order detection.
- Configurable unit-price tolerance.
- Receipt-backed quantity verification.
- Typed exception records with severity.
- Audit events for important state transitions.
- Optional API-key authentication.
- SQLite foreign-key enforcement.
- Strict request validation and bounded query pagination.

## Why this problem

The product deliberately focuses on one workflow rather than attempting to become an accounting suite. 2026 reporting continues to identify manual invoice processing, reconciliation, and administrative work as significant SMB operational friction. citeturn1search3turn1search8turn1search14

The intended value proposition is straightforward: **turn repetitive invoice comparison into a deterministic exception queue without taking payment authority away from the business.**

## Architecture

```text
Client / accounting workflow
          |
          v
     FastAPI API
          |
          +---- Pydantic validation
          |
          +---- Domain services
          |       +-- invoice fingerprinting
          |       +-- purchase-order validation
          |       +-- three-way reconciliation
          |       +-- exception generation
          |
          v
       SQLite
     /    |    \
 vendors  orders  invoices
             |
          receipts
             |
        audit_events
```

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the domain model, matching rules, security boundaries, and non-goals.

## API

- `GET /health` — service health.
- `POST /vendors` — create a supplier.
- `POST /purchase-orders` — record an order and its lines.
- `POST /receipts` — record received quantities.
- `POST /invoices` — ingest an invoice.
- `POST /invoices/{invoice_id}/reconcile?tolerance_pct=2` — run reconciliation.
- `GET /exceptions?unresolved_only=true&limit=100` — inspect the exception queue.

## Local development

Requires Python 3.12.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
uvicorn app.main:app --reload
```

The default local database is `./data/invoiceguard.sqlite3`. Override it with `INVOICEGUARD_DB`.

For a protected deployment, set `INVOICEGUARD_API_KEY` to a secret value. Never commit that value.

## Verification

CI runs Ruff linting, Mypy strict type checking, Python compilation, unit tests for reconciliation rules and duplicate detection, and API tests for health/authentication boundaries.

The repository also contains Dependabot configuration for pip and GitHub Actions. GitHub documents Dependabot as the mechanism for automated dependency updates and security update pull requests. citeturn2search1turn2search3

## Security

See [`SECURITY.md`](SECURITY.md). GitHub recommends a security policy plus dependency, secret, and code-security controls for public repositories. citeturn2search0turn2search6

## Scope and non-goals

InvoiceGuard is an exception-control layer, not an accounting replacement. It does not execute payments, calculate taxes, provide tax/legal advice, connect to banks, or autonomously approve money movement.

## Status

Early production-oriented foundation. The core deterministic reconciliation engine, persistence model, API boundary, test suite, CI, dependency maintenance, security documentation, and architecture documentation are implemented. Further integrations should be added only when they directly improve the invoice-reconciliation workflow.
