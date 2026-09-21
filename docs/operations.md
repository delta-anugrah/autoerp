# Operasional harian

Site sudah jalan. Ini yang dipakai sehari-hari.

## Makefile

`Makefile` di akar repo menggerakkan bench yang **ada di luar repo ini**
(bawaan `~/frappe-bench`).

Kalau bench-mu bukan yang bawaan, tulis sekali di `Makefile.local` — berkas ini
tidak ikut git, jadi tiap mesin punya versinya sendiri:

```make
# Makefile.local
BENCH = $(HOME)/autoerp-bench
SITE  = autoerp.localhost
```

Sesudah itu semua target jalan tanpa argumen: `make up`, `make stop`,
`make status`. Tanpa berkas itu, override per perintah juga boleh:

```bash
make up BENCH=/srv/frappe-bench SITE=pks.localhost
```

| Perintah | Isi |
|---|---|
| `make help` | daftar semua target + bench/site/URL yang dipakai |
| `make up` | start di latar belakang, tunggu sampai `/api/method/ping` menjawab (maks 120 dtk) |
| `make start` | start di depan, log di layar (Ctrl-C untuk berhenti) |
| `make stop` | SIGTERM ke supervisor honcho, tunggu 15 dtk |
| `make restart` | `stop` lalu `up`, berurutan |
| `make status` | jalan? menjawab? app apa saja? checkout mana? |
| `make where` | clone mana yang **benar-benar** dilayani bench |
| `make key-show` | cetak `ERP_API_KEY=` / `ERP_API_SECRET=` **tanpa merotasi** |
| `make key-new` | buat/rotasi akun integrasi — minta ketik `yes` |
| `make migrate` | `bench migrate` |
| `make backup` | backup database + files |
| `make reset-data` | **lihat dulu**: site mana dan berapa isinya. Tidak mengubah apa pun |
| `make reset-data-fresh` | **KOSONGKAN SITE**: `bench reinstall` — seluruh tiket, master, dan semua user selain Administrator hilang, **tanpa backup**. Minta **nama site diketik** (bukan `yes`: `SITE=` yang salah tunjuk adalah cara paling mudah mengosongkan site yang keliru). Memakai `reinstall`, **bukan `drop-site`**, supaya `site_config.json` selamat — di situ ada kunci API AutoGrade. ⚠️ Sesudahnya: `make migrate` lalu **`make key-new`**, karena user integrasi ikut terhapus dan PC pabrik ditolak 401 tanpa kunci baru. ⚠️ Jangan di site produksi. AutoGrade punya dua target nama sama |
| `make shell` | `bench console` (REPL Python di site) |
| `make demo` | isi data demo untuk showcase ke klien — menyalakan `demo_mode 1` dulu (site menolak seed tanpanya), lalu `erpnext.palm_mill.demo.seed`. AutoGrade punya target nama sama |
| `make demo-reset` | hapus data demo lalu isi ulang bersih (`erpnext.palm_mill.demo.reset`) |
| `make demo-off` | hapus data demo dan **berhenti** di situ, tidak isi ulang — jalankan sesudah showcase dan **sebelum** uji coba sungguhan di site itu: baris demo duduk di tabel yang sama dengan yang asli, jadi daftar tiket yang masih membawanya terbaca seolah pabrik membukukan muatan yang tidak pernah diterima (`erpnext.palm_mill.demo.off`) |

⚠️ **Tidak ada target test.** Test butuh site khusus; lihat
[`contributing.md`](contributing.md).

`make where` ada karena gampang sekali mengedit checkout kedua repo ini lalu
bingung kenapa tidak ada yang berubah.

## Layar sehari-hari

Workspace **Pabrik Kelapa Sawit** (halaman depan):

| Kartu angka | Isi |
|---|---|
| Avg Daily OER (%) | rendemen minyak rata-rata |
| TBS Diterima (kg) | jumlah neto |
| Tiket Timbang | jumlah tiket |
| Nilai Pembelian TBS | jumlah `nilai` untuk sumber External |
| Piutang / Hutang Usaha | outstanding invoice |
| Penjualan | grand total Sales Invoice |

Lima grafik: OER & KER harian, penerimaan TBS harian, TBS per sumber (donat),
per sertifikasi (pai), pembelian per pemasok (batang).

Navigasi lengkap ada di **sidebar**, enam kelompok: Home · Weighing & Grading ·
Production & Extraction · Finance · Estate & Blocks · Mill Settings.

## Tiket yang diketik tangan

Kalau AutoGrade mati atau truknya tidak lewat line:

1. Buat **Weighbridge Ticket** baru, isi `scale_ticket_no` dari slip timbangan.
2. Isi berat dan sortasi.
3. Submit.
4. Kalau `create_stock_documents_on_submit` mati (bawaannya mati), tekan tombol
   **Receive Stock** untuk membuat Purchase Receipt / Stock Entry.

Kalau AutoGrade menyusul mengirim kunjungan yang sama, kiriman itu **mengadopsi**
tiket ini lewat `scale_ticket_no`.

## Melihat apa yang dikirim AutoGrade

- **Integration Request** — satu baris per panggilan berhasil, menunjuk ke
  tiketnya. Ini bukti "sudah sampai".
- **Error Log** — panggilan gagal, berisi payload penuh + traceback.

Kalau AutoGrade bilang sudah kirim tapi tiketnya tidak ada, cek dua daftar itu
dulu sebelum menyalahkan jaringan.

## Bahasa

Desk bisa Indonesia atau Inggris per pengguna: menu pengguna (kiri bawah) →
**Bahasa Indonesia** / **English**. Bawaan site `id`.

Semua string ditulis **Inggris di kode** lalu diterjemahkan — mekanisme Frappe
biasa. Dua kanal:

- `erpnext/locale/id.po` — string milik ERPNext dan modul sawit
- `erpnext/fixtures/translation.json` — string milik **Frappe** (`.po` ERPNext
  tidak bisa menimpanya; baris `Translation` mengalahkan semua `.po`)

## Backup

```bash
make backup      # database + files
```

Hasilnya di `sites/<site>/private/backups/`. Sebelum `migrate` besar (misalnya
setelah merge upstream banyak), ambil backup dulu.

### Di droplet produksi — otomatis tiap hari

`deploy/droplet/backup.sh` jalan lewat cron tiap **02:15 WIB**: `bench backup
--with-files` → kirim ke Cloudflare R2 → buang yang lebih tua dari 14 hari (di R2
**dan** di dalam container).

| | |
|---|---|
| Script | `/opt/autoerp/backup.sh` ← `deploy/droplet/backup.sh` |
| Pemeriksa | `/opt/autoerp/backup-check.sh`, cron 08:00 |
| Kredensial | `/opt/autoerp/.backup-env`, `chmod 600` |
| Bucket | `autoerp-backups` — **privat**, bukan `palmgrade-captures` yang publik |
| Log | `/var/log/autoerp/backup.log`, logrotate mingguan × 8 |
| Status | `/var/log/autoerp/backup.status` — satu baris, `OK <stamp>` atau `GAGAL …` |

Kredensial sengaja **tidak** di `.env`: workflow deploy menulis ulang berkas itu
tiap rilis dan akan menghapusnya.

Isi `.backup-env`:

```bash
R2_ACCOUNT_ID=…
R2_ACCESS_KEY_ID=…
R2_SECRET_ACCESS_KEY=…
R2_BUCKET=autoerp-backups
SITE_NAME=app.smagri.id
KEEP_DAYS=14
ALERT_WEBHOOK=            # opsional; kosong = cukup logger/journalctl
```

Pasang cron-nya:

```bash
( crontab -l 2>/dev/null
  echo "15 2 * * * /opt/autoerp/backup.sh"
  echo "0  8 * * * /opt/autoerp/backup-check.sh" ) | crontab -
```

Lihat hasil terakhir:

```bash
cat /var/log/autoerp/backup.status
tail -20 /var/log/autoerp/backup.log
journalctl -t autoerp-backup -t autoerp-backup-check --since '2 days ago'
```

### Pintasan di droplet

`deploy/droplet/Makefile` dipasang sebagai `/opt/autoerp/Makefile`. Makefile di akar
repo menyetir bench **lokal**; di droplet bench itu ada di dalam container, jadi
target yang sama dibungkus `docker compose exec`.

```bash
cd /opt/autoerp
make help        # daftar target
make ping        # situsnya hidup?
make company     # nama Company yang terpasang
make key-show    # kunci AutoGrade, TIDAK merotasi
make key-new     # terbitkan kunci baru — MEROTASI secret, minta ketik `yes`
make backup      # jalur yang sama dengan cron, bukan jalur kedua
```

`key-show` mencetak dalam bentuk siap tempel ke `.env` AutoGrade
(`ERP_URL`/`ERP_API_KEY`/`ERP_API_SECRET`).

### Uji restore — wajib, dan jangan ke site produksi

Backup yang belum pernah di-restore bukan backup. Restore ke site sementara:

```bash
cd /opt/autoerp
C="docker compose -f docker-compose.prod.yml"
PW="$(grep '^DB_PASSWORD=' .env | cut -d= -f2-)"

$C exec -T backend bench new-site restoretest.localhost \
  --db-root-password "$PW" --admin-password admin --install-app erpnext

$C exec -T backend bench --site restoretest.localhost --force restore \
  "sites/app.smagri.id/private/backups/<stamp>-database.sql.gz" --db-root-password "$PW"

# Bukti isinya sampai: harus 11, sama dengan produksi
$C exec -T backend bench --site restoretest.localhost execute \
  frappe.client.get_count --args '["DocType",{"module":"Palm Mill"}]'

$C exec -T backend bench drop-site restoretest.localhost \
  --db-root-password "$PW" --force --no-backup
```

⚠️ **`bench` tanpa `--site` mengenai `app.smagri.id`** (situs `--set-default`).
`restore` yang salah sasaran **menimpa produksi**. Periksa tiap baris sebelum Enter.

⚠️ **`rclone` + R2: `exit 0` bisa menyembunyikan `501 Not Implemented`.** Sesudah
unggah, rclone menyetel mtime lewat CopyObject (`x-amz-copy-source`); R2 tidak
punya CopyObject, menjawab 501, dan rclone mengulang **seluruh** percobaan —
padahal unggahannya sudah berhasil. Karena itu `backup.sh` memakai
`--no-update-modtime`. Kalau muncul lagi, diagnosisnya `--dump headers`, bukan
menebak ACL.

## Setelah menarik perubahan kode

```bash
bench --site pks.localhost migrate        # skema + patch
bench --site pks.localhost clear-cache    # setelah ubah JSON / terjemahan
bench build --app erpnext                 # setelah ubah JS atau .po
```

⚠️ **`bench migrate` tidak mengompilasi terjemahan.** Setelah menyentuh
`locale/*.po`: `bench compile-po-to-mo --app erpnext --force` lalu `clear-cache`
(bootinfo menyimpan seluruh kamus per pengguna).

## Menaikkan versi dari upstream ERPNext

```bash
git remote add upstream https://github.com/frappe/erpnext.git   # sekali
git fetch upstream
git merge upstream/version-16
```

Konflik yang wajar ada di berkas branding (`hooks.py`, logo, `modules.txt`) —
ambil punya kita. Ambil backup site yang jalan sebelum `migrate` sesudahnya.

## Scheduler

Tiap 15 menit `finalize_due_tickets` menyapu draft yang sudah siap. Dia **hanya
jalan kalau ada worker** — `bench start` (dan `make up`) menjalankannya,
`bench serve` sendirian tidak.

Kalau tiket menumpuk di `Ready` dan tidak pernah `Finalised`, dua tersangka:
worker mati, atau tidak ada Item Price TBS untuk tanggal itu (cek Error Log).
