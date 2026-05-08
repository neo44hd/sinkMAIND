#!/bin/bash
# sinkMAIND — setup cron for automatic indexing every 30 minutes
CRON_JOB="*/30 * * * * /bin/bash $HOME/sinkia-memory/scripts/index_now.sh"
(crontab -l 2>/dev/null | grep -v "sinkia-memory"; echo "$CRON_JOB") | crontab -
echo "Cron configurado: indexación cada 30 minutos"
crontab -l | grep sinkia-memory
