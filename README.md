# AutoERP

Fork [ERPNext](https://github.com/frappe/erpnext) yang mengikuti branch rilis **`version-16`**
(pindah dari `develop` pada 2026-09-16), dengan merek **AutoERP**. Inilah aplikasi ERP di balik
demo pabrik kelapa sawit PalmGrade / PKS.

Di dalamnya aplikasi ini tetap bernama `erpnext` (`app_name = "erpnext"` di `erpnext/hooks.py`),
jadi ia terpasang di `apps/erpnext` dan dipasang ke site sebagai `erpnext`. Yang menyebut AutoERP
cuma `app_title`, logo, dan ikon desk. Ini disengaja — supaya merge dari upstream dan setiap
panggilan `frappe.get_app("erpnext")` tetap jalan.

## Bedanya dengan upstream

| Bagian | Perubahan |
|---|---|
| Merek | `app_title`/`app_publisher` = AutoERP, logo + favicon AutoERP (`erpnext/public/images/autoerp-*.svg`), ikon desk, footer, tautan bantuan, workspace "AutoERP Settings" menggantikan "ERPNext Settings" |
| Penyesuaian | suntingan kecil di doctype setelan Accounts/Buying/Stock, `stock_ledger.py`, `reorder_item.py`, Production Plan, Company, dan workspace CRM/Support |

Selebihnya ERPNext upstream apa adanya. Lihat `git log` — tiap baris di atas punya commit sendiri.

## Lingkungan yang sudah diuji

| Alat | Versi yang dipakai |
|---|---|
| Python | 3.14 (`pyproject.toml` minta `>=3.14`) |
| Node / yarn | 26.x / 1.22 |
| MariaDB | 12.2 (10.6+ semestinya jalan) |
| Redis | 8.x |
| bench | 5.29 |
| frappe | `develop` @ commit `2231252` |

## Menjalankannya dari nol

```bash
# 1. bench dengan frappe develop, dipatok ke commit yang dipakai menguji fork ini
bench init --frappe-branch version-16 --python python3.14 frappe-bench
cd frappe-bench
bench setup requirements

# 2. aplikasi ini — perhatikan: mendarat di apps/erpnext, bukan apps/autoerp
bench get-app git@github.com:delta-anugrah/autoerp.git --branch staging

# 3. sebuah site
bench new-site autoerp.localhost --db-root-password <sandi root mariadb> --admin-password admin
bench --site autoerp.localhost install-app erpnext
bench use autoerp.localhost
bench start          # http://localhost:8000
```

Bench milik Frappe butuh redis jalan di port yang tertulis di `config/redis_*.conf`
(13000/11000/12000) — `bench start` menyalakannya sendiri. Kalau kamu menjalankan `bench serve`
manual, nyalakan sendiri: `redis-server config/redis_cache.conf --daemonize yes` (begitu juga
`redis_queue.conf`), plus `bench --site <site> worker` supaya pekerjaan latar (reposting,
propagasi accounting dimension) jalan.

## Dokumentasi

Mulai dari **[`docs/README.md`](docs/README.md)** — indeks sembilan panduan pendek berbahasa
Indonesia: apa itu AutoERP, cara memasangnya, model data, bagaimana satu kunjungan truk menjadi
Purchase Receipt, API AutoGrade, kontrak integrasi AutoGrade, operasional harian, cara
berkontribusi, dan tiap jebakan yang pernah memakan waktu orang.

## Mengisi data ke site yang baru

Ada dua cara. **Pakai seeder** kecuali kamu memang butuh site Jesse yang persis.

### Seeder — data dibangun dari kode

`erpnext/palm_mill/demo.py` membangun data dengan *bentuk* yang sama seperti dump demo: perusahaan,
kebun dan blok, pemasok plasma dan agen, item dan harga, truk, login desk, akun konsol, dan tujuh
hari kunjungan truk yang didorong lewat controller sungguhan.

```bash
bench --site <site> set-config demo_mode 1
bench --site <site> execute erpnext.palm_mill.demo.seed
bench --site <site> execute erpnext.palm_mill.demo.reset     # hapus tiketnya, isi ulang
bench --site <site> execute erpnext.palm_mill.demo.off       # hapus tiketnya, berhenti (tanpa isi ulang)
bench --site <site> execute erpnext.palm_mill.demo.summary   # sekarang isinya apa
```

Tiga perintah yang sama lewat `Makefile` (`BENCH`/`SITE` bawaannya `~/frappe-bench` /
`pks.localhost`): `make demo`, `make demo-reset`, `make demo-off` — AutoGrade punya tiga nama yang
persis sama.

Untuk mengosongkan site sepenuhnya — bukan cuma baris demonya — `make reset-data` memperlihatkan
apa yang ada dan `make reset-data-fresh` menghapusnya, dengan meminta nama site diketik lebih
dulu. Ia menjalankan `bench reinstall`, bukan `drop-site`, jadi `site_config.json` selamat dan
kunci API yang tersimpan di situ tidak diganti diam-diam. Sisanya habis: tiket, master, dan semua
pengguna kecuali Administrator. Lanjutkan dengan `make migrate` dan `make key-new`, karena
pengguna integrasi AutoGrade ikut terhapus dan PC pabrik ditolak dengan 401 sampai kunci baru
diterbitkan. AutoGrade punya dua nama target yang sama.

Beda dengan dump, seeder ini boleh diserahkan ke klien atau dipasang di laptop mereka: ia tidak
membawa kunci enkripsi site maupun hash sandi sungguhan. Ia menolak jalan di site yang belum
menyatakan dirinya demo (`demo_mode 1`) kecuali dipaksa — sandi demo sama persis di semua akun
dan tertulis di kode sumber, jadi ia tidak boleh mendarat di site yang benar-benar dipakai.

### Dump database — site Jesse yang persis

Demo sawit (perusahaan *PT Sawit Rambang Lestari*, 3.848 tiket timbangan, ~7,4 ribu transaksi
Mei–Juli 2026, 58 truk yang tertaut ke pemasok TBS-nya) itu **data, bukan kode**. Ia hidup di
database MariaDB milik sebuah site, jadi pemasangan aplikasi ini dari nol akan kosong. Untuk
mendapatkannya, pulihkan dump database yang menempel di rilis
[`sawit-data-2026-09-09-truck`](https://github.com/delta-anugrah/autoerp/releases/tag/sawit-data-2026-09-09-truck).
Dump itu terikat ke aplikasi ini pada commit `915bcc2` dan frappe pada `2231252` — pakai bench dari
bagian di atas.

Ikuti langkah ini dari atas ke bawah, dijalankan dari direktori bench (`frappe-bench/`):

```bash
# 1. unduh dumpnya (butuh akses collaborator ke repo ini; atau ambil dari halaman Releases)
gh release download sawit-data-2026-09-09-truck --repo delta-anugrah/autoerp -D /tmp/sawit

# 2. site baru buat tempat memulihkan (install-app TIDAK perlu — dump sudah membawa aplikasinya)
bench new-site pks.localhost --db-root-password <sandi root mariadb> --admin-password admin

# 3. pulihkan dump ke situ, lalu samakan skemanya dengan kode yang terpasang
bench --site pks.localhost restore /tmp/sawit/*-pks_localhost-database.sql.gz --db-root-password <sandi root mariadb>
bench --site pks.localhost migrate

# 4. dump membawa hash Administrator yang lama — pasang sandimu sendiri
bench --site pks.localhost set-admin-password admin

# 5. jalankan
bench use pks.localhost
bench start                       # http://pks.localhost:8000  (login: Administrator / admin)
```

Di Linux, tambahkan `127.0.0.1 pks.localhost` ke `/etc/hosts`; macOS menyelesaikan `*.localhost`
sendiri. Satu worker harus jalan (`bench start` menyalakan satu) atau accounting dimension tidak
akan pernah sampai ke GL Entry.

**Sehari-hari, begitu benchnya ada**, pakai `Makefile` di repo ini (`make help` mendaftar semua
target):

```bash
make up          # nyalakan di latar, kembali begitu site menjawab
make status      # jalan? menjawab? bench melayani checkout yang mana?
make stop
make key-show    # ERP_API_KEY / ERP_API_SECRET milik AutoGrade, tanpa merotasinya
```

`make up` menolak menyalakan bench kedua. Menjalankan `bench start` dua kali terbaca seperti crash
— yang kedua tidak bisa mengikat port redis dan honcho mematikan seluruh grupnya — padahal bench
pertama masih melayani. Jangan pernah menjalankan ulang `create_integration_user` cuma untuk
membaca kredensialnya: itu merotasi secret, dan setiap AutoGrade yang masih memegang yang lama
kena 401.

**Yang semestinya kamu lihat.** Satu perusahaan, PT Sawit Rambang Lestari (singkatan `S`).
Workspace **Pabrik Kelapa Sawit** di desk, daftar Weighbridge Ticket berisi ~3,8 ribu baris,
Purchase Receipt (~1,8 ribu), dan Stock Ledger untuk TBS / CPO / PK. Cek cepat tanpa browser:

```bash
bench --site pks.localhost execute frappe.get_all --kwargs '{"doctype":"Company","fields":["name","abbr"]}'
# [{"name": "PT Sawit Rambang Lestari", "abbr": "S"}]
```

Yang perlu diketahui:

- **Datanya fiktif.** Pabrik 45 t/jam dengan kebun inti 5.000 ha, dibangkitkan secara
  deterministik. Tidak ada satu pun di sini yang merupakan hasil operasi pabrik sungguhan; jangan
  menyajikannya seolah-olah begitu.
- **Dump ini berisi kredensial** (hash sandi pengguna, kunci enkripsi site). Karena itu ia ada di
  rilis privat — jangan di-commit dan jangan dibagikan ke luar daftar collaborator repo ini.
- **Dump ini lebih tua dari modul Palm Mill.** Ia diambil pada commit `915bcc2`, waktu DocType
  pabrik masih berupa record `custom: 1`; `bench migrate` di branch ini menyelaraskan JSON yang
  dikirim aplikasi di atasnya, dan patch-nya memperbarui datanya. Yang tersisa sebagai record
  database saja tinggal Accounting Dimensions.
- **Pasang dari nol:** [`docs/installation.md`](docs/installation.md).
- **Jangan memulihkan ke aplikasi yang jauh lebih baru.** Pulihkan dulu, baru `migrate`. Kalau
  kamu merge banyak ERPNext upstream, ambil backup baru dari site yang sedang jalan sebelum
  memigrasinya.
- Dataset ini dibangkitkan oleh pipeline privat `delta-anugrah/palmgrade-erp-demo`. Kalau suatu
  saat ia harus dibangun ulang dari nol alih-alih dipulihkan, tanya Jesse.
- **Desktop Layout yang tersimpan membekukan launcher.** Grid desktop menampilkan snapshot
  `Desktop Layout` tiap pengguna lebih dulu ketimbang `tabDesktop Icon`, dan tidak ada yang
  membatalkannya — jadi begitu ada yang menekan Save di mode edit launcher, perubahan berikutnya
  pada JSON ikon yang dikirim aplikasi berhenti sampai ke dia. Klik kanan → **Reset Layout**, atau
  hapus baris `Desktop Layout`-nya.

## Terjemahan

Desk bisa dipindah antara bahasa Indonesia dan Inggris per pengguna (menu pengguna → **Bahasa
Indonesia** / **English**; bawaan site-nya Indonesia). Semua yang ada di lapisan pabrik ditulis
**dalam bahasa Inggris di berkas sumber** lalu diterjemahkan ke Indonesia — mekanisme yang sama
dengan yang dipakai Frappe dan ERPNext — sehingga satu setelan membalik semua label, tombol,
status, dan judul.

Dua kanal, dan alasan keduanya ada:

- **`erpnext/locale/id.po`** — tiap string milik ERPNext atau lapisan pabrik. Ada juga
  `erpnext/locale/en.po`, untuk sedikit nilai *tersimpan* yang berbahasa Indonesia (kriteria
  grading, nama DocType kebun, `Non-sertifikasi`) supaya pengguna Inggris melihat "Unripe",
  "Block", "Uncertified".
- **`erpnext/fixtures/translation.json`** — baris `Translation` untuk string milik **Frappe**
  (`hooks.py` `ignore_translatable_strings_from = ["frappe"]` menjaga mereka tetap di luar katalog
  ERPNext, jadi `.po`-nya tidak akan pernah bisa menimpa *Rumah* milik Frappe untuk Home). Baris
  Translation mengalahkan semua `.po`. Disinkronkan saat migrate.

Alur kerja waktu kamu menambah atau mengubah string yang dilihat pengguna:

```bash
bench generate-pot-file --app erpnext            # sumber → main.pot (jangan pernah menambah msgid manual)
bench update-po-files --app erpnext --locale id  # dan --locale en
#   isi msgstr di erpnext/locale/id.po (format tulisan babel write_po; urut)
bench compile-po-to-mo --app erpnext --force     # runtime membaca .mo, bukan .po — migrate TIDAK mengompilasi
bench --site <site> migrate && bench --site <site> clear-cache   # bootinfo menyimpan seluruh kamus per pengguna
```

Aturannya: tulis bahasa Inggris di sumber; kirim msgid tanpa konteks (ekstraktornya tidak
memancarkan `msgctxt`, dan tampilan daftar / field read-only / ekspor tidak pernah mengirim satu
pun); `update-po-files` diam-diam membuang tiap entri `.po` yang msgid-nya tidak ada di POT. Nilai
tersimpan itu data — terjemahkan untuk ditampilkan, jangan pernah mengganti namanya. Legenda
chart group-by memperlihatkan nilai tersimpan dalam dua bahasa.

## Mengikuti ERPNext upstream

```bash
git remote add upstream https://github.com/frappe/erpnext.git   # sekali saja
git fetch upstream
git merge upstream/version-16
```

Harap siap konflik di berkas merek yang didaftar di atas; ambil punya kita.

## Ikut mengerjakan

Clone repo ini (akses collaborator sudah cukup), bikin branch dari **`staging`**, lalu buka PR
balik ke `staging`; rilis keluar sebagai **merge commit** `staging` → `main`. `CLAUDE.md` berisi
catatan untuk kerja berbantuan AI, dan [`docs/contributing.md`](docs/contributing.md) membahas
gaya, tes, dan CI.

## Modul Palm Mill

`erpnext/palm_mill` adalah modul pabrik kelapa sawit milik fork ini: DocType sawitnya (Weighbridge
Ticket, Weighbridge Grading, Truck, Blok, Kebun, Divisi, Sumber TBS, Sertifikasi), Palm Mill
Settings, workspace "Pabrik Kelapa Sawit" beserta kartu dan chart-nya, logika penyelesaian tiket,
dan endpoint masuk untuk AutoGrade — satu-satunya sistem yang berbicara dengan ERP
(`erpnext.palm_mill.api.upsert_truck` dan `upsert_visit`; program timbangan memberi makan
AutoGrade). Rancangannya ada di `docs/autograde-integration.md`.

Aturan yang menjaga sebuah site tetap sehat:

- **Jangan pernah menjalankan `bench migrate` di checkout yang tidak punya `erpnext/palm_mill`.**
  Frappe menghapus setiap DocType standar yang controller-nya tidak bisa ia impor, **beserta
  tabelnya**.
- Sesudah mengubah `modules.txt`, jalankan `bench --site <site> clear-cache` sebelum `migrate` di
  tiap site; peta modulnya di-cache per site.
- Pengguna integrasi dibuat dengan `bench --site <site> execute
  erpnext.palm_mill.setup.create_integration_user --kwargs '{"email": "...", "full_name": "..."}'`.
  Mereka memegang Palm Mill Integration, Purchase User, dan Stock User; kunci dan secret-nya
  dicetak sekali saja.
- Tes (`bench --site test_site run-tests --module erpnext.palm_mill.test_api` dan tes DocType)
  butuh `test_site` khusus dengan `allow_tests`. Jangan pernah menjalankannya di site berisi data
  sungguhan: penyiapan tes milik ERPNext menghapus transaksi.
- Menyunting DocType ini lewat UI butuh `developer_mode` menyala di site-nya (di `pks.localhost`
  menyala); Frappe lalu mengekspor ulang JSON-nya ke dalam modul.
