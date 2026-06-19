# Security Policy

## Supported versions

RADAR follows a single-release model. Only the latest tagged release on `main`
receives security fixes.

| Version | Supported |
|---------|-----------|
| 1.0.x   | ✅        |
| < 1.0   | ❌        |

## Reporting a vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Report privately instead, using either:

- GitHub's [private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
  (**Security → Report a vulnerability** on this repo), or
- email to **paulpietra83@gmail.com** with `[SECURITY]` in the subject.

Please include: a description, reproduction steps or a proof of concept, the
affected version/commit, and the impact you foresee. We aim to acknowledge
within **72 hours** and to ship a fix or mitigation as fast as the severity
warrants. Please give us a reasonable window to patch before any public
disclosure.

## Handling secrets

RADAR never stores credentials in the repository:

- All secrets come from environment variables — `.env` is gitignored and must
  never be committed.
- The `/scan*` endpoints are gated by a shared bearer token (`RADAR_SHARED_TOKEN`);
  the API **fails closed** if the token is unset.
- Testers can supply their own Linkup key via the `X-Linkup-Key` header (BYOK),
  so no shared key needs to be distributed.

If you find a committed secret, treat it as compromised: report it as above and
rotate the key immediately.
