# Instalasi AutoERP

Dari clone sampai satu kunjungan truk jadi Purchase Receipt. ±45 menit,
sebagian besar nunggu build.

> **Langkah rinci per perintah + tabel "Cek" tiap step ada di
> [`sawit/docs/onboarding/4-instalasi-autoerp.md`](../../docs/onboarding/4-instalasi-autoerp.md)**
> (diuji 2026-09-16 di macOS). Dokumen ini ringkasannya + cara mengisi data.

## 0. Yang dipasang

| | |
|---|---|
| Frappe Framework | `version-16` |
| AutoERP | fork ERPNext `version-16` + modul `palm_mill` — `delta-anugrah/autoerp`, branch `staging` |
| Nama app di bench | **`erpnext`** (bukan `autoerp`) |
| Database | MariaDB, satu DB per site |
| Python | 3.14 |

```bash
brew install python@3.14 mariadb redis node yarn uv pkgconf
pipx install frappe-bench
```

⚠️ `uv` dan `pkgconf` **wajib** sejak bench 5.31 — tanpa itu `bench init` mati
separuh jalan.

## 1. MariaDB — satu baris sebelum apa pun

MariaDB 11.6+ menyalakan `innodb_snapshot_isolation`. Frappe membaca dokumen
lalu memperbaruinya di transaksi yang sama di mana-mana; di bawah snapshot
isolation itu jadi error 1020, yang di Desk terbaca **"Deadlock Occurred"**.

```ini
# /opt/homebrew/etc/my.cnf   (Linux: /etc/mysql/mariadb.conf.d/50-server.cnf)
[mysqld]
innodb_snapshot_isolation = OFF
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci
```

Taruh di `[mysqld]`, **bukan** `[client]` — CLI menolaknya sebagai opsi asing.
Lalu `brew services restart mariadb` dan cek:

```bash
mariadb -u root -p -e "SELECT @@innodb_snapshot_isolation;"   # OFF
```

App juga melonggarkannya per koneksi (`before_request` / `before_job`), tapi
setel server-nya juga.

## 2. Bench + app

```bash
bench init --frappe-branch version-16 --python python3.14 autoerp-bench
cd autoerp-bench
bench get-app git@github.com:delta-anugrah/autoerp.git --branch staging
bench build --app erpnext        # sekalian mengompilasi locale/*.po → .mo
```

⚠️ **Repo privat → pakai SSH**, bukan HTTPS. Remote di dalam bench bernama
`upstream`, bukan `origin`.

Cek: `ls apps/erpnext/erpnext/palm_mill/doctype` → 11 folder.

## 3. Site

Nama site bebas — `pks.localhost` di bawah cuma contoh, dan kebetulan juga
bawaan `Makefile` (`SITE ?=`). Kalau kamu memakai nama lain (mis.
`autoerp.localhost`), tulis sekali di `Makefile.local` supaya semua perintah
`make` mengikutinya; lihat `operations.md`.

⚠️ **Nyalakan Redis dulu.** `after_install` ERPNext memanggil `frappe.enqueue`,
jadi tanpa Redis hidup `new-site` mati di `Error 61 connecting to
127.0.0.1:11000` — sesudah semua DocType telanjur terpasang. Kalau kamu memakai
`bench start`, dia sudah menyalakannya; kalau belum, nyalakan tangan dan
**matikan lagi sebelum `bench start`**.

```bash
bench new-site pks.localhost --db-name pks --admin-password admin \
  --db-root-username "$USER" --db-socket /tmp/mysql.sock --install-app erpnext
bench --site pks.localhost set-config developer_mode 1
bench use pks.localhost
```

Di macOS tidak ada sandi root MariaDB yang perlu disimpan: user OS adalah
superuser lewat socket. Linux: socket biasanya `/run/mysqld/mysqld.sock`, dan
tambahkan `127.0.0.1 pks.localhost` ke `/etc/hosts`.

`install_app` menjalankan `after_install`, yang membuat: field tambahan, peran
`Weighbridge Operator` + `Palm Mill Integration`, **Sumber TBS `Internal` dan
`External`**, setelan bawaan (aturan potongan, batas 18%, timeout 6 jam,
jendela 2 jam), dan favicon.

⚠️ **Situs baru tidak menjalankan patch.** `install_app` menandai semua patch
selesai tanpa menjalankannya, jadi kebijakan situs ini masih harus dijalankan
tangan (utang yang tercatat sebagai E5):

```bash
bench --site pks.localhost execute erpnext.patches.v17_0.palm_mill_language.execute
bench --site pks.localhost execute erpnext.patches.v17_0.palm_mill_precision.execute
bench --site pks.localhost execute frappe.db.set_single_value --kwargs \
  '{"doctype":"Stock Settings","fieldname":"enable_serial_and_batch_no_for_item","value":1}'
bench --site pks.localhost clear-cache
```

Jalankan **patch-nya**, jangan menyetel field satu per satu: `palm_mill_language`
mengerjakan lima hal, bukan cuma bahasa — dia juga menyalakan Language `id`,
melepas pengguna yang terpaku ke `en-US`, menyembunyikan empat gudang seed yang
kosong, dan menghapus dua Item Group bawaan yang tidak terpakai.

Yang terakhir wajib: tanpa itu TBS ber-batch gagal **417 "Activate Serial and
Batch No"** saat finalisasi.

## 4. Isi data — pilih satu

### 4a. Seeder demo (disarankan)

`erpnext/palm_mill/demo.py` membangun data dari kode: perusahaan, kebun, blok,
pemasok, item + harga, truk, akun Desk, akun konsol, dan 7 hari kunjungan truk
lewat controller sungguhan.

```bash
bench --site pks.localhost set-config demo_mode 1
bench --site pks.localhost execute erpnext.palm_mill.demo.seed
```

Isinya: **PT Sawit Rambang Lestari**, 2 kebun, 4 divisi, 4 KUD plasma + 3 agen,
10 truk (BE Lampung / BG Sumsel), TBS Rp 2.850/kg, ±6–11 kunjungan per hari
selama 7 hari.

Akun yang dibuat (sandi semua `sawit2026`):

| Email | Peran |
|---|---|
| `krani@demo.autoerp.test` | Weighbridge Operator |
| `mandor@demo.autoerp.test` | + Stock User |
| `manajer@demo.autoerp.test` | + Purchase/Stock/Accounts |
| `operator@demo.autoerp.test` | AutoGrade Operator (`operator`) |
| `support@demo.autoerp.test` | AutoGrade Operator (`support`) |

Perintah lain:

```bash
bench --site pks.localhost execute erpnext.palm_mill.demo.reset      # hapus tiket, seed ulang
bench --site pks.localhost execute erpnext.palm_mill.demo.summary    # apa yang ada sekarang
```

`reset` cuma menghapus tiket bertanda `DEMO-` beserta dokumen stoknya; master,
pemasok, truk, dan akun dibiarkan.

⚠️ Seeder **menolak jalan** di site yang tidak bertanda `demo_mode 1`, kecuali
dipaksa `force=1`. Ini penjaga supaya data demo tidak pernah mendarat di site
produksi.

⚠️ Sandi demo sama untuk semua akun dan tertulis di kode. **Jangan pakai seeder
di site yang dipakai sungguhan.**

### 4b. Dump database privat

Kalau kamu memang butuh site yang persis sama dengan punya Mas Samuel (3.848
tiket, laporan OER berisi). Butuh akses kolaborator ke repo.

⚠️ Dump berisi kunci enkripsi site dan hash sandi pengguna. **Tidak boleh
diberikan ke klien atau dipasang di mesin mereka** — itu alasan seeder di §4a
dibuat. Untuk hampir semua keperluan, pakai seeder.

```bash
gh release download sawit-data-2026-09-09-truck --repo delta-anugrah/autoerp -D /tmp/sawit

bench new-site pks.localhost --db-name pksdemo --admin-password admin \
  --db-root-username "$USER" --db-socket /tmp/mysql.sock
bench --site pks.localhost restore /tmp/sawit/*-database.sql.gz \
  --db-root-username "$USER" --db-socket /tmp/mysql.sock
bench --site pks.localhost set-config developer_mode 1
bench --site pks.localhost migrate
bench --site pks.localhost set-admin-password admin
bench --site pks.localhost clear-cache
```

`migrate` yang mengangkat dump ke keadaan sekarang: DocType JSON yang dikirim
app menimpa rekaman `custom: 1` milik dump, lalu **11 patch `palm_mill_*`**
berjalan. Di site hasil restore patch **jalan sendiri** — jadi step patch manual
(§3) tidak perlu di sini.

Dump ini berskema `develop`; `migrate` menaikkannya ke `version-16` — terbukti
2026-09-16.

**Satu hal yang tidak dikerjakan patch:** dump berisi 146 Quality Inspection
(semuanya salah bertanda Rejected) dan dua template. Lab sudah dikeluarkan dari
lapisan pabrik, dan ini data demo, jadi dihapus tangan:

```bash
bench --site pks.localhost console
```

```python
for n in frappe.get_all("Quality Inspection", pluck="name"):
    doc = frappe.get_doc("Quality Inspection", n)
    if doc.docstatus == 1:
        doc.flags.ignore_permissions = True
        doc.cancel()                       # on_cancel melepas tautan di baris stock entry
    frappe.delete_doc("Quality Inspection", n, force=True, ignore_permissions=True)
for t in frappe.get_all("Quality Inspection Template", pluck="name"):
    frappe.delete_doc("Quality Inspection Template", t, force=True, ignore_permissions=True)
frappe.db.commit()
```

### 4c. Kosong

Boleh, tapi ingat: `Sumber TBS` harus punya `Internal` dan `External`
(`after_install` sudah membuatnya), dan `Palm Mill Settings` harus menunjuk
`tbs_item` + `tbs_warehouse` sebelum tiket bisa difinalisasi.

## 5. Jalankan

```bash
make up          # start di latar belakang, tunggu sampai site menjawab
make status      # jalan? menjawab? checkout mana yang dilayani?
```

Buka http://pks.localhost:8000 — `Administrator` / `admin`.

⚠️ **Jangan `bench start` dua kali.** Yang kedua tidak bisa mengikat port redis,
satu anak mati, lalu honcho menjatuhkan seluruh grupnya — di layar terbaca
seperti bench pertama crash, padahal dia masih melayani. `make up` menolak
menyalakan yang kedua.

Di Linux tambahkan `127.0.0.1 pks.localhost` ke `/etc/hosts`; macOS
menyelesaikan `*.localhost` sendiri.

## 6. Kunci buat AutoGrade

```bash
make key-new     # buat akun integrasi (konfirmasi "yes")
make key-show    # lihat lagi TANPA merotasi
```

Tempel hasilnya ke `.env` AutoGrade sebagai `ERP_API_KEY` / `ERP_API_SECRET`.

## 7. Cek instalasi benar

```bash
bench --site pks.localhost console
```

```python
frappe.get_all("Sumber TBS", pluck="name")                       # ['External', 'Internal']
frappe.db.count("Weighbridge Ticket")                            # > 0 kalau di-seed
frappe.db.get_single_value("System Settings", "language")        # 'id'
frappe.db.get_single_value("Palm Mill Settings", "tbs_item")     # 'TBS'
frappe.db.get_single_value("Stock Settings", "enable_serial_and_batch_no_for_item")  # 1
```

Di Desk: workspace **Pabrik Kelapa Sawit** dengan 7 kartu angka dan 5 grafik.

## 8. Kalau gagal

Semua jebakan yang pernah memakan waktu ada di [`gotchas.md`](gotchas.md).
Yang paling sering:

| Gejala | Sebab | Obat |
|---|---|---|
| `bench init` mati separuh jalan | `uv` / `pkgconf` belum ada | §0, lalu `rm -rf autoerp-bench` dan ulang |
| Port jadi 8001 | ada bench lain jalan | matikan yang lain dulu |
| TBS gagal **417** | Stock Settings belum disetel | §3 baris terakhir |
| "Could not find FFB Source" | `after_install` tidak jalan | `bench --site … execute erpnext.palm_mill.setup.after_install` |
| Kunci API 401 padahal benar | ada `default_site` di `common_site_config.json` | hapus key itu, `bench restart` |
| Desk tetap Inggris | cache | `clear-cache` + Ctrl-Shift-R |
| "Deadlock Occurred" | snapshot isolation | §1 |
