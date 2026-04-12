import argparse
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import asyncio

from db.database import engine
from db import models

models.Base.metadata.create_all(bind=engine)
console = Console()

async def run_demo():
    console.print(Panel.fit("[bold blue]CV Screening AI Agent[/bold blue]\nDémarrage du mode CLI Demo...", border_style="blue"))
    
    with console.status("[bold green]Initialisation de la base de données...") as status:
        await asyncio.sleep(1)
        console.log("Base de données SQLite prête.")
        
    with console.status("[bold green]Création du job 'Développeur Python'...") as status:
        await asyncio.sleep(1)
        console.log("Job profile créé avec succès.")
        
    with console.status("[bold yellow]Parsing des CVs (PDF, DOCX) et Anonymisation...") as status:
        await asyncio.sleep(2)
        console.log("3 CVs parsés en texte brut.")
        
    with console.status("[bold magenta]Analyse Anthropic Claude (Extraction & Scoring)...") as status:
        await asyncio.sleep(3)
        console.log("Analyse sémantique terminée.")
        
    console.print("\n[bold]Résultats du Screening:[/bold]")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Rang", style="dim", width=6)
    table.add_column("Candidat")
    table.add_column("Score Final", justify="right")
    table.add_column("Note IA")
    
    table.add_row("1", "Alice Dupont", "[green]92.5[/green]", "Excellent profil technique, correspond parfaitement.")
    table.add_row("2", "Bob Martin", "[yellow]75.0[/yellow]", "Bonne expérience mais manque de compétences en Docker.")
    table.add_row("3", "[MASQUÉ]", "[red]42.0[/red]", "Ne possède pas le niveau d'étude requis.")
    
    console.print(table)
    console.print("\n[bold green]✓[/bold green] Export Excel généré: [cyan]report.xlsx[/cyan]")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CV Screening AI Agent CLI")
    parser.add_argument("--demo", action="store_true", help="Lancer la démonstration CLI")
    args = parser.parse_args()
    
    if args.demo:
        asyncio.run(run_demo())
    else:
        console.print("[red]Mode non spécifié. Utilisez --demo pour la démonstration.[/red]")
