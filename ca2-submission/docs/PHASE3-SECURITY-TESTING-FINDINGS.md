# CA2 Phase 3: Security Testing Findings & Prioritization

## Tools Used
1. Trivy v0.70.0 - Container image vulnerability scanning
2. kubesec v2.14.2 - Kubernetes manifest security posture review

---

## Finding 1: Container Image Vulnerabilities (Trivy)

### Before Remediation
- Total: 20 vulnerabilities (CRITICAL: 3, HIGH: 17)
- Source: OS packages in python:3.12-slim base (OpenSSL, libcap, ncurses)
- Python dependencies (flask, requests, psycopg2): 0 vulnerabilities (clean)

### Remediation Applied
- Added apt-get update and apt-get upgrade to Dockerfile
- Switched to non-root user in image (USER appuser)

### After Remediation
- Total: 4 vulnerabilities (CRITICAL: 0, HIGH: 4)
- Reduction: 80 percent (eliminated all CRITICAL plus 13 HIGH)
- Remaining 4: ncurses CVE-2025-69720 (no upstream fix available, tracked)

---

## Finding 2: Kubernetes Manifest Posture (kubesec)

### Score: 7 points - all hardening checks passed

PASSED:
- RunAsNonRoot
- CPU and Memory limits (DoS prevention)
- CPU and Memory requests
- Capabilities dropped (ALL)

RECOMMENDED (future work):
- ServiceAccountName with least privilege
- ReadOnlyRootFilesystem
- Seccomp / AppArmor profiles
- automountServiceAccountToken: false

---

## Prioritization Matrix

| Finding | Severity | Effort | Priority | Status |
|---------|----------|--------|----------|--------|
| CRITICAL OpenSSL CVEs | CRITICAL | Low | 1 | FIXED |
| HIGH OS package CVEs | HIGH | Low | 2 | FIXED (most) |
| Containers as root | HIGH | Low | 3 | FIXED (Phase 1) |
| No NetworkPolicy | HIGH | Med | 4 | FIXED (Phase 1) |
| No service auth | HIGH | Med | 5 | FIXED (Phase 1) |
| ncurses CVE (no fix) | HIGH | N/A | Monitor | Tracked |
| ReadOnlyRootFS | MEDIUM | Low | Future | Recommended |
| Seccomp profiles | MEDIUM | Med | Future | Recommended |

---

## Conclusion
Security testing with Trivy and kubesec validated the Phase 1 hardening and
identified container image vulnerabilities. Remediation reduced image CVEs by
80 percent (all CRITICAL eliminated) and achieved a passing kubesec posture
score of 7. Remaining items are documented as future work.
