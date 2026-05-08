# sinkMAIND

Sistema de memoria retroactiva con búsqueda inteligente para SynK-IA.

Indexa automáticamente logs, chats, documentos, apps y servicios del Mac mini con búsqueda textual (SQLite FTS5) y semántica (Ollama embeddings).

## Requisitos

- Python 3.9+
- Ollama (con modelo `nomic-embed-text` para búsqueda semántica)
- SQLite3 con FTS5

## Instalación

```bash
pip3 install -r requirements.txt
```

## Uso

```bash
# Indexar todas las fuentes
./memory index --all

# Buscar texto
./memory search "error"

# Buscar por app
./memory search "docker" --app docker

# Buscar con filtros combinados
./memory search "error" --app pm2 --type log --level error --since 2025-03-01

# Búsqueda semántica (requiere Ollama + nomic-embed-text)
./memory search --semantic "problemas de conexión"

# Búsqueda híbrida
./memory search --hybrid "configuración del túnel"

# Ver estadísticas
./memory stats
./memory stats --by-app
./memory stats --by-type

# Documentos recientes
./memory recent

# Apps detectadas
./memory apps

# Fuentes configuradas
./memory sources

# Indexación periódica (cada 30 min)
./scripts/setup_cron.sh
```

## Fuentes de datos

| Fuente | Tipo | Descripción |
|--------|------|-------------|
| pm2_logs | log | Logs de servicios PM2 |
| docker_logs | log | Logs de contenedores Docker |
| zsh_history | shell | Historial de comandos |
| claude_data | chat | Conversaciones y configs de Claude Code |
| warp_data | chat | Chats de Warp/Oz |
| sinkia_project | code | Código del proyecto SynK-IA |
| hermetic_mobile | code | Proyecto Hermetic Mobile |
| local_claude_code | code | Fork local de Claude Code |
| documents | doc | Documentos (.md, .txt, .pdf, .docx, .xlsx) |
| apps | system | Lista de apps instaladas |
| services | system | Estado de servicios activos |
| openclaw | system | Config y datos de OpenClaw |
| skills | config | Skills de Claude Code |
| launch_agents | config | LaunchAgents de macOS |
| cloudflare_tunnel | config | Config del túnel Cloudflare |

## Filtros de búsqueda

- `--app` — por app (docker, pm2, warp, claude, nginx, ollama...)
- `--type` — por tipo (log, chat, doc, config, code, report, system)
- `--cat` — por categoría (system, ai, network, project, docs)
- `--level` — por severidad (error, warn, info, debug)
- `--since` / `--until` — rango de fechas (YYYY-MM-DD)
- `--today` / `--this-week` / `--this-month` — atajos de fecha
- `--path` — filtrar por ruta de archivo
- `--tag` — filtrar por tag
- `--sort` — ordenar por relevance o date
- `--limit` — máximo resultados (default: 20)
- `--format` — table, json, detail, brief

## Configuración

Editar `config.yaml` para añadir/quitar fuentes o cambiar parámetros de indexación.

## Licencia

MIT
