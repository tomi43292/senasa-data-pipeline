# SENASA Authentication Implementation TODO

This checklist tracks the end-to-end implementation of AFIP → SENASA authentication in senasa-data-pipeline using FastAPI, httpx, Clean Architecture, and robust retry/validation.

## Phase 1: Core Architecture (12 files)

### Ports (4)
- [ ] src/senasa_pipeline/application/ports/session_store_port.py
- [ ] src/senasa_pipeline/application/ports/http_client_port.py
- [ ] src/senasa_pipeline/application/ports/auth_provider_port.py
- [ ] src/senasa_pipeline/application/ports/senasa_login_port.py

### Use Cases (1)
- [ ] src/senasa_pipeline/application/use_cases/ensure_senasa_session.py

### Adapters (5)
- [ ] src/senasa_pipeline/infrastructure/adapters/http/httpx_client.py
- [ ] src/senasa_pipeline/infrastructure/adapters/afip/portal_cf_provider.py
- [ ] src/senasa_pipeline/infrastructure/adapters/afip/jsf_provider.py
- [ ] src/senasa_pipeline/infrastructure/adapters/senasa/login_consumer.py
- [ ] src/senasa_pipeline/infrastructure/adapters/session/memory_store.py

### API (1)
- [ ] src/senasa_pipeline/presentation/api/routes/auth.py

### Tests (2+)
- [ ] tests/unit/test_ensure_senasa_session.py
- [ ] tests/unit/test_portal_cf_provider.py

## Phase 2: Resilience & Observability
- [ ] Add tenacity-based retries with jitter per network step
- [ ] Add circuit breaker per upstream (AFIP, PortalCF, SENASA)
- [ ] structlog logging with context (stage, url, status)
- [ ] Prometheus counters and histograms for auth attempts and latency

## Phase 3: Persistence & CLI
- [ ] Implement persistent SessionStore (sqlite/duckdb)
- [ ] CLI command: `senasa auth ensure`

## Notes
- Prefer Portal CF (token/sign) as primary path; fall back to JSF when needed.
- Validate SENASA session by probing `/Sur/Extracciones/List` without redirects and checking `__VIEWSTATE`.
- No Django: use FastAPI and project’s own storage for session persistence.
