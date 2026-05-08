# sinkMAIND

Sistema de memoria retroactiva con búsqueda inteligente para SynK-IA.

Indexa automáticamente logs, chats, documentos, apps y servicios del Mac mini con búsqueda textual (SQLite FTS5) y semántica (Ollama embeddings). Todo funciona 100% offline/local, sin dependencias de APIs externas.

## Qué hace

- Indexa **15 fuentes de datos** del sistema (logs, chats, código, documentos, apps, servicios)
- Búsqueda **textual** instantánea con SQLite FTS5
- Búsqueda **semántica** con embeddings locales de Ollama
- Búsqueda **híbrida** que fusiona ambos métodos (Reciprocal Rank Fusion)
- **12 filtros combinables**: fecha, app, tipo, categoría, severidad, ruta, tags...
- **4 formatos de salida**: tabla, JSON, detalle, breve
- **Indexación automática** cada 30 minutos vía cron
- **Deduplicación** por hash SHA256 — no indexa lo mismo dos veces
- **Detección automática** de app, nivel de log y timestamps

## Requisitos

- Python 3.9+
- Ollama (con modelo `nomic-embed-text` para búsqueda semántica)
- SQLite3 con soporte FTS5 (incluido en macOS)

## Instalación rápida

```bash
git clone https://github.com/neo44hd/sinkMAIND.git
cd sinkMAIND
pip3 install -r requirements.txt
```

Inicializar la base de datos y primer indexado:

```bash
./memory index --all
```

Configurar alias global y cron automático:

```bash
# Alias para usar 'memory' desde cualquier directorio
echo 'alias memory="~/sinkia-memory/memory"' >> ~/.zshrc
source ~/.zshrc

# Indexación automática cada 30 minutos
./scripts/setup_cron.sh
```

## Comandos disponibles

### `memory search` — Búsqueda

Búsqueda textual, semántica o híbrida con filtros avanzados.

```bash
# Búsqueda textual básica
memory search "error"

# Búsqueda semántica (entiende el significado, no solo la palabra exacta)
memory search --semantic "problemas de conexión"

# Búsqueda híbrida (fusiona textual + semántica)
memory search --hybrid "configuración del túnel de cloudflare"
```

#### Filtros de búsqueda

| Flag | Descripción | Valores |
|------|-------------|---------|
| `--app` | Filtrar por aplicación | docker, pm2, warp, claude, nginx, ollama, openclaw, sinkia, cloudflared, shell |
| `--type` | Filtrar por tipo de fuente | log, chat, doc, config, code, report, system, shell |
| `--cat` | Filtrar por categoría | system, ai, network, project, docs |
| `--level` | Filtrar por severidad (logs) | error, warn, info, debug |
| `--since` | Fecha inicio | YYYY-MM-DD |
| `--until` | Fecha fin | YYYY-MM-DD |
| `--today` | Solo hoy | (flag, sin valor) |
| `--this-week` | Últimos 7 días | (flag, sin valor) |
| `--this-month` | Últimos 30 días | (flag, sin valor) |
| `--path` | Filtrar por ruta de archivo | texto parcial, ej: "sinkia/" |
| `--tag` | Filtrar por tag | texto del tag |
| `--sort` | Ordenar resultados | relevance (default), date |
| `--limit` | Máximo resultados | número (default: 20) |
| `--format` | Formato de salida | table (default), json, detail, brief |

#### Ejemplos de búsqueda con filtros

```bash
# Errores de Docker
memory search "error" --app docker

# Solo logs con nivel error hoy
memory search "error" --type log --level error --today

# Código de deploy en el proyecto Sinkia desde marzo
memory search "deploy" --type code --since 2025-03-01

# Errores del servidor esta semana, ordenados por fecha
memory search "error" --this-week --sort date

# Configuraciones de Ollama en formato detallado
memory search "ollama" --type config --format detail

# Búsqueda semántica filtrada por app
memory search --semantic "problemas de memoria" --app pm2 --this-month

# Búsqueda híbrida con múltiples filtros
memory search --hybrid "ssl" --type log --app nginx --limit 5 --format json

# Exportar resultados a JSON
memory search "docker" --format json > docker_results.json
```

#### Formatos de salida

**table** (default) — Tabla con columnas Fecha, App, Tipo, Level, Fuente, Fragmento:

```
🔍 Resultados: 3 encontrados
┏━━━━━━━┳━━━━━━━━━┳━━━━━━┳━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┓
┃ Fecha ┃ App     ┃ Tipo ┃ Level ┃ Fuente      ┃ Fragmento            ┃
┡━━━━━━━╇━━━━━━━━━╇━━━━━━╇━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━┩
│ 2026… │ docker  │ log  │ error │ docker-logs │ FATAL: role "root"…  ┃
└───────┴─────────┴──────┴───────┴─────────────┴──────────────────────┘
```

**brief** — Una línea por resultado:

```
  2026-05-08 docker-logs   FATAL: role "root" does not exist...
  2026-05-08 pm2_logs      [AIDEN] Error: connection refused...
```

**detail** — Panel completo con contenido expandido:

```
╭─────────────────── docker-logs • docker • log ───────────────────╮
│ 2026-05-06 13:26:41 FATAL:  role "root" does not exist          │
│ 2026-05-06 13:26:41 FATAL:  role "postgres" does not exist      │
╰────── 📅 None | 📂 docker:synkia-v3-postgres | 🏷️ None ──────────╯
```

**json** — Array JSON con todos los campos, ideal para integraciones:

```json
[{"id": 123, "content": "...", "source": "docker-logs", "app": "docker", ...}]
```

### `memory index` — Indexación

Indexa fuentes de datos en la base de datos.

```bash
# Indexar todas las fuentes habilitadas
memory index --all

# Indexar una fuente específica
memory index --source pm2_logs
memory index --source docker_logs
memory index --source zsh_history

# Ver qué fuentes están configuradas
memory index --status

# Generar embeddings para búsqueda semántica
memory index --embeddings
```

### `memory stats` — Estadísticas

Muestra estadísticas de la base de datos.

```bash
# Total de documentos
memory stats

# Desglose por aplicación
memory stats --by-app

# Desglose por tipo de fuente
memory stats --by-type

# Desglose por fuente
memory stats --by-source
```

### `memory recent` — Documentos recientes

Muestra los últimos documentos indexados.

```bash
# Últimos 10 (default)
memory recent

# Últimos 20
memory recent --limit 20
```

### `memory apps` — Apps detectadas

Lista las aplicaciones/servicios detectados en la base de datos.

```bash
memory apps
```

### `memory sources` — Fuentes indexadas

Lista las fuentes de datos que tienen documentos indexados.

```bash
memory sources
```

### `memory tag` — Gestión de tags

Añade o lista tags manuales en documentos.

```bash
# Añadir tag a un documento
memory tag add "deployment" 42

# Listar todos los tags existentes
memory tag list
```

### `memory export` — Exportar resultados

Exporta resultados de búsqueda a archivo.

```bash
# Exportar a CSV
memory export --query "docker" --output docker_results.csv

# Exportar a JSON
memory export --query "error" --format json --output errors.json

# Exportar a stdout
memory export --query "nginx"
```

## Fuentes de datos

| Fuente | Tipo | Categoría | Descripción |
|--------|------|-----------|-------------|
| pm2_logs | log | system | Logs de servicios gestionados con PM2 |
| docker_logs | log | system | Logs de contenedores Docker activos |
| zsh_history | shell | system | Historial de comandos del terminal |
| claude_data | chat | ai | Conversaciones, configs y skills de Claude Code |
| warp_data | chat | ai | Chats con Oz y datos de Warp |
| sinkia_project | code | project | Código fuente del proyecto SynK-IA |
| hermetic_mobile | code | project | Proyecto Hermetic Mobile |
| local_claude_code | code | project | Fork local de Claude Code |
| documents | doc | docs | Documentos en ~/Documents, ~/Desktop, ~/Downloads |
| apps | system | system | Lista de apps instaladas (Applications + brew) |
| services | system | system | Estado de servicios (pm2, docker, brew) |
| openclaw | system | system | Configuración y datos de OpenClaw |
| skills | config | system | Skills de Claude Code |
| launch_agents | config | system | LaunchAgents de macOS |
| cloudflare_tunnel | config | system | Configuración del túnel Cloudflare |

### Añadir nuevas fuentes

Editar `config.yaml` para añadir una fuente:

```yaml
sources:
  mi_nueva_fuente:
    path: "~/mi-proyecto/"
    type: code          # log, shell, chat, code, doc, config, system
    enabled: true
```

Tipos de fuente soportados:
- **log**: lee archivos `.log` línea a línea, detecta nivel y timestamp
- **shell**: lee historial de shell, limpia formato zsh
- **chat**: indexa directorio como archivos de texto
- **code**: indexa archivos `.py`, `.js`, `.ts`, `.json`, `.yaml`, `.yml`, `.toml`
- **doc**: indexa archivos `.md`, `.txt`, `.pdf`, `.docx`, `.xlsx`
- **config**: indexa archivos de configuración
- **system**: ejecuta comandos o lee archivos de sistema

Para fuentes basadas en comandos:

```yaml
  estado_red:
    commands:
      - "netstat -an | grep LISTEN"
      - "ifconfig | grep inet"
    type: system
    enabled: true
```

## Arquitectura

```
sinkia-memory/
├── README.md
├── requirements.txt
├── config.yaml              # Fuentes, DB, embeddings, indexación
├── memory                   # Script ejecutable (CLI wrapper)
├── src/
│   ├── __init__.py
│   ├── database.py           # SQLite FTS5 + embeddings store
│   ├── indexer.py            # Ingesta de todas las fuentes
│   ├── embeddings.py         # Ollama embeddings + cosine similarity
│   ├── search.py             # Búsqueda textual + semántica + híbrida
│   └── cli.py                # CLI con click + rich
├── scripts/
│   ├── index_now.sh          # Indexación manual (para cron)
│   └── setup_cron.sh         # Configurar cron cada 30 min
├── data/                     # Base de datos SQLite (gitignored)
│   └── memory.db
└── tests/
    └── test_search.py
```

### Motor de búsqueda

1. **Textual** — SQLite FTS5 con índice invertido. Match instantáneo en `documents_fts`. Fallback a LIKE si la query FTS tiene sintaxis inválida.

2. **Semántica** — Genera embedding del query via Ollama (`nomic-embed-text`), calcula similitud coseno contra todos los embeddings almacenados, retorna los top-N más similares.

3. **Híbrida** — Ejecuta ambas búsquedas, fusiona con Reciprocal Rank Fusion (k=60), retorna resultados combinados ordenados por score.

### Deduplicación

Cada documento genera un `content_hash` (SHA256). Si el hash ya existe en la DB, el documento se ignora. Esto permite re-indexar sin duplicar.

### Detección automática

- **App**: detectada automáticamente desde la ruta del archivo (ej: ruta contiene "docker" → app=docker)
- **Nivel de log**: regex que busca ERROR/WARN/INFO/DEBUG/FATAL en el contenido
- **Timestamp**: regex que busca formatos ISO, syslog, etc. en las primeras líneas
- **Categoría**: mapeada automáticamente desde el tipo de fuente (log→system, chat→ai, code→project...)

## Configuración

### config.yaml

```yaml
# Fuentes de datos
sources:
  pm2_logs:
    path: "~/.pm2/logs/"
    type: log
    enabled: true          # poner false para deshabilitar

# Base de datos
database:
  path: "~/sinkia-memory/data/memory.db"

# Embeddings
embeddings:
  provider: ollama
  url: "http://localhost:11434"
  model: "nomic-embed-text"

# Parámetros de indexación
indexing:
  interval_minutes: 30     # para referencia del cron
  chunk_size: 500          # caracteres por chunk
  chunk_overlap: 50        # solapamiento entre chunks
```

### Embeddings (búsqueda semántica)

Para habilitar la búsqueda semántica:

```bash
# Descargar modelo de embeddings
ollama pull nomic-embed-text

# Generar embeddings para documentos existentes
memory index --embeddings
```

Nota: con `OLLAMA_NUM_PARALLEL=1` y `OLLAMA_MAX_LOADED_MODELS=1`, la generación de embeddings se hace secuencialmente sin saturar el servidor.

### Cron (indexación automática)

```bash
# Configurar
cat scripts/setup_cron.sh
# Ejecutar
./scripts/setup_cron.sh

# Verificar
crontab -l | grep sinkia-memory

# Quitar
crontab -l | grep -v sinkia-memory | crontab -
```

## Interfaz gráfica (Mission Control)

sinkMAIND está integrado en el dashboard de Mission Control. Accede desde:

```
http://127.0.0.1:3030/memory
```

Funciones disponibles en la UI:
- Búsqueda textual, semántica e híbrida con un click
- Filtros por app, tipo, nivel, fecha
- Tarjetas de resultados expandibles con click
- Barra de estadísticas en tiempo real (total, logs, chats, code, docs, shell)
- Pestañas: Buscar / Estadísticas / Fuentes
- Botón de re-indexación

## Licencia

MIT
