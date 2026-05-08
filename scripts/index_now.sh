#!/bin/bash
# sinkMAIND — manual indexing
export PATH="/opt/homebrew/bin:$PATH"
cd "$HOME/sinkia-memory"
python3 src/cli.py index --all >> "$HOME/sinkia-memory/data/indexing.log" 2>&1
echo "[$(date)] Indexación completada" >> "$HOME/sinkia-memory/data/indexing.log"
