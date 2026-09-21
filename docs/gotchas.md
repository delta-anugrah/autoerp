# Jebakan

Semuanya pernah terjadi dan memakan waktu. Diurutkan dari yang paling merusak.

## 1. `bench migrate` di checkout tanpa `erpnext/palm_mill`

**Frappe menghapus DocType standar yang controllernya tidak bisa dia impor —
beserta tabelnya.** Tanpa error, tanpa konfirmasi. Ini juga yang menghapus
Workspace publik tanpa berkas app.

Selalu pastikan checkout yang dilayani bench punya modulnya:

```bash
make where
ls apps/erpnext/erpnext/palm_mill/doctype     # harus 11 folder
```

## 2. Menjalankan ulang `create_integration_user` cuma untuk melihat kunci

Dia **merotasi** `api_secret`. Semua AutoGrade yang masih memegang yang lama
langsung 401, dan tiketnya berhenti sampai ada yang sadar.

```bash
make key-show     # lihat tanpa merotasi
make key-new      # kalau memang mau merotasi (minta konfirmasi)
```

## 3. `bench start` dua kali

Yang kedua tidak bisa mengikat port redis, satu anaknya mati, lalu honcho
menjatuhkan seluruh grupnya. Di layar terbaca seperti bench pertama crash —
padahal dia masih melayani dengan baik. `make up` menolak menyalakan yang kedua.

## 4. Site baru lahir tanpa kebijakan situs — **sudah diperbaiki**

`install_app` menandai **semua patch selesai tanpa menjalankannya**, jadi site baru
dulu tidak pernah mendapat bahasa `id`, presisi 2 desimal, maupun Stock Settings
`enable_serial_and_batch_no_for_item` — lahir berbahasa Inggris, 3 desimal, dan
**TBS ber-batch gagal 417** saat finalisasi.

Sejak PR #17 kebijakan itu ikut `after_install` (`apply_site_policy()`), jadi site
baru sudah benar tanpa perintah manual. Yang tetap perlu diketahui: pembersihan
gudang/item group bawaan berjalan dari hook **`setup_wizard_complete`**, bukan
`after_install` — gudang seed dibuat `Company.create_default_warehouses` dan item
group oleh `install_fixtures`, keduanya **sesudah** `after_install`, jadi dipanggil
di sana hasilnya nol kecocokan tanpa pesan apa pun.

⚠️ Flag serial/batch disimpan di **dua** tempat: Single yang dibaca validasi server,
dan default yang dibaca `item.js` untuk memutuskan field Batch No dirender atau tidak.
`set_single_value` saja menghasilkan site yang bisa menerima TBS tapi
**menyembunyikan centang "Has Batch No"** di form Item.

## 5. "Deadlock Occurred" padahal tidak ada deadlock

MariaDB 11.6+ mengubah update baris yang sama secara bersamaan jadi error 1020,
bukan menunggu lock. Frappe membaca dokumen lalu memperbaruinya di transaksi
yang sama di mana-mana (dashboard chart, naming series).

Obatnya `innodb_snapshot_isolation = OFF` di `[mysqld]` — **bukan** `[client]`,
yang ditolak CLI sebagai opsi asing. App juga melonggarkannya per koneksi lewat
hook `before_request` / `before_job`.

## 6. Mengedit JSON yang dikirim app tidak berpengaruh

`migrate` **melewati berkas yang lebih tua dari baris database**. Ubah juga
`modified` di JSON-nya.

Dan `Workspace.is_hidden` **tidak pernah** disinkronkan dari berkas sama sekali
— harus lewat patch.

## 7. Terjemahan tidak berubah setelah edit `.po`

`bench migrate` **tidak** mengompilasi `.po`. Runtime membaca `.mo`.

```bash
bench compile-po-to-mo --app erpnext --force
bench --site <site> clear-cache        # bootinfo cache kamus per pengguna
```

Dan jangan menambahkan msgid ke `.po` dengan tangan: `bench generate-pot-file`
lalu `bench update-po-files`. `update-po-files` membuang diam-diam entri yang
msgid-nya tidak ada di POT.

## 8. Widget workspace hilang tanpa pesan

Blok konten workspace mencocokkan widget **berdasarkan label**. Beri label pada
kartu/grafik/pintasan, dan `*_name` di bloknya harus sama persis — kalau tidak,
widgetnya lenyap diam-diam.

## 9. Launcher membeku setelah ada yang menekan Save

Desk merender snapshot `Desktop Layout` per pengguna lebih diutamakan daripada
`tabDesktop Icon`, dan tidak ada yang membatalkannya. Setelah seseorang menekan
Save di mode edit launcher, perubahan ikon yang dikirim app berhenti sampai ke
dia.

Obat: klik kanan → **Reset Layout**, atau hapus baris `Desktop Layout`-nya.

## 10. Ikon SVG tidak berubah

`/assets/` di-cache browser 12 jam (`max-age=43200`). Buka URL ikonnya langsung
lalu hard-reload.

Favicon lebih parah: browser menyimpannya **per URL** dan tidak menengok lagi
selama URL-nya sama. Itu sebabnya berkas favicon sekarang bernama
`autoerp-favicon-palem.svg` — mengganti isi berkas lama saja meninggalkan
lambang lama di tab orang.

## 11. Nama paket report ikut tanda kurung

Paket script report dinamai `frappe.scrub(nama report)`, kurung ikut. Pakai
nama report berupa kata biasa saja.

## 12. `developer_mode` menulis balik ke repo

Site `pks.localhost` menyalakan `developer_mode`. **Edit Sidebar** di UI menulis
langsung ke `erpnext/workspace_sidebar/*.json`, dan mengedit DocType lewat UI
mengekspor ulang JSON-nya. Berguna — dan gampang ter-commit tanpa sengaja. Cek
`git status` sebelum commit.

## 13. Kunci API 401 padahal benar

Cek ada tidaknya `default_site` di `sites/common_site_config.json`. Kalau ada,
hapus lalu `bench restart`.

## 14. Menjalankan test di site berisi data sungguhan

Setup test ERPNext **menghapus transaksi**. Selalu pakai site khusus dengan
`allow_tests`; jangan pernah di site berisi data.

## 15. Batch harian terhapus saat satu receipt dibatalkan

Batch tanpa referensi akan "diadopsi" Purchase Receipt pertama yang memakainya,
dan ERPNext menghapusnya saat receipt itu dibatalkan — padahal tiket lain hari
itu masih memakai batch yang sama.

Karena itu `get_or_create_daily_batch()` selalu menyetel `reference_doctype` /
`reference_name` ke tiket pembuatnya.

## 16. Regex plat yang lepas dari kembarannya

`SCANNABLE_PLATE` di `erpnext/palm_mill/utils.py` harus identik dengan
`_BENTUK_PLAT` di `domain/qr.py` milik AutoGrade. Kalau berbeda, kartu QR
tercetak untuk plat yang gerbang tidak bisa baca — ketahuan di gerbang, setelah
kartunya tertempel, dengan sopir menunggu.

Test `test_scannable_plate_matches_autograde` mengunci itu. Ubah di sini, ubah
di sana, **dalam PR yang sama**.

## 17. Tiket menumpuk di `Ready`, tidak pernah `Finalised`

Dua tersangka:

1. **Worker mati.** Scheduler tidak jalan tanpa worker. `bench start` /
   `make up` menjalankannya; `bench serve` sendirian tidak.
2. **Tidak ada harga TBS** untuk tanggal itu. `try_finalize` sengaja berhenti
   tanpa submit dan menulis Error Log — lebih baik daripada membukukan nilai 0.

## 18. Data demo mendarat di site sungguhan

`demo.seed` menolak jalan di site tanpa `demo_mode 1`, kecuali dipaksa
`force=1`. Sandinya sama untuk semua akun dan tertulis di kode — jangan pakai
seeder di site yang dipakai sungguhan.

## 19. Site `--install-app` lahir tanpa isi wizard — dan satu di antaranya diam

`bench new-site --install-app erpnext` **tidak menjalankan setup wizard**, jadi lima
hal yang biasanya dibuat wizard tidak ada. Empat di antaranya gagal keras dan mudah
dikenali; yang kelima tidak melapor apa pun.

| Hilang | Gejala |
|---|---|
| `Warehouse Type: Transit` | pembuatan Company gagal (set gudang bawaan memuat Goods In Transit) |
| Price List `Standard Buying` | Item Price gagal dibuat |
| Fiscal Year | Purchase Receipt tidak bisa posting ke GL |
| `Stock Settings.enable_serial_and_batch_no_for_item` | item ber-batch (TBS) ditolak saat submit |
| **Default currency `INR`** | **tidak ada gejala** — lihat di bawah |

⚠️ **Yang kelima adalah yang berbahaya.** Company dan Price List dua-duanya IDR, tapi
currency penagihan supplier diambil dari **global default**, dan di site baru itu `INR`.
Akibatnya tiap Purchase Receipt terbit dalam INR dengan `conversion_rate` 184,07:
`amount` **benar** (Rp 26 jt untuk 10 ton), tapi `base_amount` dan Stock In Hand dikali
184× — Rp 180 **miliar** untuk seminggu. Tidak ada error, tidak ada peringatan, dan
angka yang dilihat di form receipt justru yang benar, jadi ini cuma ketahuan kalau ada
yang membuka neraca.

Periksa sebelum memasukkan transaksi apa pun:

```python
frappe.db.get_default("currency")                                  # harus IDR
frappe.db.get_value("Purchase Receipt", <nama>, "conversion_rate")  # harus 1.0
```

`demo.set_defaults_currency()` membereskan kelimanya; site yang dibuat dengan cara lain
harus disetel sendiri.

## 20. Setelah ubah `modules.txt`

Jalankan `bench --site <site> clear-cache` **sebelum** `migrate`, di setiap
site. Peta modul di-cache per site.

## 21. Kolom "Percent" di sortasi, angka operator kilogram

Baris sortasi punya kolom berlabel **Percent**, tapi angka yang ada di kepala operator
timbangan adalah kilogram. Mengetik `500` untuk "500 kg sampah" alih-alih `5` dulu
lolos `validate()` dan menghasilkan, pada muatan 10.000 kg:

```
sampah_kg : 50.000 kg
kg_dibayar: -40.000 kg
nilai     : -Rp 114.000.000
```

Tidak ada yang menahannya: `max_potongan_pct` hanya membatasi `potongan_pct`,
sedangkan `sampah_kg` dipotong terpisah di atasnya, jadi batas itu tidak pernah
melihat angka ini. Tiga baris @60 % juga lolos — masing-masing sah, bersama 180 %.

Sejak PR #25 `validate_grading_percentages()` menolak baris di luar 0–100 dan jumlah
di atas 100, dan `kg_dibayar` tidak pernah negatif. Kalau menambah kriteria baru,
jangan lewati penjaga ini: angkanya yang dibayar ke pemasok.

## 22. Enam penghalang berurutan antara tiket dan dokumen stok

Ditemukan 2026-09-21 saat membuktikan rantai AutoGrade → AutoERP di site produksi
yang baru lahir. Semuanya muncul **satu per satu**, masing-masing hanya setelah yang
sebelumnya ditutup, dan tidak satu pun menyebut yang berikutnya.

| # | Pesannya | Sebabnya |
|---|---|---|
| 1 | "Please set FFB Item, CPO Item, Kernel Item" | Item `TBS`/`CPO`/`PK` belum dibuat |
| 2 | "Please set FFB Receiving Warehouse, Internal FFB Transfer Income Account" | Belum diisi di Palm Mill Settings. `Internal` butuh **dua-duanya**; `External` cukup gudang |
| 3 | tombol **Receive Stock** tidak ada | Tiket harus **Submit** dulu (`weighbridge_ticket.js` menuntut `docstatus === 1`) |
| 4 | "The selected item cannot have Batch" | Item TBS perlu **Has Batch No** |
| 5 | "Group node warehouse is not allowed to select for transactions" | Gudang yang dipilih group node |
| 6 | "Item TBS has zero rate but 'Allow Zero Valuation Rate' is not enabled" | Belum ada **Item Price** TBS |

⚠️ **#4 — checkbox-nya tidak hilang, sectionnya kolaps.** "Has Batch No" ada di
**Serial Nos / Batches** yang tertutup di tab Inventory. Flag site
`enable_serial_and_batch_no_for_item` sudah `1` di **kedua** penyimpanannya; memeriksa
flag itu dan membersihkan cache adalah jalan buntu. **Jangan** centang "Automatically
Create New Batch": AutoGrade menamai batch sendiri `TBS-YYYYMMDD`
(`get_or_create_daily_batch`), sedangkan auto-create ERPNext memakai `AAAA.00001`.

⚠️ **#5 — site baru lahir tanpa gudang yang bisa dipakai.** `hide_seed_masters()`
menonaktifkan keempat gudang bawaan, dan `All Warehouses` yang tersisa adalah group
node. Sampai `after_install` membuat gudang sendiri, tiap site baru butuh satu gudang
dibuat dengan tangan:

```bash
bench --site <site> execute frappe.client.insert --args '[{"doctype":"Warehouse",
  "warehouse_name":"Gudang TBS","company":"<Company>",
  "parent_warehouse":"All Warehouses - <ABBR>","is_group":0}]'
```

⚠️ **#6 hanya PERINGATAN, bukan kegagalan** — Stock Entry tetap dibuat. Tapi
`harga_per_kg` **dikunci saat finalisasi** (`weighbridge_ticket.py`: `if not
self.harga_per_kg`) dan tidak pernah dibaca ulang, jadi tiket yang difinalisasi
sebelum Item Price ada bernilai **Rp 0 selamanya**: stoknya benar, pembukuannya
bohong. Menguji ulang berarti **truk baru**, bukan tiket yang sama.

UOM di Item Price harus sama dengan `stock_uom` Item — `get_price()` membacanya dari
sana, dan UOM yang berbeda membuat harganya tidak ketemu tanpa pesan apa pun.
