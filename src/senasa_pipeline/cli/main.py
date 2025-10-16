import typer
from rich.console import Console
from rich.progress import track

app = typer.Typer(help="SENASA Data Pipeline CLI")
console = Console()

@app.command()
def sync(incremental: bool = typer.Option(False, "--incremental", "-i")) -> None:
    """Sincroniza datos desde fuentes SENASA."""
    console.print("Iniciando sync...")
    for _ in track(range(10), description="Procesando"):
        pass
    console.print("Listo ✅")
