# Model data — 11 DocType modul Palm Mill

Semua ada di `erpnext/palm_mill/doctype/`. Satu DocType = satu folder berisi
`.json` (skema, sumber kebenaran tabel), `.py` (logika server), kadang `.js`
(perilaku form) dan `test_*.py`.

## Peta singkat

```
Weighbridge Ticket  ← dokumen inti, satu per kunjungan truk
├── grading[]       → Weighbridge Grading   (tabel anak: kriteria + persen)
├── truck           → Truck                 → Supplier (bawaan ERPNext)
├── blok            → Blok                  → Kebun, Divisi, Sertifikasi
├── sumber_tbs      → Sumber TBS            (cuma 2 baris: Internal, External)
├── purchase_receipt → Purchase Receipt     (bawaan ERPNext)
└── stock_entry      → Stock Entry          (bawaan ERPNext)

Palm Mill Settings  ← Single, semua setelan pabrik
└── grading_rules[] → Palm Mill Grading Rule (tabel anak: kriteria + bobot potongan)

AutoGrade Operator  ← akun login konsol operator di pabrik
```

---

## 1. Weighbridge Ticket — tiket timbang

Dokumen inti. **Satu kunjungan truk = satu tiket.** Berat dan sortasi menempel
sendiri-sendiri, urutan kedatangannya bebas.

- **Submittable**: ya. Draft → Submit (Finalised) → Cancel.
- **Penamaan**: `WB-.YYYY.-.#####` → `WB-2026-00001`
- **Riwayat perubahan**: dicatat (`track_changes`)

| Kelompok | Field | Tipe | Catatan |
|---|---|---|---|
| Kepala | `ticket_date` | Date | wajib; menentukan tanggal pembukuan |
| | `company` | Link Company | wajib |
| | `status` | Select | read-only, diturunkan: Waiting Weight / Waiting Grading / Ready / Finalised / Cancelled |
| Sumber | `sumber_tbs` | Link Sumber TBS | wajib; **diturunkan**, bukan diketik (lihat §aturan) |
| | `supplier` | Link Supplier | kosong = buah kebun sendiri |
| | `blok` | Link Blok | buat TBS Internal |
| | `sertifikasi` | Link Sertifikasi | ikut dari blok kalau kosong |
| Truk | `truck` | Link Truck | |
| | `driver_name` | Data | ikut dari truk |
| | `time_in` / `time_out` | Time | |
| Berat | `gross_weight_kg` / `tare_weight_kg` / `net_weight_kg` | Float | neto = bruto − tara |
| Sortasi | `grading` | Table | baris kriteria + persen |
| | `sampah_kg` | Float | mengurangi kg, bukan harga |
| | `potongan_pct` | Percent | hasil hitungan |
| | `net_after_deduction_kg` | Float | kg yang dibayar |
| Uang | `harga_per_kg` | Currency | dari Item Price kalau kosong |
| | `nilai` | Currency | kg dibayar × harga |
| Tautan | `purchase_receipt` / `stock_entry` | Link | read-only, diisi saat finalisasi |
| | `catatan` | Small Text | |
| Integrasi | `scale_ticket_no` | Data | nomor slip timbangan manual |
| | `weight_received_at` / `grading_received_at` | Datetime | kapan AutoGrade mengirim |
| | `grading_missing` | Check | sortasi tidak pernah datang, dipakai potongan bawaan |
| | `grading_revised` | Check | AutoGrade mengubah sortasi **setelah** finalisasi |
| | `autograde_visit_id` / `autograde_assignment_id` | Data | kunci pencocokan |
| | `autograde_url` | Data/URL | tautan ke detail per janjang di AutoGrade |
| | `grading_total` / `grading_acc` / `grading_rej` | Int | jumlah janjang |

**Hak akses**: System Manager (penuh) · Weighbridge Operator (penuh) ·
**Palm Mill Integration** (baca/tulis/buat/**submit**, tapi **tidak boleh cancel
atau delete** — integrasi tidak boleh membatalkan pembukuan).

**Tombol di form** (`weighbridge_ticket.js`):
- **Receive Stock** — muncul kalau sudah submit tapi dokumen stok belum ada
  (tiket yang diketik tangan).
- **Open AutoGrade** — buka `autograde_url` di tab baru.

### Aturan turunan (`validate`)

Tiga hal dihitung sendiri, jangan diketik:

1. **`supplier`** kosong → ambil pemilik truk.
2. **`sumber_tbs`** → `sumber_for_supplier()`: ada supplier = `External`, tidak
   ada = `Internal`. Nilai yang diketik dan bertentangan **ditimpa**. Beda
   plasma vs agen hidup di `supplier_group` bawaan ERPNext, bukan di sini.
3. **`sertifikasi`** kosong → ikut `blok.sertifikasi`.

### Status

| Status | Kapan |
|---|---|
| Waiting Weight | neto ≤ 0 |
| Waiting Grading | neto ada, sortasi belum, `grading_missing` belum dinyalakan |
| Ready | berat + sortasi lengkap, tinggal finalisasi |
| Finalised | `docstatus = 1` |
| Cancelled | `docstatus = 2` |

---

## 2. Weighbridge Grading — baris sortasi (tabel anak)

| Field | Tipe | Catatan |
|---|---|---|
| `kriteria` | Select | Mentah / Tangkai Panjang / Matang / Lewat Matang / Sampah |
| `persen` | Percent | |
| `berat_kg` | Float | dihitung: neto × persen |

⚠️ **Tiga kriteria pertama milik AI**, dua terakhir diketik operator. Tiap
kiriman AutoGrade **mengganti** baris Mentah/Tangkai Panjang/Matang dan
**membiarkan** Sampah/Lewat Matang. Kamera tidak bisa melihat sampah — sampah
ditimbang, bukan dilihat.

---

## 3. Truck — truk

- **Penamaan**: `field:plate_number` → nama dokumennya **adalah** platnya
  (`B 5455 DK`)

| Field | Tipe | Catatan |
|---|---|---|
| `plate_number` | Data | wajib, ejaan tampilan (boleh spasi) |
| `supplier` | Link Supplier | pemilik; kosong = truk kebun sendiri |
| `vehicle_class` | Select | Colt Diesel / Dump Truck / Tronton |
| `driver_name` | Data | |
| `plate_normalized` | Data | read-only, huruf+angka saja, HURUF BESAR |
| `autograde_id` | Data | read-only |
| `source` | Select | Manual / AutoGrade / Scale — jejak asal saja |

**Kunci lintas sistem adalah `plate_normalized`**, bukan `plate_number`.
`normalize_plate()` membuang semua selain huruf dan angka lalu meng-uppercase.
Fungsi ini **wajib identik** dengan `plateNormalizer` di AutoGrade.

**Plat ganda ditolak** (`DuplicateEntryError`) berdasarkan plat ternormalisasi —
jadi `B 1234 XY` dan `b1234xy` adalah truk yang sama.

**Plat aneh cuma diperingatkan, tidak diblokir.** Plat dinas, plat lama, dan
plat luar daerah bentuknya beda-beda dan itu sah. Yang muncul peringatan oranye
"kartu QR-nya tidak akan terbaca di gerbang" — backoffice yang memutuskan.

---

## 4. Palm Mill Settings — setelan pabrik (Single)

Satu-satunya tempat angka kebijakan. `Weighbridge Operator` cuma boleh baca.

| Field | Bawaan | Buat apa |
|---|---|---|
| `tbs_item` / `cpo_item` / `kernel_item` | TBS / CPO / PK | Item ERPNext |
| `tbs_warehouse` | — | gudang penerimaan TBS |
| `purchase_cost_center` | — | cost center pembelian |
| `buying_price_list` | — | daftar harga beli TBS |
| `inti_expense_account` | — | akun lawan buat TBS kebun sendiri |
| `grading_rules[]` | Mentah 60, Lewat Matang 15, Tangkai Panjang 100 | bobot potongan per 1% kriteria |
| `max_potongan_pct` | 18 | batas atas potongan |
| `default_potongan_pct` | 0 | dipakai kalau sortasi tidak pernah datang |
| `grading_timeout_hours` | 6 | setelah ini tiket difinalisasi tanpa sortasi |
| `match_window_hours` | 2 | lebar jendela pencocokan tiket |
| `create_stock_documents_on_submit` | **0 (mati)** | kalau nyala, submit langsung bikin dokumen stok |

---

## 5. Palm Mill Grading Rule — bobot potongan (tabel anak)

`kriteria` (Select, sama 5 pilihan) + `deduction_pct` (Percent). Baca:
"tiap 1% kriteria ini memotong sekian persen harga".

---

## 6. AutoGrade Operator — akun konsol pabrik

Akun yang dipakai operator login di **konsol AutoGrade**, bukan di ERP Desk.
AutoERP yang memiliki dan meng-hash; AutoGrade menariknya lalu memverifikasi
**di pabrik, offline**.

| Field | Tipe | Catatan |
|---|---|---|
| `email` | Data/Email | wajib, jadi nama dokumen, dinormalkan huruf kecil |
| `full_name` | Data | wajib |
| `active` | Check | bawaan nyala |
| `role` | Select | `operator` / `support` — `support` membuka menu developer konsol |
| `new_password` | Data/Password | **input form saja**, tidak pernah disimpan |
| `password_hash` | Data | read-only, hash passlib |

⚠️ **Kenapa hash-nya `Data` biasa, bukan field `Password`?** Field `Password`
Frappe disimpan di tabel `__Auth` yang sengaja tidak pernah dilayani lewat REST.
Kalau dipakai, AutoGrade tidak bisa menariknya dan login offline mustahil. Yang
keluar dari site cuma hash `pbkdf2_sha256`, tidak pernah sandi asli.

Dua penjagaan di controller:
- `before_naming` menormalkan email **sebelum** nama dokumen diambil. Kalau
  ditaruh di `validate` sudah telat: `Operator.DUA@x` dan `operator.dua@x` jadi
  dua akun dengan dua sandi.
- `new_password` di-hash lalu **dikosongkan** sebelum disimpan. `track_changes`
  nyala, jadi sandi mentah yang tertinggal akan abadi di riwayat versi.

Minimal 8 karakter, satu aturan dipakai dua jalan masuk (form dan `set_password`).

---

## 7–11. Master kebun (sederhana, System Manager saja)

| DocType | Penamaan | Field |
|---|---|---|
| **Kebun** | `field:title` | `title` |
| **Divisi** | `field:title` | `title` |
| **Sertifikasi** | `field:title` | `title` |
| **Sumber TBS** | `field:title` | `title` — cuma 2 baris: `Internal`, `External`, dibuat saat install |
| **Blok** | `field:blok_code` | `blok_code`, `kebun`, `divisi` (wajib), `luas_ha`, `tahun_tanam`, `jumlah_pokok`, `sertifikasi` |

⚠️ **Sumber TBS wajib punya dua baris itu.** `sumber_tbs` di tiket wajib diisi
dan menunjuk ke sini; site tanpa keduanya **tidak bisa menerima satu kunjungan
pun**. `after_install` membuatnya; site lama dapat lewat patch.

---

## Field tambahan di DocType bawaan ERPNext

Dibuat `erpnext/palm_mill/setup.py` saat install:

| Induk | Field | Tipe | Buat apa |
|---|---|---|---|
| Batch | `custom_source_batches` | Small Text (ro) | batch asal saat repack |
| Batch | `custom_source_stock_entry` | Link Stock Entry (ro) | |
| Batch | `custom_sertifikasi` | Data | campuran sertifikasi TBS pembentuk batch |
| Purchase Receipt Item | `custom_grading_note` | Small Text | ringkasan sortasi terbaca manusia |
| Purchase Receipt | `custom_weighbridge_ticket` | Link Weighbridge Ticket | tautan balik |

Modul ini **tidak** mengirim Property Setter apa pun.

## Peran

| Peran | Dibuat oleh | Isi |
|---|---|---|
| `Weighbridge Operator` | modul | krani timbang: tiket, truk, baca master |
| `Palm Mill Integration` | modul | akun mesin AutoGrade |

Keduanya dapat izin **baca** ke Supplier, Blok, Kebun, Divisi, Sumber TBS,
Sertifikasi. Tanpa itu sidebar menampilkan judul "Kebun & Blok" kosong tanpa isi
— Frappe membuang item sidebar yang gagal cek izin, diam-diam.

Akun integrasi juga memegang `Purchase User` + `Stock User`, karena finalisasi
membuat Purchase Receipt / Stock Entry lewat pemeriksaan izin ERPNext biasa.

## Laporan, workspace, grafik

- **Laporan**: `Oil Extraction Rate` — membaca Stock Entry ber-`purpose=Repack`,
  menghitung OER = CPO/TBS dan KER = inti/TBS per hari.
- **Workspace** `Pabrik Kelapa Sawit`: 7 kartu angka (OER rata-rata, TBS
  diterima, jumlah tiket, nilai pembelian, piutang, hutang, penjualan),
  5 grafik, 10 pintasan. Navigasinya di sidebar, bukan di `links`.
- **Tidak ada print format.** Kartu QR truk adalah **halaman web**
  (`/truck_qr_cards`), bukan dokumen — kartunya grid gambar yang digunting,
  dan dialog cetak browser sudah cukup.
