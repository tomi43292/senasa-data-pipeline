# Clean Architecture - Documentación

## Capas

- Domain: entidades, value objects e interfaces (repos/services) puras.
- Application: casos de uso y ports (sin depender de frameworks).
- Infrastructure: adapters/repositories que implementan interfaces.
- Presentation: FastAPI (routers) y CLI (Typer) que orquestan casos de uso.

## Principios

- Inversión de dependencias: las capas externas dependen de las internas.
- Testabilidad: mocks/fakes sobre interfaces y ports.
- SRP/SoC: responsabilidades separadas por carpeta.
- Documentar con docstrings y typing estricto.

## Rutas

- API REST: /v1/senasa/sync, /v1/senasa/records, /v1/senasa/export
- CLI: sync, export, validate
