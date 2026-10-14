#!/bin/bash
# Ежедневный полный бэкап прода bn-tora.com на этот Mac.
# Запускается launchd (~/Library/LaunchAgents/com.bn-tora.backup.plist) раз в час
# и при входе в систему; если сегодняшний бэкап уже есть — ничего не делает.
# Хранит 3 последних архива в backups/ (папка в .gitignore).
# В архиве: снимок db.sqlite3 (через sqlite3 .backup), media/, .env, код,
# texts/, конфиг nginx и systemd-юнит.

set -uo pipefail
export PATH=/usr/bin:/bin:/usr/sbin:/sbin

HOST=root@89.108.83.228
REMOTE_DIR=/srv/tora-online
KEEP=3
DIR="$(cd "$(dirname "$0")/.." && pwd)/backups"
LOG="$DIR/backup.log"
TODAY=$(date +%Y-%m-%d)
OUT="$DIR/tora-online-$TODAY.tar.gz"

mkdir -p "$DIR"
log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"; }
notify() { osascript -e "display notification \"$1\" with title \"Бэкап bn-tora.com\"" >/dev/null 2>&1; }

[ "${1:-}" != "--force" ] && [ -s "$OUT" ] && exit 0

REMOTE_CMD='set -e
T=$(mktemp -d); trap "rm -rf $T" EXIT
sqlite3 '"$REMOTE_DIR"'/db.sqlite3 ".backup $T/db.sqlite3"
[ "$(sqlite3 $T/db.sqlite3 "PRAGMA integrity_check;")" = ok ]
tar czf - \
  -C '"$REMOTE_DIR"' --exclude=./venv --exclude=./.cache --exclude=./.gunicorn \
     --exclude=./gunicorn.sock --exclude=./staticfiles --exclude=./db.sqlite3 \
     --exclude="./db.sqlite3.*" . \
  -C "$T" db.sqlite3 \
  -C / etc/nginx/sites-available/bn-tora.com etc/systemd/system/tora-online.service'

# SSH через en0 в обход VPN (см. проблему с РКН); если не вышло — обычным маршрутом.
ok=0
for opts in "-o BindInterface=en0" ""; do
  if ssh $opts -o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=15 \
       "$HOST" "$REMOTE_CMD" > "$OUT.part" 2>>"$LOG" \
     && tar tzf "$OUT.part" db.sqlite3 >/dev/null 2>&1; then
    ok=1; break
  fi
  log "попытка не удалась (${opts:-обычный маршрут})"
done

if [ $ok = 0 ]; then
  rm -f "$OUT.part"
  log "ОШИБКА: бэкап не скачан, повторю через час"
  notify "Не удалось скачать бэкап, повторю через час"
  exit 1
fi

mv "$OUT.part" "$OUT"
log "OK $(basename "$OUT") $(du -h "$OUT" | cut -f1)"

# Оставить только $KEEP последних архивов.
ls -1t "$DIR"/tora-online-*.tar.gz | tail -n +$((KEEP + 1)) | while read -r f; do
  rm -f "$f"; log "удалён старый $(basename "$f")"
done
