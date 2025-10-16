import typer
from senasa_pipeline.application.use_cases.sync_senasa_data import SyncSenasaDataUseCase
from senasa_pipeline.application.use_cases.export_senasa_data import ExportSenasaDataUseCase
from senasa_pipeline.application.dtos.sync_request_dto import SyncRequestDTO
from senasa_pipeline.application.dtos.export_request_dto import ExportRequestDTO
from senasa_pipeline.infrastructure.repositories.duckdb_repository import DuckDBSenasaRepository
from senasa_pipeline.infrastructure.adapters.scraping_adapter import SenasaWebScrapingAdapter
from senasa_pipeline.infrastructure.adapters.notification_adapter import SimpleNotificationAdapter
from senasa_pipeline.infrastructure.adapters.storage_adapter import ParquetStorageAdapter

app = typer.Typer(help="SENASA Data Pipeline CLI")

_repo = DuckDBSenasaRepository()
_scraper = SenasaWebScrapingAdapter()
_notifier = SimpleNotificationAdapter()
_storage = ParquetStorageAdapter()

@app.command()
def sync(incremental: bool = typer.Option(False, "--incremental", "-i")) -> None:
    uc = SyncSenasaDataUseCase(scraper=_scraper, validator=lambda r: True, repo=_repo)  # type: ignore[arg-type]
    n = uc.execute(SyncRequestDTO(incremental=incremental))
    typer.echo(f"Registros procesados: {n}")

@app.command()
def export(format: str = typer.Option("parquet", "--format", "-f"), path: str = typer.Option("export.parquet", "--path", "-p")) -> None:
    uc = ExportSenasaDataUseCase(repo=_repo, storage=_storage)
    out = uc.execute(ExportRequestDTO(format=format), path=path)
    typer.echo(out)
