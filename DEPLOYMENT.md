# sinkMAIND — Despliegue en Producción

## Resumen

Sistema de memoria retroactiva que indexa y busca (textual, semántica, híbrida) sobre logs, chats, código, configuraciones y documentos. Integrado con Mission Control vía tarjeta 🧠 en el dashboard.

**Estado**: 91,467 documentos · 100% embeddings (768-dim) · 1.1 GB

## Arquitectura

```
Tailscale (100.78.4.14:3030)
  └─ Mission Control (Node/Express, pm2)
       ├── / → Dashboard principal (tarjeta 🧠 sinkMAIND)
       ├── /memory → Dashboard interactivo de búsqueda
       └── /api/memory/* → API bridge (execFile → CLI)
             └─ sinkMAIND CLI (Python/Click/Rich)
                  └─ SQLite FTS5 + Ollama embeddings (nomic-embed-text)
```

## Requisitos

- macOS, Python 3.9+, Node.js 25+, Ollama 0.22+
- Tailscale con IP fija
- pm2 global (`npm i -g pm2`)

## Instalación

```bash
git clone https://github.com/neo44hd/sinkMAIND.git ~/sinkia-memory
cd ~/sinkia-memory
pip3 install -r requirements.txt
chmod +x memory
```

## Primera indexación

```bash
# Inicializar DB e indexar fuentes
./memory index --all

# Generar embeddings (~33 min para 91K docs)
./memory index --embeddings --max-docs 5000 --embed-batch 50
```

## Indexación automática (cron)

```bash
bash ~/sinkia-memory/scripts/setup_cron.sh
# Instala: */30 * * * * /bin/bash ~/sinkia-memory/scripts/index_now.sh
```

## Mission Control

Archivos de integración:
- `server.js` → importa `registerMemoryRoutes`
- `lib/memory-api.js` → puente CLI ↔ API REST
- `lib/auth.js` → Basic Auth + sesiones cookie
- `public/memory.html` → dashboard interactivo
- `public/index.html` → tarjeta 🧠 en dashboard principal
- `public/app.js` → carga stats de memoria al iniciar

```bash
cd ~/mission-control && npm install
pm2 start ~/mission-control/server.js --name mission-control
pm2 save
```

### Autenticación (.env)

```
APP_HOST=100.78.4.14
APP_PORT=3030
AUTH_USER=admin
AUTH_PASS=<contraseña>
```

- Auth off si AUTH_PASS vacío
- Localhost siempre sin auth
- Sesiones cookie HttpOnly 24h

## Uso CLI

```bash
./memory search "docker error" --limit 10          # Textual
./memory search "problemas de red" --semantic       # Semántica
./memory search "deploy" --hybrid                   # Híbrida (mejor precisión)
./memory search "error" --app docker --level error  # Con filtros
./memory stats --by-app                             # Estadísticas
./memory recent --limit 5                           # Últimos indexados
```

## Uso API

```bash
curl -u admin:<pass> 'http://100.78.4.14:3030/api/memory/stats'
curl -u admin:<pass> 'http://100.78.4.14:3030/api/memory/search?query=docker&hybrid=1&limit=5'
curl -u admin:<pass> 'http://100.78.4.14:3030/api/memory/apps'
curl -u admin:<pass> 'http://100.78.4.14:3030/api/memory/sources'
```

## Seguridad

- Server vinculado solo a IP Tailscale
- Basic Auth + sesiones cookie HttpOnly
- Cloudflare tunnel NO expone Mission Control
- Ollama solo en localhost:11434

## Mantenimiento

```bash
./memory index --all                                          # Re-indexar
./memory index --embeddings --max-docs 5000 --embed-batch 50  # Nuevos embeddings
./memory stats                                                # Verificar integridad
cp ~/sinkia-memory/data/memory.db ~/sinkia-memory/data/memory.db.bak  # Backup
```

## Fuentes indexadas (14)

| Fuente | Tipo | Contenido |
|---|---|---|
| pm2_logs | log | cloudflared, mission-control, sinkia-api |
| docker_logs | log | Contenedores Docker |
| zsh_history | shell | Historial de comandos |
| claude_data | chat | Conversaciones Claude Code |
| warp_data | chat | Sesiones Warp/Oz |
| sinkia_project | code | Código SynK-IA |
| hermetic_mobile | code | Código Hermetic Mobile |
| local_claude_code | code | Local Claude Code |
| documents | doc | Documents, Desktop, Downloads |
| apps | system | Aplicaciones instaladas |
| services | system | pm2, docker, brew services |
| openclaw | system | Config OpenClaw |
| skills | config | Skills Claude Code |
| launch_agents | config | LaunchAgents macOS |
| cloudflare_tunnel | config | Config Cloudflare |

## Resolución de problemas

**Ollama no responde**: `ollama serve && ollama pull nomic-embed-text`

**Semántica irrelevante**: Usar `--app <nombre>` o `--hybrid` para mejor precisión

**DB corrupta**: `cp ~/sinkia-memory/data/memory.db.bak ~/sinkia-memory/data/memory.db`

**Tarjeta no aparece**: `pm2 restart mission-control`
