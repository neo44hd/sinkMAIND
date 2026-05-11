#!/usr/bin/env python3
"""sinkMAIND CLI — command-line interface for the retroactive memory system."""

import json
import os
import sys
from datetime import datetime, timedelta

import click
import yaml
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import database
import embeddings
import indexer
import search as search_engine

console = Console()

CONFIG_PATH = os.path.expanduser("~/sinkia-memory/config.yaml")


def load_config() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


def _parse_date(date_str: str) -> str:
    """Parse date string to ISO format."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        return date_str


def _build_filters(
    app=None, doc_type=None, category=None, level=None,
    since=None, until=None, today=False, this_week=False, this_month=False,
    path=None, tag=None,
) -> dict:
    """Build filter dict from CLI options."""
    filters = {}
    if app:
        filters["app"] = app
    if doc_type:
        filters["doc_type"] = doc_type
    if category:
        filters["category"] = category
    if level:
        filters["level"] = level
    if today:
        filters["since"] = datetime.now().strftime("%Y-%m-%d")
    elif this_week:
        filters["since"] = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    elif this_month:
        filters["since"] = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    if since:
        filters["since"] = _parse_date(since)
    if until:
        filters["until"] = _parse_date(until)
    if path:
        filters["path"] = path
    if tag:
        filters["tag"] = tag
    return filters


def _truncate(text: str, max_len: int = 60) -> str:
    """Truncate text for display."""
    text = text.replace("\n", " ").strip()
    if len(text) > max_len:
        return text[:max_len - 3] + "..."
    return text


@click.group()
def cli():
    """🧠 sinkMAIND — Sistema de memoria retroactiva"""
    pass


# ─── SEARCH ──────────────────────────────────────────────────────
@cli.command()
@click.argument("query", required=False, default="")
@click.option("-s", "--semantic", is_flag=True, help="Búsqueda semántica (Ollama embeddings)")
@click.option("--hybrid", is_flag=True, help="Búsqueda híbrida (textual + semántica)")
@click.option("--app", help="Filtrar por app (docker, pm2, warp, claude, nginx, ollama...)")
@click.option("--type", "doc_type", help="Filtrar por tipo (log, chat, doc, config, code, report, system)")
@click.option("--cat", help="Filtrar por categoría (system, ai, network, project, docs)")
@click.option("--level", help="Filtrar por severidad (error, warn, info, debug)")
@click.option("--since", help="Fecha inicio (YYYY-MM-DD)")
@click.option("--until", help="Fecha fin (YYYY-MM-DD)")
@click.option("--today", is_flag=True, help="Solo hoy")
@click.option("--this-week", is_flag=True, help="Esta semana")
@click.option("--this-month", is_flag=True, help="Este mes")
@click.option("--path", help="Filtrar por ruta")
@click.option("--tag", help="Filtrar por tag")
@click.option("--sort", default="relevance", type=click.Choice(["relevance", "date"]), help="Ordenar por")
@click.option("--limit", default=20, type=int, help="Máximo resultados")
@click.option("--format", "fmt", default="table", type=click.Choice(["table", "json", "detail", "brief"]), help="Formato salida")
def search(query, semantic, hybrid, app, doc_type, cat, level, since, until,
           today, this_week, this_month, path, tag, sort, limit, fmt):
    """Buscar en la memoria del sistema."""
    if not query and not semantic:
        console.print("[red]Error: proporciona un texto de búsqueda o usa --semantic[/red]")
        return

    filters = _build_filters(app, doc_type, cat, level, since, until, today, this_week, this_month, path, tag)

    if hybrid:
        results = search_engine.hybrid_search(query, filters=filters, limit=limit)
    elif semantic:
        results = search_engine.search(query, semantic=True, filters=filters, limit=limit)
    else:
        results = search_engine.search(query, semantic=False, filters=filters, limit=limit, sort=sort)

    if not results:
        console.print("[yellow]No se encontraron resultados[/yellow]")
        return

    if fmt == "json":
        click.echo(json.dumps(results, indent=2, ensure_ascii=False, default=str))
        return

    if fmt == "brief":
        for r in results:
            src = r.get("source", "?")
            date = (r.get("created_at") or r.get("indexed_at", ""))[:10]
            frag = _truncate(r.get("content", ""), 80)
            console.print(f"  [dim]{date}[/dim] [cyan]{src:15}[/cyan] {frag}")
        return

    if fmt == "detail":
        for r in results:
            score = f" (score: {r.get('score', 'N/A')})" if "score" in r else ""
            console.print(Panel(
                r.get("content", ""),
                title=f"[bold]{r.get('source', '?')}[/bold] • {r.get('app', '?')} • {r.get('doc_type', '?')}{score}",
                subtitle=f"📅 {r.get('created_at', '?')} | 📂 {r.get('source_path', '?')} | 🏷️ {r.get('tags', '-')}"
            ))
        return

    # Default: table format
    table = Table(title=f"🔍 Resultados: {len(results)} encontrados", show_lines=True)
    table.add_column("Fecha", style="dim", width=10)
    table.add_column("App", style="cyan", width=12)
    table.add_column("Tipo", style="green", width=8)
    table.add_column("Level", style="red", width=6)
    table.add_column("Fuente", style="yellow", width=15)
    table.add_column("Fragmento", width=50)

    for r in results:
        date = (r.get("created_at") or r.get("indexed_at", ""))[:10]
        app_val = r.get("app", "-") or "-"
        dtype = r.get("doc_type", "-") or "-"
        lvl = r.get("level", "-") or "-"
        src = r.get("source", "-") or "-"
        frag = _truncate(r.get("content", ""), 50)

        # Color level
        if lvl == "error":
            lvl = f"[bold red]{lvl}[/bold red]"
        elif lvl == "warn":
            lvl = f"[yellow]{lvl}[/yellow]"

        table.add_row(date, app_val, dtype, lvl, src, frag)

    console.print(table)


# ─── INDEX ───────────────────────────────────────────────────────
@cli.command()
@click.option("--all", "index_all", is_flag=True, help="Indexar todas las fuentes")
@click.option("--source", help="Indexar una fuente específica")
@click.option("--status", is_flag=True, help="Mostrar fuentes configuradas")
@click.option("--embeddings", "gen_embeddings", is_flag=True, help="Generar embeddings para documentos sin embedding")
@click.option("--max-docs", default=500, type=int, help="Máximo documentos a procesar (default 500)")
@click.option("--embed-batch", default=20, type=int, help="Textos por petición Ollama (default 20)")
def index(index_all, source, status, gen_embeddings, max_docs, embed_batch):
    """Indexar fuentes de datos."""
    database.init_db()

    if status:
        config = load_config()
        sources = config.get("sources", {})
        table = Table(title="📂 Fuentes configuradas")
        table.add_column("Fuente", style="bold")
        table.add_column("Tipo", style="cyan")
        table.add_column("Habilitada", style="green")
        table.add_column("Ruta/Comando", style="dim")

        for name, cfg in sources.items():
            enabled = "✅" if cfg.get("enabled", True) else "❌"
            stype = cfg.get("type", "?")
            path = cfg.get("path", cfg.get("command", ", ".join(cfg.get("commands", []))))
            table.add_row(name, stype, enabled, str(path)[:50])

        console.print(table)
        return

    if gen_embeddings:
        total_done = 0
        while True:
            count = embeddings.generate_and_store_embeddings(
                batch_size=50, max_docs=max_docs, embed_batch=embed_batch
            )
            total_done += count
            if count == 0:
                break
            console.print(f"[green]Lote completado: {total_done} embeddings totales generados[/green]")
        console.print(f"[bold green]✅ Embeddings completados: {total_done} generados en total[/bold green]")
        return

    if index_all:
        indexer.index_all()
        return

    if source:
        indexer.index_specific(source)
        return

    console.print("[yellow]Usa --all, --source <nombre>, --status, o --embeddings[/yellow]")


# ─── STATS ───────────────────────────────────────────────────────
@cli.command()
@click.option("--by-app", is_flag=True, help="Estadísticas por app")
@click.option("--by-type", is_flag=True, help="Estadísticas por tipo")
@click.option("--by-source", is_flag=True, help="Estadísticas por fuente")
def stats(by_app, by_type, by_source):
    """Ver estadísticas de la base de datos."""
    if by_app:
        rows = database.get_stats(by="app")
        col = "App"
    elif by_type:
        rows = database.get_stats(by="doc_type")
        col = "Tipo"
    elif by_source:
        rows = database.get_stats(by="source")
        col = "Fuente"
    else:
        rows = database.get_stats()
        total = rows[0]["total"] if rows else 0
        console.print(Panel(f"📊 Total documentos: [bold]{total}[/bold]", title="sinkMAIND Stats"))
        return

    table = Table(title=f"📊 Estadísticas por {col}")
    table.add_column(col, style="bold")
    table.add_column("Count", style="cyan", justify="right")
    for r in rows:
        table.add_row(str(r.get("key", "?")), str(r.get("count", 0)))
    console.print(table)


# ─── RECENT ──────────────────────────────────────────────────────
@cli.command()
@click.option("--limit", default=10, type=int, help="Número de resultados")
def recent(limit):
    """Ver documentos recién indexados."""
    docs = database.get_recent(limit=limit)
    if not docs:
        console.print("[yellow]No hay documentos indexados[/yellow]")
        return

    table = Table(title=f"🕐 Últimos {len(docs)} documentos")
    table.add_column("ID", style="dim", width=6)
    table.add_column("Fecha", style="dim", width=10)
    table.add_column("App", style="cyan", width=12)
    table.add_column("Fuente", style="yellow", width=15)
    table.add_column("Fragmento", width=50)

    for d in docs:
        date = (d.get("indexed_at", ""))[:10]
        frag = _truncate(d.get("content", ""), 50)
        table.add_row(str(d["id"]), date, d.get("app", "-") or "-", d.get("source", "-") or "-", frag)

    console.print(table)


# ─── APPS ────────────────────────────────────────────────────────
@cli.command()
def apps():
    """Listar apps/servicios detectados."""
    app_list = database.get_apps()
    if not app_list:
        console.print("[yellow]No hay apps en la base de datos[/yellow]")
        return

    console.print(Panel("\n".join(f"  • {a}" for a in app_list), title="📦 Apps detectados"))


# ─── SOURCES ─────────────────────────────────────────────────────
@cli.command()
def sources():
    """Listar fuentes configuradas."""
    src_list = database.get_sources()
    if not src_list:
        console.print("[yellow]No hay fuentes indexadas[/yellow]")
        return

    console.print(Panel("\n".join(f"  • {s}" for s in src_list), title="📂 Fuentes indexadas"))


# ─── TAG ─────────────────────────────────────────────────────────
@cli.command()
@click.argument("action", type=click.Choice(["add", "list"]))
@click.argument("tag_name", required=False)
@click.argument("doc_id", type=int, required=False)
def tag(action, tag_name, doc_id):
    """Gestionar tags de documentos."""
    if action == "add" and tag_name and doc_id:
        # Simple tag addition via direct SQL
        conn = database._get_conn()
        row = conn.execute("SELECT tags FROM documents WHERE id = ?", (doc_id,)).fetchone()
        if row:
            existing = row["tags"] or ""
            new_tags = f"{existing},{tag_name}" if existing else tag_name
            conn.execute("UPDATE documents SET tags = ? WHERE id = ?", (new_tags, doc_id))
            conn.commit()
            console.print(f"[green]✅ Tag '{tag_name}' añadido al documento {doc_id}[/green]")
        else:
            console.print(f"[red]Documento {doc_id} no encontrado[/red]")
        conn.close()
    elif action == "list":
        conn = database._get_conn()
        rows = conn.execute("SELECT DISTINCT tags FROM documents WHERE tags IS NOT NULL AND tags != ''").fetchall()
        conn.close()
        all_tags = set()
        for r in rows:
            for t in r["tags"].split(","):
                t = t.strip()
                if t:
                    all_tags.add(t)
        if all_tags:
            console.print(Panel("\n".join(f"  • {t}" for t in sorted(all_tags)), title="🏷️ Tags"))
        else:
            console.print("[yellow]No hay tags[/yellow]")
    else:
        console.print("[yellow]Uso: tag add <tag_name> <doc_id> | tag list[/yellow]")


# ─── EXPORT ──────────────────────────────────────────────────────
@cli.command()
@click.option("--query", help="Consulta de búsqueda para exportar")
@click.option("--format", "fmt", default="csv", type=click.Choice(["csv", "json"]), help="Formato de exportación")
@click.option("--output", default=None, help="Archivo de salida (default: stdout)")
def export(query, fmt, output):
    """Exportar resultados a archivo."""
    if not query:
        console.print("[red]Error: proporciona --query[/red]")
        return

    results = database.search_text(query, limit=1000)

    if fmt == "json":
        content = json.dumps(results, indent=2, ensure_ascii=False, default=str)
    else:
        # CSV
        import csv
        import io
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=["id", "source", "app", "doc_type", "level", "created_at", "content"])
        writer.writeheader()
        for r in results:
            writer.writerow({k: r.get(k, "") for k in writer.fieldnames})
        content = buf.getvalue()

    if output:
        with open(output, "w") as f:
            f.write(content)
        console.print(f"[green]✅ Exportado a {output} ({len(results)} resultados)[/green]")
    else:
        click.echo(content)


if __name__ == "__main__":
    cli()
