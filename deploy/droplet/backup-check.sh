#!/usr/bin/env bash
# Pemeriksa backup — jaring pengaman untuk kegagalan yang TIDAK BISA dilaporkan
# backup.sh sendiri: cron mati, script terhapus, droplet reboot dan cron tak
# pernah jalan. Dalam kasus itu backup.sh tidak pernah dipanggil, jadi tidak ada
# yang mengirim peringatan. Pemeriksa ini yang menyadarinya.
#
# Dijalankan cron beberapa jam SESUDAH jadwal backup.

set -Eeuo pipefail

BASE=/opt/autoerp
STATUS=/var/log/autoerp/backup.status
LOG=/var/log/autoerp/backup.log
MAKS_JAM="${MAKS_JAM:-30}"   # 24 jam + kelonggaran; di bawah ini dianggap wajar

# shellcheck disable=SC1091
[ -f "${BASE}/.backup-env" ] && { set -a; . "${BASE}/.backup-env"; set +a; }

lapor() {
  logger -t autoerp-backup-check -p user.err "$1"
  echo "$(date '+%Y-%m-%d %H:%M:%S') CEK: $1" >> "$LOG"
  [ -n "${ALERT_WEBHOOK:-}" ] || return 0
  curl -fsS -m 15 -H 'Content-Type: application/json' \
    --data-raw "{\"content\": \"$1\"}" "$ALERT_WEBHOOK" >/dev/null 2>&1 || true
}

if [ ! -f "$STATUS" ]; then
  lapor "Backup AutoERP: berkas status tidak ada — backup belum pernah jalan?"
  exit 1
fi

isi="$(cat "$STATUS")"
case "$isi" in
  GAGAL*) lapor "Backup AutoERP: jalan terakhir GAGAL — ${isi}"; exit 1 ;;
esac

# Tua = cron tidak jalan. Ini kegagalan yang paling sunyi dan paling berbahaya.
umur_detik=$(( $(date +%s) - $(stat -c %Y "$STATUS") ))
umur_jam=$(( umur_detik / 3600 ))
if [ "$umur_jam" -gt "$MAKS_JAM" ]; then
  lapor "Backup AutoERP: sukses terakhir ${umur_jam} jam lalu (batas ${MAKS_JAM}) — cron mati?"
  exit 1
fi

echo "OK: ${isi} (${umur_jam} jam lalu)"
