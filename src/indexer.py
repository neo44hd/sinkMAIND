"""sinkMAIND indexer — ingests data from all configured sources."""

import json
import os
import re
import subprocess
import sys

import yaml

# Add parent to path so we can import sibling modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import database

CONFIG_PATH = os.path.expanduser("~/sinkia-memory/config.yaml")

# App name detection patterns from paths
APP_PATTERNS = {
    "nginx": "nginx",
    "docker": "docker",
    "pm2": "pm2",
    "cloudflare": "cloudflared",
    "cloudflared": "cloudflared",
    "ollama": "ollama",
    "warp": "warp",
    "claude": "claude",
    "openclaw": "openclaw",
    "sinkia": "sinkia",
    "hermetic": "hermetic-mobile",
    "homebrew": "homebrew",
    "brew": "homebrew",
}

# Category mapping
CATEGORY_MAP = {
    "log": "system",
    "shell": "system",
    "chat": "ai",
    "code": "project",
    "doc": "docs",
    "config": "system",
    "system": "system",
    "report": "docs",
}

# Log level detection
LOG_LEVEL_RE = re.compile(
    r"\b(ERROR|ERR|FATAL|CRITICAL|WARN|WARNING|INFO|DEBUG|TRACE)\b",
    re.IGNORECASE,
)

# Timestamp detection patterns
TIMESTAMP_PATTERNS = [
    re.compile(r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})"),
    re.compile(r"(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})"),
    re.compile(r"(\w{3} \d{1,2} \d{2}:\d{2}:\d{2})"),
    re.compile(r"(\d{4}-\d{2}-\d{2})"),
]


def load_config() -> dict:
    """Load config.yaml."""
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


from typing import List, Optional


def detect_app(path: str) -> str:
    """Detect app name from a file path."""
    path_lower = path.lower()
    for pattern, app in APP_PATTERNS.items():
        if pattern in path_lower:
            return app
    return "unknown"


def detect_level(text: str) -> Optional[str]:
    """Detect log level from text."""
    match = LOG_LEVEL_RE.search(text)
    if match:
        level = match.group(1).upper()
        if level in ("ERR", "FATAL", "CRITICAL"):
            return "error"
        if level in ("WARN", "WARNING"):
            return "warn"
        if level == "INFO":
            return "info"
        if level in ("DEBUG", "TRACE"):
            return "debug"
    return None


def detect_timestamp(text: str) -> Optional[str]:
    """Extract timestamp from a line of text."""
    for pattern in TIMESTAMP_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1)
    return None


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """Split text into overlapping chunks."""
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        # Try to break at sentence/line boundary
        if end < len(text):
            last_newline = chunk.rfind("\n")
            if last_newline > chunk_size // 2:
                chunk = chunk[: last_newline + 1]
                end = start + last_newline + 1
        chunks.append(chunk.strip())
        start = end - overlap
    return [c for c in chunks if c]


def index_log_files(path: str, source_name: str, app: str = None):
    """Index all .log files in a directory."""
    path = os.path.expanduser(path)
    if not os.path.isdir(path):
        print(f"  ⚠ {path} no existe, saltando")
        return 0

    count = 0
    for fname in sorted(os.listdir(path)):
        if not fname.endswith(".log"):
            continue
        fpath = os.path.join(path, fname)
        detected_app = app or detect_app(fname)
        try:
            with open(fpath, "r", errors="replace") as f:
                content = f.read()
        except Exception as e:
            print(f"  ⚠ Error leyendo {fpath}: {e}")
            continue

        # Process line by line for log files
        lines = content.split("\n")
        chunk = []
        chunk_len = 0
        for line in lines:
            chunk.append(line)
            chunk_len += len(line)
            if chunk_len >= 500:
                text = "\n".join(chunk)
                level = detect_level(text)
                ts = detect_timestamp(text[:100]) if chunk else None
                doc_id = database.insert_document(
                    content=text,
                    source=source_name,
                    source_path=fpath,
                    doc_type="log",
                    app=detected_app,
                    category="system",
                    level=level,
                    created_at=ts,
                )
                if doc_id:
                    count += 1
                chunk = []
                chunk_len = 0

        # Remaining
        if chunk:
            text = "\n".join(chunk)
            level = detect_level(text)
            ts = detect_timestamp(text[:100]) if chunk else None
            doc_id = database.insert_document(
                content=text,
                source=source_name,
                source_path=fpath,
                doc_type="log",
                app=detected_app,
                category="system",
                level=level,
                created_at=ts,
            )
            if doc_id:
                count += 1

    return count


def index_shell_history(path: str):
    """Index shell history file."""
    path = os.path.expanduser(path)
    if not os.path.isfile(path):
        print(f"  ⚠ {path} no existe, saltando")
        return 0

    count = 0
    try:
        with open(path, "r", errors="replace") as f:
            for line in f:
                line = line.strip()
                # Skip zsh timestamp lines
                if line.startswith(": ") or not line or line.startswith("#"):
                    continue
                # Clean zsh extended history format
                line = re.sub(r"^: \d+:\d+;", "", line)
                if not line:
                    continue
                doc_id = database.insert_document(
                    content=line,
                    source="zsh-history",
                    source_path=path,
                    doc_type="shell",
                    app="shell",
                    category="system",
                )
                if doc_id:
                    count += 1
    except Exception as e:
        print(f"  ⚠ Error leyendo {path}: {e}")

    return count


def index_directory(path: str, extensions: List[str], source_name: str, doc_type: str = "doc", max_files: int = 500):
    """Index files in a directory recursively."""
    path = os.path.expanduser(path)
    if not os.path.isdir(path):
        print(f"  ⚠ {path} no existe, saltando")
        return 0

    config = load_config()
    chunk_size = config.get("indexing", {}).get("chunk_size", 500)
    chunk_overlap = config.get("indexing", {}).get("chunk_overlap", 50)

    count = 0
    files_processed = 0

    for root, dirs, files in os.walk(path):
        # Skip hidden and common irrelevant dirs
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "__pycache__", ".git", "venv", ".venv")]

        for fname in files:
            if files_processed >= max_files:
                print(f"  ⚠ Límite de {max_files} archivos alcanzado")
                return count

            ext = os.path.splitext(fname)[1].lower()
            if ext not in extensions:
                continue

            fpath = os.path.join(root, fname)
            detected_app = detect_app(fpath)
            category = CATEGORY_MAP.get(doc_type, "docs")

            try:
                # Skip binary files and very large files
                if os.path.getsize(fpath) > 5 * 1024 * 1024:  # 5MB
                    continue
                with open(fpath, "r", errors="replace") as f:
                    content = f.read()
            except Exception:
                continue

            if not content.strip():
                continue

            chunks = chunk_text(content, chunk_size, chunk_overlap)
            for chunk in chunks:
                doc_id = database.insert_document(
                    content=chunk,
                    source=source_name,
                    source_path=fpath,
                    doc_type=doc_type,
                    app=detected_app,
                    category=category,
                )
                if doc_id:
                    count += 1

            files_processed += 1

    return count


def index_command_output(command: str, source_name: str):
    """Execute a command and index its output."""
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=30
        )
        output = result.stdout.strip()
        if not output:
            return 0
    except Exception as e:
        print(f"  ⚠ Error ejecutando '{command}': {e}")
        return 0

    # Split into lines and group into chunks
    lines = output.split("\n")
    chunk = []
    chunk_len = 0
    count = 0

    for line in lines:
        chunk.append(line)
        chunk_len += len(line)
        if chunk_len >= 500:
            text = "\n".join(chunk)
            doc_id = database.insert_document(
                content=text,
                source=source_name,
                source_path=command,
                doc_type="system",
                category="system",
            )
            if doc_id:
                count += 1
            chunk = []
            chunk_len = 0

    if chunk:
        text = "\n".join(chunk)
        doc_id = database.insert_document(
            content=text,
            source=source_name,
            source_path=command,
            doc_type="system",
            category="system",
        )
        if doc_id:
            count += 1

    return count


def index_docker_logs():
    """Index Docker container logs."""
    try:
        result = subprocess.run(
            "docker ps --format '{{.ID}} {{.Names}}'",
            shell=True, capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            print("  ⚠ Docker no disponible")
            return 0
    except Exception:
        print("  ⚠ Docker no disponible")
        return 0

    count = 0
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split(maxsplit=1)
        container_id = parts[0]
        container_name = parts[1] if len(parts) > 1 else container_id

        try:
            result = subprocess.run(
                f"docker logs --tail 200 {container_id}",
                shell=True, capture_output=True, text=True, timeout=15,
            )
            output = result.stdout + result.stderr
            if not output.strip():
                continue
        except Exception:
            continue

        chunks = chunk_text(output, 500, 50)
        for chunk in chunks:
            level = detect_level(chunk)
            doc_id = database.insert_document(
                content=chunk,
                source="docker-logs",
                source_path=f"docker:{container_name}",
                doc_type="log",
                app="docker",
                category="system",
                level=level,
            )
            if doc_id:
                count += 1

    return count


def index_source(source_name: str, source_config: dict) -> int:
    """Index a single source based on its config."""
    source_type = source_config.get("type", "unknown")
    count = 0

    if not source_config.get("enabled", True):
        print(f"  ⊘ {source_name} deshabilitado, saltando")
        return 0

    # Path-based sources
    if "path" in source_config:
        path = source_config["path"]
        if source_type == "log":
            count = index_log_files(path, source_name)
        elif source_type == "shell":
            count = index_shell_history(path)
        elif source_type in ("doc", "code", "config", "chat"):
            extensions = source_config.get(
                "extensions",
                [".md", ".txt", ".py", ".js", ".ts", ".json", ".yaml", ".yml", ".toml"]
                if source_type == "code"
                else [".md", ".txt", ".pdf", ".docx", ".xlsx"],
            )
            count = index_directory(path, extensions, source_name, source_type)
        elif source_type == "system":
            # For system paths, index as text files
            count = index_directory(path, [".json", ".yaml", ".yml", ".txt", ".md", ".plist", ".env"], source_name, source_type)

    # Multi-path sources (like documents)
    elif "paths" in source_config:
        extensions = source_config.get("extensions", [".md", ".txt"])
        for p in source_config["paths"]:
            c = index_directory(p, extensions, source_name, source_type)
            count += c

    # Command-based sources
    elif "commands" in source_config:
        for cmd in source_config["commands"]:
            c = index_command_output(cmd, source_name)
            count += c

    # Docker logs special case
    elif source_name == "docker_logs" or (source_config.get("command", "") == "docker logs"):
        count = index_docker_logs()

    return count


def index_all():
    """Index all enabled sources from config."""
    config = load_config()
    sources = config.get("sources", {})

    print("🧠 sinkMAIND — Indexando fuentes...")
    print()

    total = 0
    for source_name, source_config in sources.items():
        print(f"📂 Indexando {source_name}...", end=" ", flush=True)
        try:
            count = index_source(source_name, source_config)
            print(f"{count} documentos nuevos")
            total += count
        except Exception as e:
            print(f"ERROR: {e}")

    print()
    print(f"✅ Total: {total} documentos nuevos indexados")
    return total


def index_specific(source_name: str):
    """Index a specific source by name."""
    config = load_config()
    sources = config.get("sources", {})

    if source_name not in sources:
        print(f"⚠ Fuente '{source_name}' no encontrada en config.yaml")
        print(f"Fuentes disponibles: {', '.join(sources.keys())}")
        return 0

    print(f"📂 Indexando {source_name}...", end=" ", flush=True)
    count = index_source(source_name, sources[source_name])
    print(f"{count} documentos nuevos")
    return count


if __name__ == "__main__":
    database.init_db()
    if len(sys.argv) > 1:
        index_specific(sys.argv[1])
    else:
        index_all()
