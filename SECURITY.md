# Security Policy

## Supported version

The `main` branch is the supported development line.

## Reporting a vulnerability

Please do not publish sensitive vulnerability details in a public issue. Use GitHub's private vulnerability reporting feature when it is enabled for the repository, or contact the maintainer through a private GitHub channel.

Include:

- affected endpoint/module;
- reproducible steps;
- expected and observed behavior;
- potential impact;
- a minimal proof of concept that contains no real credentials or private data.

## Security design

InvoiceGuard does not execute payments or store bank credentials. The API supports an environment-provided API key for deployments that require authentication. Production deployments should use TLS, a gateway with rate limiting, restricted network access, protected secrets, and a database backup strategy.

Security-sensitive areas include authentication, input validation, SQL parameterization, duplicate detection, reconciliation integrity, and audit history.

Do not commit API keys, passwords, tokens, private certificates, customer data, or supplier documents containing personal information.
