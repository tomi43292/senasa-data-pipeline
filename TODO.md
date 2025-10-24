# SENASA Data Pipeline - TODO

## ✅ COMPLETED

### ✅ Clean Architecture Foundation
- [x] Use Cases (Application Layer)
- [x] Ports/Interfaces (Application Layer)
- [x] Adapters (Infrastructure Layer)
- [x] FastAPI Presentation Layer
- [x] Domain Models and Value Objects

### ✅ Authentication System (AFIP → SENASA)
- [x] **UnifiedAfipProvider**: JSF login + Portal CF fallback
- [x] **SenasaLoginConsumer**: POST /afip + user selection
- [x] **EnsureSenasaSessionUseCase**: orchestration with TTL validation
- [x] **SQLiteSessionStore**: cookie persistence
- [x] **HttpxClient**: shared session between AFIP and SENASA
- [x] **Environment configuration**: CUIT, password, timeouts, TTL
- [x] **Working E2E flow**: replicates coadelpa-project login() exactly

## 🚧 IN PROGRESS / TODO

### 🔧 Testing & Quality Assurance
- [ ] **Unit tests** for UnifiedAfipProvider (JSF + Portal CF scenarios)
- [ ] **Unit tests** for SenasaLoginConsumer (POST /afip + user selection)
- [ ] **Integration tests** with httpx.MockTransport for HTTP mocking
- [ ] **E2E tests** with real credentials (optional, for development)
- [ ] **Error handling tests** (network failures, AFIP down, invalid credentials)
- [ ] **TTL expiration tests** for SQLiteSessionStore
- [ ] **Code coverage** reporting with pytest-cov

### 📋 Logging & Observability
- [ ] **Structured logging** with loguru or structlog
- [ ] **Log correlation IDs** across use case execution
- [ ] **Security**: mask sensitive data (passwords, tokens) in logs
- [ ] **Performance metrics**: login duration, success/failure rates
- [ ] **Health check endpoint** for auth system status
- [ ] **Prometheus metrics** integration (optional)

### 📊 Data Pipeline Core
- [ ] **SENASA API client** for data extraction
- [ ] **Data models** for tambores, extracciones, etc.
- [ ] **ETL use cases** for data processing
- [ ] **Database adapters** (PostgreSQL/SQLite)
- [ ] **Scheduling system** for automated runs
- [ ] **Data validation** and quality checks

### 🚀 DevOps & Deployment
- [ ] **Docker containerization**
- [ ] **CI/CD pipeline** with GitHub Actions
- [ ] **Environment-specific configs** (dev/staging/prod)
- [ ] **Database migrations** strategy
- [ ] **Monitoring and alerting**
- [ ] **Deployment documentation**

### 📚 Documentation
- [ ] **API documentation** with OpenAPI/Swagger
- [ ] **Architecture decision records** (ADRs)
- [ ] **Developer setup guide**
- [ ] **Authentication flow diagrams**
- [ ] **Troubleshooting guide**

## 📝 NOTES

### Authentication Implementation
- Follows Clean Architecture principles with clear separation of concerns
- UnifiedAfipProvider handles both JSF and Portal CF methods with shared HttpClient
- SenasaLoginConsumer focuses only on SENASA-specific login completion
- Use case orchestrates the flow and manages session persistence
- Exact replication of working coadelpa-project login() method

### Next Priority
1. **Add comprehensive tests** to ensure reliability
2. **Implement structured logging** for debugging and monitoring
3. **Begin core data pipeline** features once auth is stable

### Environment Variables Required
```bash
AFIP_CUIT=your_cuit_here
AFIP_PASSWORD=your_password_here
HTTP_TIMEOUT=45
SESSION_TTL_HOURS=12
```
