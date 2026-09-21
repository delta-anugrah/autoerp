#!/usr/bin/env bash
# Backup harian AutoERP: dump di dalam container -> R2 -> buang yang tua.
#
# Dijalankan cron sebagai `deploy`. Kredensial di /opt/autoerp/.backup-env (chmod 600),
# sengaja TERPISAH dari .env supaya workflow deploy tidak menimpanya.
#
# Prinsip: gagal itu harus berisik dan berhenti, bukan diam dan setengah jalan.
# Yang paling berbahaya bukan backup gagal, tapi backup yang DIKIRA jalan.

set -Eeuo pipefail

BASE=/opt/autoerp
COMPOSE="docker compose -f ${BASE}/docker-compose.prod.yml"
LOG=/var/log/autoerp/backup.log

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*"; }

STATUS=/var/log/autoerp/backup.status   # baris tunggal: hasil jalan terakhir

# Satu tempat untuk semua pemberitahuan. `logger` selalu jalan (masuk journalctl,
# nol konfigurasi); webhook opsional — kosongkan ALERT_WEBHOOK di .backup-env
# kalau kanalnya belum ada, sisanya tetap berfungsi.
beritahu() {
  logger -t autoerp-backup -p user.err "$1" || true
  [ -n "${ALERT_WEBHOOK:-}" ] || return 0
  curl -fsS -m 15 -H 'Content-Type: application/json' \
    --data-raw "{\"content\": \"$1\"}" "$ALERT_WEBHOOK" >/dev/null 2>&1 \
    || log "peringatan: webhook tidak terkirim"
}

# Gagal harus berisik. Tanpa ini cron gagal dalam diam dan baru ketahuan
# berbulan-bulan kemudian, tepat saat backup-nya paling dibutuhkan.
gagal() {
  local code=$? baris=$1
  log "GAGAL di baris ${baris} (exit ${code})"
  echo "GAGAL $(date '+%Y-%m-%d %H:%M:%S') baris ${baris} exit ${code}" > "$STATUS"
  beritahu "Backup AutoERP GAGAL di baris ${baris} (exit ${code}). Lihat ${LOG}"
}
trap 'gagal $LINENO' ERR

exec >>"$LOG" 2>&1
log "=== mulai ==="

# shellcheck disable=SC1091
set -a; . "${BASE}/.backup-env"; set +a

: "${R2_ACCOUNT_ID:?belum diisi di .backup-env}"
: "${R2_ACCESS_KEY_ID:?belum diisi di .backup-env}"
: "${R2_SECRET_ACCESS_KEY:?belum diisi di .backup-env}"
: "${R2_BUCKET:?belum diisi di .backup-env}"
: "${SITE_NAME:?belum diisi di .backup-env}"
KEEP_DAYS="${KEEP_DAYS:-14}"

export RCLONE_CONFIG=""  # jangan pakai ~/.config/rclone, semua lewat env
export RCLONE_CONFIG_R2_TYPE=s3
export RCLONE_CONFIG_R2_PROVIDER=Cloudflare
export RCLONE_CONFIG_R2_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID"
export RCLONE_CONFIG_R2_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY"
export RCLONE_CONFIG_R2_ENDPOINT="https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
# R2 tidak punya ACL; tanpa ini rclone mengirim header yang ditolak.
export RCLONE_CONFIG_R2_NO_CHECK_BUCKET=true
export RCLONE_CONFIG_R2_ACL=private
# Sesudah unggah, rclone menyetel mtime dengan CopyObject ke objek itu sendiri
# (`x-amz-copy-source` + `metadata-directive: REPLACE`). R2 tidak punya
# CopyObject dan menjawab 501, lalu rclone menganggap SELURUH percobaan gagal
# dan mengulang — unggahannya sendiri sebenarnya sudah berhasil sejak awal.
# Terbukti dari `--dump headers` 2026-09-21, bukan dugaan. Nama berkas sudah
# memuat stempel waktu, jadi mtime objek tidak dipakai siapa pun.
export RCLONE_CONFIG_R2_NO_HEAD=true

# --- 1. dump ---------------------------------------------------------------
# --with-files ikut menyertakan lampiran (private + public files).
log "bench backup ${SITE_NAME}"
$COMPOSE exec -T backend bench --site "$SITE_NAME" backup --with-files

# Nama berkas dipilih backend, bukan ditebak: ambil yang paling baru.
STAMP="$($COMPOSE exec -T backend bash -c \
  "ls -1t sites/${SITE_NAME}/private/backups/*-database.sql.gz | head -1" | tr -d '\r')"
[ -n "$STAMP" ] || { log "FATAL: bench backup tidak menghasilkan dump"; exit 1; }
PREFIX="$(basename "$STAMP" -database.sql.gz)"
log "dump: ${PREFIX}"

# --- 2. tarik keluar container --------------------------------------------
# Volume sites di-mount di container; disalin ke host dulu supaya rclone
# tidak perlu tahu apa-apa soal docker.
STAGE="$(mktemp -d /tmp/autoerp-backup.XXXXXX)"
trap 'rm -rf "$STAGE"' EXIT

for suffix in database.sql.gz site_config_backup.json files.tar private-files.tar; do
  src="sites/${SITE_NAME}/private/backups/${PREFIX}-${suffix}"
  if $COMPOSE exec -T backend test -f "$src" 2>/dev/null; then
    $COMPOSE exec -T backend cat "$src" > "${STAGE}/${PREFIX}-${suffix}"
    log "  ambil ${suffix} ($(stat -c%s "${STAGE}/${PREFIX}-${suffix}") byte)"
  fi
done

# Dump kosong = backup yang tidak menyelamatkan apa pun. Lebih baik gagal keras.
DBFILE="${STAGE}/${PREFIX}-database.sql.gz"
[ -s "$DBFILE" ] || { log "FATAL: dump database kosong"; exit 1; }
gzip -t "$DBFILE" || { log "FATAL: dump database korup (gzip -t gagal)"; exit 1; }
log "dump utuh: $(stat -c%s "$DBFILE") byte"

# --- 3. kirim ke R2 --------------------------------------------------------
DEST="r2:${R2_BUCKET}/$(date +%Y/%m)/${PREFIX}"
log "kirim ke ${DEST}"
rclone copy "$STAGE" "$DEST" --s3-no-check-bucket --no-update-modtime --stats-one-line

# Baca balik dari R2 — kalau tidak diperiksa, ini cuma harapan.
REMOTE_N="$(rclone lsf "$DEST" | wc -l)"
LOCAL_N="$(find "$STAGE" -type f | wc -l)"
[ "$REMOTE_N" -eq "$LOCAL_N" ] || { log "FATAL: R2 ${REMOTE_N} berkas, lokal ${LOCAL_N}"; exit 1; }
log "terverifikasi: ${REMOTE_N} berkas di R2"

# --- 4. buang yang tua -----------------------------------------------------
# Di R2 dan di dalam container. Tanpa ini disk droplet pelan-pelan penuh.
rclone delete "r2:${R2_BUCKET}" --min-age "${KEEP_DAYS}d" --rmdirs || \
  log "peringatan: pembersihan R2 tidak tuntas"

$COMPOSE exec -T backend bash -c \
  "find sites/${SITE_NAME}/private/backups -type f -mtime +${KEEP_DAYS} -delete" || \
  log "peringatan: pembersihan dump lokal tidak tuntas"

echo "OK $(date '+%Y-%m-%d %H:%M:%S') ${PREFIX}" > "$STATUS"
log "=== selesai: ${PREFIX} ==="
