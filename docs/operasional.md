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
| `make shell` | `bench console` (REPL Python di site) |

⚠️ **Tidak ada target test.** Test butuh site khusus; lihat
[`kontribusi.md`](kontribusi.md).

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
