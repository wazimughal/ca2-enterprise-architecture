# CA2 Security Review & Architecture Analysis

## Part A: Current Architecture Documentation

### A1. System Components

**Services:**
- Gateway (Flask, port 5000) - Entry point for all requests
- Checkout (Flask, port 5001) - Processes checkout requests
- Pricing (Flask, port 5002) - Returns product prices
- Inventory (Flask, port 5003) - Checks product stock
- PostgreSQL (port 5432) - Stores audit records

**Kubernetes Resources:**
- Namespace: ca2
- Deployments: 5 (gateway, checkout, pricing, inventory, postgres)
- Services: 5 ClusterIP services
- Ingress: 1 (Traefik with KEDA HTTP interceptor)

---

## Part B: Security Risks Identified

### Risk 1: No Service-to-Service Authentication
- **Severity:** HIGH
- **Issue:** Services communicate with no auth - pods can impersonate each other
- **Fix:** Add API key validation between services

### Risk 2: No Network Policy
- **Severity:** HIGH
- **Issue:** Any pod can reach any other pod and database
- **Fix:** Create NetworkPolicy restricting traffic flows

### Risk 3: Containers Running as Root
- **Severity:** HIGH
- **Issue:** If compromised, attacker gets root access
- **Fix:** Add securityContext with runAsNonRoot: true

### Risk 4: No Resource Limits
- **Severity:** MEDIUM
- **Issue:** DoS vulnerability - one pod can exhaust cluster
- **Fix:** Set CPU/memory requests and limits

### Risk 5: Secrets Not Encrypted at Rest
- **Severity:** MEDIUM
- **Issue:** DB credentials stored plain in etcd
- **Fix:** Enable encryption at rest in Kubernetes

### Risk 6: No Logging/Monitoring
- **Severity:** HIGH
- **Issue:** Can't detect attacks or troubleshoot
- **Fix:** Add JSON logging and Prometheus (Phase 2)

### Risk 7: Images Not Scanned
- **Severity:** MEDIUM
- **Issue:** Base images may have vulnerabilities
- **Fix:** Scan with Trivy (Phase 3)

---

## Part C: Risk Prioritization

| Rank | Risk | Severity | Effort | When |
|------|------|----------|--------|------|
| 1 | Service-to-Service Auth | HIGH | Easy | Phase 1 |
| 2 | Network Policy | HIGH | Medium | Phase 1 |
| 3 | Run as Non-Root | HIGH | Easy | Phase 1 |
| 4 | Resource Limits | MEDIUM | Easy | Phase 1 |
| 5 | Encryption at Rest | MEDIUM | Hard | Future |
| 6 | Logging/Monitoring | HIGH | Medium | Phase 2 |
| 7 | Image Scanning | MEDIUM | Easy | Phase 3 |

---

## Part D: Architecture Diagrams

See: DIAGRAM-A-CURRENT-STATE.md and DIAGRAM-B-IMPROVED-STATE.md

