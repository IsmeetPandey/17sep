# Contributing to InvoiceGuard

## Development principles

- Keep the product focused on invoice reconciliation and exception control.
- Define acceptance behavior before changing business rules.
- Keep domain logic deterministic and explainable.
- Review the full diff before every meaningful commit.
- Add regression tests for every fixed defect.
- Do not introduce a dependency without verifying its legitimacy and necessity.
- Never commit secrets or real customer/supplier data.

## Local checks

```bash
python -m ruff check .
python -m mypy app
python -m compileall -q app tests
python -m pytest -q
```

## Change workflow

1. Describe the operational problem the change solves.
2. Add or update acceptance tests.
3. Implement the smallest coherent domain change.
4. Review the complete diff for correctness, security, and performance.
5. Run all checks locally.
6. Update documentation when behavior or architecture changes.
7. Submit a focused pull request.
