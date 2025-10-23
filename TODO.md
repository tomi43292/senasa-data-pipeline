# SENASA Authentication Implementation TODO

This checklist tracks the end-to-end implementation of AFIP → SENASA authentication in senasa-data-pipeline using FastAPI, httpx, Clean Architecture, and robust retry/validation.

## Phase 1: Core Architecture (12 files)

### Ports (4)
- [x] src/senasa_pipeline/application/ports/session_store_port.py
- [x] src/senasa_pipeline/application/ports/http_client_port.py
- [x] src/senasa_pipeline/application/ports/auth_provider_port.py
- [x] src/senasa_pipeline/application/ports/senasa_login_port.py

### Use Cases (1)
- [x] src/senasa_pipeline/application/use_cases/ensure_senasa_session.py

### Adapters (5)
- [x] src/senasa_pipeline/infrastructure/adapters/http/httpx_client.py
- [x] src/senasa_pipeline/infrastructure/adapters/afip/portal_cf_provider.py (robust JSON detection)
- [x] src/senasa_pipeline/infrastructure/adapters/afip/jsf_provider.py (fallback)
- [x] src/senasa_pipeline/infrastructure/adapters/senasa/login_consumer.py (OIDC + selection)
- [x] src/senasa_pipeline/infrastructure/adapters/session/memory_store.py
- [x] src/senasa_pipeline/infrastructure/adapters/session/sqlite_store.py

### API (1)
- [x] src/senasa_pipeline/presentation/api/routes/auth.py

### Tests (2+)
- [x] tests/unit/test_ensure_senasa_session.py
- [ ] tests/unit/test_portal_cf_provider.py
- [ ] tests/unit/test_senasa_login_consumer_oidc.py

## Phase 2: Resilience & Observability
- [x] Add tenacity-based retries with jitter per network step (httpx client)
- [ ] Add circuit breaker per upstream (AFIP, PortalCF, SENASA)
- [ ] structlog logging with context (stage, url, status)
- [ ] Prometheus counters and histograms for auth attempts and latency

## Phase 3: Persistence & CLI
- [x] Implement persistent SessionStore (sqlite/duckdb)
- [ ] CLI command: `senasa auth ensure`

## Environment & Docs
- [x] Add .env.example
- [x] Ignore .env in .gitignore
- [x] Load .env in settings and document variables in README

## New tasks
- [ ] Improve provider selection on Login.aspx (fallback a primer usuario si no coincide id/texto)
- [ ] Add extra OIDC follow-up after selection if needed (loop with cap)
- [ ] Add integration tests using httpx.MockTransport for OIDC/selection
