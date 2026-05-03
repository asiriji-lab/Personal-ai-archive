# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| main (HEAD) | ✅ |

## Reporting a Vulnerability

If you discover a security vulnerability, please **do not** open a public issue.

Instead, report it privately via one of these methods:

1. **GitHub Security Advisories:** Use the [private vulnerability reporting](https://github.com/asiriji-lab/Personal-ai-archive/security/advisories/new) feature.
2. **Email:** Contact the maintainers directly (see GitHub profile).

### What to include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### Response timeline

- **Acknowledgment:** Within 48 hours
- **Assessment:** Within 1 week
- **Fix (if confirmed):** Best effort, typically within 2 weeks

## Security Considerations

This project is designed to run **100% locally**. However:

- **Never commit `.env` files** — they may contain API keys.
- **The `knowledge_base/` directory** contains personal data and is gitignored by default.
- **MCP bridge (`brain_server.py`)** binds to `localhost` only — do not expose to the network without authentication.
- **Validation harness** results should be reviewed before trusting AI-generated content.
