---
name: server-droplet-prod
description: Isi sebenarnya droplet produksi `autoerp-prod` (188.166.178.75) — spek, container, volume, port, nginx, sertifikat, firewall, jalur berkas, dan jejak api/frontend yang dipensiunkan. Pakai kalau lagi deploy/rollback ke droplet, menaksir "muat nggak di RAM segitu", mencari nama container atau jalur `.env`, menyiapkan nginx untuk domain baru, mendiagnosis "kenapa 502"/"disk penuh"/"kok mati", atau butuh fakta server apa pun — JANGAN menebak dan JANGAN tanya user duluan, baca ini dulu.
---

# Droplet produksi — `autoerp-prod`

⚠️ **Salinan.** Aslinya di repo `sawit` (workspace internal), `.claude/skills/
server-droplet-prod/`. Droplet ini melayani AutoERP, jadi salinannya ada di sini
supaya yang bekerja dari checkout autoerp saja tidak perlu menebak fakta server.
**Kalau diubah, ubah di kedua tempat** — isi yang bercabang lebih berbahaya
daripada tidak ada sama sekali, karena dua-duanya terbaca meyakinkan.

Angka di sini **hasil baca langsung di mesinnya**, bukan taksiran. Dipakai untuk
menjawab "muat nggak", "namanya apa", "di mana berkasnya" tanpa menebak dan tanpa
membebani user dengan pertanyaan yang jawabannya sudah ada.

> **Diukur: 2026-09-20 19:00 WIB**, di tengah Fase B (deploy AutoERP).
> Cara ukur ulang ada di bagian terakhir. **Kalau tanggal di atas lebih dari ~2
> bulan, ukur ulang sebelum memakai angka RAM/disk.**

## Ringkas

| | |
|---|---|
| Nama / IP | `autoerp-prod` / `188.166.178.75` (DigitalOcean, SGP1) |
| Alias SSH | `ssh autoerpprod` (`autoerpprodroot` untuk root) |
| OS | Ubuntu **24.04.4 LTS**, kernel 6.8.0-139 |
| CPU / RAM | **2 vCPU / 3.8 GB**, **tanpa swap** |
| Disk | **48 GB**, terpakai ~11 GB, sisa ~38 GB |
| Akses | SSH sebagai `deploy`. `sudo` minta sandi. |
| Firewall | UFW aktif — **hanya** OpenSSH, 80/tcp, 443/tcp |

⚠️ **Nama lama `palmgrade-prod` masih muncul di mana-mana** — jalur `/opt/palmgrade-*`,
volume `palmgrade-api_*`, container `palmgrade_*`, alias SSH `palmgradeprod`, dan
berkas kunci `~/.ssh/palmgrade_prod`. Yang berubah 2026-09-20 hanya nama droplet,
hostname, dan alias SSH baru. Alias lama sengaja **tidak** dihapus.

⚠️ **Di-resize 2026-09-20** dari 1 vCPU / 2 GB. Kotak "Downscale anytime" **dicentang**,
jadi disk ditahan di 50 GB dan ukurannya masih bisa diturunkan lagi. Tanpa centang itu
disk jadi 80 GB dan permanen.

## Yang jalan sekarang

| Container | Status |
|---|---|
| `portainer` | **Up** — satu-satunya yang hidup |
| `palmgrade_frontend` | **Stopped** (`v1.8.0`) |
| `palmgrade_api` | **Stopped** (`v1.17.0`) |
| `palmgrade_postgres` | **Stopped** (`postgres:16-alpine`) |
| `palmgrade_mongo` | **Stopped** (`mongo:7.0`) |

Keempatnya di-**`stop`** 2026-09-20 karena AutoERP mengambil alih `app.smagri.id`.
`stop`, bukan `down -v`: **volumenya utuh** dan bisa dinyalakan lagi dengan `start`.

⚠️ **Nama container pakai underscore** dan **tidak** sama dengan dev compose (yang
menamai api `palmgrade_backend`). Compose produksi hidup di host, bukan di repo —
target `docker exec` **tidak bisa ditebak dari checkout lokal**. Selalu:

```bash
docker ps -a --format '{{.Names}}\t{{.Status}}\t{{.Image}}'
```

**Tidak ada container yang menghadap internet.** Semua bind ke `127.0.0.1`; nginx
milik host yang menerima 80/443. Pertahankan pola ini.

## Jalur berkas

| | |
|---|---|
| **AutoERP** | `/opt/autoerp/` — `.env` + `docker-compose.prod.yml` |
| api (pensiun) | `/opt/palmgrade-api/` |
| frontend (pensiun) | `/opt/palmgrade-frontend/` |
| nginx | `/etc/nginx/sites-available/palmgrade.conf` → symlink di `sites-enabled/` |

⚠️ **Jalur droplet ≠ jalur PC pabrik.** Di pabrik semuanya di bawah satu induk
(`/opt/palmgrade/autograde/`). Di droplet terpisah per layanan. Salah jalur =
mengedit `.env` yang tidak dibaca siapa pun.

Droplet **runtime-only**: tidak ada source code, tidak ada `git clone`, dan **tidak ada
`gh`**. Menarik berkas dari repo privat lewat `curl` ke raw.githubusercontent **gagal 404**;
salurkan dari laptop: `git show origin/main:<path> | ssh autoerpprod 'cat > /tujuan'`.

## Volume — yang tidak boleh hilang

```
palmgrade-api_postgres_data     ← data produksi api lama
palmgrade-api_mongo_data        ← data produksi api lama
palmgrade-api_captures_data
portainer_data
+ volume AutoERP (sites, db-data, 2 redis) setelah `up` pertama
```

🚫 **`docker compose down -v` menghapus volume ini permanen.** Untuk mematikan
layanan pakai **`stop`**.

## nginx + TLS

Satu berkas gabungan `/etc/nginx/sites-available/palmgrade.conf` memuat **tiga**
blok server: `api.smagri.id`, `app.smagri.id`, `portainer.smagri.id`. Bukan satu
berkas per domain — cari blok `server_name`, jangan bikin berkas baru.

Satu sertifikat menutupi ketiganya:

```
Certificate Name: api.smagri.id
Domains: api.smagri.id app.smagri.id portainer.smagri.id
Expiry: 2026-12-07
```

⚠️ **Nama sertifikatnya `api.smagri.id` walau isinya bertiga.** Memindahkan
`app.smagri.id` ke AutoERP **tidak butuh certbot ulang** — cukup ubah `proxy_pass`
dari `127.0.0.1:3050` ke `127.0.0.1:8080` dan tambah blok `/socket.io`. Menjalankan
certbot ulang justru berisiko memecah sertifikat yang sudah jalan.

Cloudflare: proxied (orange), SSL/TLS **Full (strict)**. 🚫 Jangan pernah Flexible.

## Kebersihan disk — 44 image menumpuk

~24 tag api + ~20 tag frontend masih tersimpan. Berguna untuk rollback, jadi **jangan
`docker image prune -a`** membabi buta. Kalau disk sempit, hapus tag lama satu per satu
dan sisakan 2–3 versi terakhir.

## Jebakan

1. **Reboot tidak membaca `.env` yang berubah.** Perlu `restart` layanan.
2. **Versi di CLAUDE.md gampang basi.** Yang terakhir jalan `api v1.17.0` +
   `frontend v1.8.0`, sementara CLAUDE.md menulis `v1.3.2`/`v1.2.2`.
3. **Tanpa swap.** Proses yang kehabisan RAM langsung kena OOM kill, tidak melambat
   dulu. Gejalanya container mati sendiri tanpa error yang menunjuk ke penyebab.
4. **`sudo` minta sandi.** Perintah panjang berawalan `sudo` menggantung menunggu input
   kalau dijalankan tanpa terminal.
5. **Uptime bisa sangat panjang** dengan `*** System restart required ***` menumpuk
   (71 hari saat diukur 2026-09-18). Reboot saat tenang, bukan saat sibuk.
6. **Automated Backups DO aktif** (mingguan, Minggu 00:00–04:00 UTC, simpan 4). Biayanya
   ikut naik setelah resize. Ini **bukan** pengganti `bench backup` — yang mingguan
   terlalu jarang untuk buku besar.

## Backup AutoERP — sejak 2026-09-21

Harian ke Cloudflare R2, **uji restore sudah lolos** (11 DocType palm_mill di site
hasil restore, produksi dicek tetap 11).

| | |
|---|---|
| Script | `/opt/autoerp/backup.sh` (sumber: `autoerp/deploy/droplet/backup.sh`) |
| Pemeriksa | `/opt/autoerp/backup-check.sh`, cron 08:00 — menangkap "cron mati" |
| Cron | `15 2 * * *` backup, `0 8 * * *` cek, sebagai user `deploy` |
| Kredensial | `/opt/autoerp/.backup-env` chmod 600 — **terpisah dari `.env`** karena workflow deploy menulis ulang `.env` tiap rilis |
| Bucket | `autoerp-backups` (R2), **Public Access Disabled** |
| Token | `autoerp-backup-writer`, Account token, Object R&W, scoped 1 bucket |
| Log | `/var/log/autoerp/backup.log` + `backup.status` (satu baris `OK`/`GAGAL`) |
| Ukuran | dump ~874 KB → free tier 10 GB, **biaya Rp 0** |

Cek cepat: `cat /var/log/autoerp/backup.status`

⚠️ **Jangan taruh dump di `palmgrade-captures`** — bucket itu public read lewat
`captures.smagri.id`. Dump berisi seluruh buku besar.

🔴 **`rclone` + R2: `exit 0` menyembunyikan `501 Not Implemented`.** Sesudah unggah,
rclone menyetel mtime lewat CopyObject (`x-amz-copy-source` + `metadata-directive:
REPLACE`); R2 tidak punya CopyObject → 501 → rclone mengulang **seluruh** percobaan
dan berhasil di percobaan kedua. Unggahannya sendiri **sudah berhasil sejak awal**.
Obatnya `--no-update-modtime`. **Bukan** ACL dan **bukan** checksum — dua tebakan itu
sudah dicoba dan meleset; docs Cloudflare menyesatkan di sini. Diagnosis yang benar:
`rclone copy … --dump headers | grep -iE "x-amz|501"`.

⚠️ `rclone` dari apt = **1.60** (Okt 2022) dan itu cukup. Installer resmi
(`curl rclone.org/install.sh | sudo bash`) lambat dan gampang dikira nge-hang.

⚠️ `/var/log` di Ubuntu `775 root:syslog` itu **normal**; logrotate tetap menolak
tanpa `su`. Log AutoERP karena itu di direktorinya sendiri `/var/log/autoerp/`.

## Cara ukur ulang

```bash
nproc; free -h; df -h /
lsb_release -d; uname -r
ls -la /opt/
docker ps -a --format '{{.Names}}\t{{.Status}}\t{{.Image}}'
docker volume ls
sudo ss -tlnp | grep LISTEN
sudo certbot certificates | grep -E "Certificate Name|Domains|Expiry"
sudo ufw status
```

Perbarui berkas ini **beserta tanggal di atas** setiap kali angkanya berubah —
angka tanpa tanggal lebih berbahaya daripada tidak ada angka.
