# Security Policy

## Supported Versions

We actively maintain security updates for the following versions of the `instance-security` project:

| Version | Supported          |
|---------|--------------------|
| 1.0     | ✅ Yes            |
| < 1.0   | ❌ No             |

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it responsibly. We appreciate your help in keeping our project secure.

### How to Report
- **Email**: Send a detailed report to [sourav.sarkar@ecanarys.com](sourav.sarkar@ecanarys.com). Include:
  - A description of the vulnerability.
  - Steps to reproduce the issue.
  - Potential impact (e.g., data exposure, code execution).
  - Any suggested fixes, if applicable.
- **Response Time**: We aim to acknowledge your report within 48 hours and provide a detailed response within 7 days.
- **Confidentiality**: Please do not disclose the vulnerability publicly until we’ve had a chance to address it.

### What to Expect
- After reporting, we’ll work with you to validate the issue.
- If the vulnerability is confirmed, we’ll prioritize a fix and release a patch as soon as possible.
- We’ll credit you in the release notes (unless you prefer to remain anonymous).

## Security Updates

We use Dependabot to monitor and apply security updates to our dependencies:
- **Maven Dependencies**: We automatically apply security updates for dependencies in `pom.xml` (e.g., `commons-collections`, `junit`). Updates are grouped under the `security-group` and assigned to the "JavaTest" milestone.
- **GitHub Actions**: We monitor updates to GitHub Actions workflows daily.
- **Process**: Security updates are reviewed and merged promptly to ensure the project remains secure.

## Best Practices

To minimize security risks, we recommend the following:
- Keep dependencies up to date by reviewing Dependabot pull requests.
- Avoid using unsupported versions of this project (see table above).
- If using this project in production, ensure you’ve enabled Dependabot security updates in your repository settings.

## Contact

For general security inquiries, reach out to the maintainers at [sourav.sarkar@ecanarys.com](mailto:sourav.sarkar@ecanarys.com).

---

Last updated: April 3, 2025
