import typer
from senasa_pipeline.application.use_cases import (
    SyncSenasaDataUseCase,
    ExportSenasaDataUseCase,
    SyncRequestDTO,
    ExportRequestDTO,
)
from senasa_pipeline.infrastructure.adapters import (
    DuckDBSenasaRepository,
    ParquetStorageAdapter,
    SenasaWebScrapingAdapter,
    SimpleNotificationAdapter,
)

app = typer.Typer(help="SENASA Data Pipeline CLI")

repo = DuckDBSenasaRepository()
scraper = SenasaWebScrapingAdapter()
notifier = SimpleNotificationAdapter()
storage = ParquetStorageAdapter()

@app.command()
def sync(incremental: bool = typer.Option(False, "--incremental", "-i")) -> None:
    uc = SyncSenasaDataUseCase(scraper=scraper, validator=lambda r: True, repo=repo, notifier=notifier)  # type: ignore[arg-type]
    n = uc.execute(SyncRequestDTO(incremental=incremental))
    typer.echo(f"Registros procesados: {n}")

@app.command()
def export(format: str = typer.Option("parquet", "--format", "-f"), path: str = typer.Option("export.parquet", "--path", "-p")) -> None:
    uc = ExportSenasaDataUseCase(repo=repo, storage=storage)
    out = uc.execute(ExportRequestDTO(format=format), path=path)
    typer.echo(out)

@app.command()
def validate() -> None:
    typer.echo("validate placeholder")
