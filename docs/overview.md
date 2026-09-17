# Pengenalan AutoERP

Baca ini dulu. Tidak perlu install apa pun. ±10 menit.

## 1. AutoERP itu apa

Pembukuan pabrik kelapa sawit. Fork [ERPNext](https://github.com/frappe/erpnext)
`version-16` + satu modul buatan sendiri: `erpnext/palm_mill/`.

Yang dipakai dari ERPNext bawaan: pembelian, stok, batch, akuntansi, laporan
keuangan. Yang ditambahkan modul sawit: **tiket timbang**, sortasi, potongan,
master kebun/blok, laporan rendemen, dan pintu masuk buat AutoGrade.

## 2. Kenapa fork, bukan app terpisah

Keputusan terkunci 2026-09-13. Modul sawit menyentuh Purchase Receipt, Stock
Entry, Batch, dan Item Price secara dalam; sebagai app terpisah sambungannya
jadi rapuh tiap ERPNext naik versi. Harga yang dibayar: tiap merge dari upstream
ERPNext berpotensi konflik di berkas branding.

⚠️ **Nama app tetap `erpnext`.** Di bench dia jadi `apps/erpnext`, di site
dipasang sebagai `erpnext`, dan semua import `erpnext.*`. Cuma judul, logo, dan
ikon yang berbunyi "AutoERP".

## 3. Dua kotak, bukan satu

```
┌─ PC pabrik (boleh offline) ─────────┐      ┌─ Server ──────────────────┐
│  AutoGrade                          │      │  AutoERP                  │
│  kamera + AI + PLC + timbangan      │─────▶│  Frappe + MariaDB         │
│  konsol operator (port 8100)        │ HTTP │  ERP Desk (port 8000)     │
└─────────────────────────────────────┘      └───────────────────────────┘
```

Satu UI per lokasi, bukan satu UI untuk semua. Konsol operator **tidak bisa**
dipindah ke ERP Desk karena harus hidup saat internet putus, dibaca dari
beberapa meter di luar ruangan, dan menyentuh hardware (coil PLC, kamera).

**Butiran kiriman — jangan dibalik:**

| | Di mana | Kenapa |
|---|---|---|
| Per janjang (foto, verdict AI) | tetap di PC pabrik | Bukti. Jumlahnya ribuan per hari; ERP bukan tempat event |
| Rekap per truk | dikirim ke AutoERP | Ini angka yang masuk pembukuan |

Kalau butuh telusur sampai janjang, AutoERP menyimpan **tautan** (`autograde_url`),
bukan janjangnya.

## 4. Satu kunjungan truk, dari gerbang sampai jadi uang

| # | Di mana | Yang terjadi | Tiket jadi apa |
|---|---|---|---|
| 1 | Jembatan timbang | Truk masuk isi, ditimbang bruto | dibuat, **Waiting Weight** |
| 2 | Ramp | Buah diturunkan ke line grading | tetap |
| 3 | Line grading | Kamera menilai tiap janjang: ACC / REJ | tetap |
| 4 | Line grading | Janjang REJ **naik lagi ke truk**; AutoGrade menutup line | baris sortasi terisi |
| 5 | Jembatan timbang | Truk keluar **membawa yang ditolak** → tara | neto terisi, **Ready** |
| 6 | AutoERP | Hitung potongan, ambil harga, submit | **Finalised** |
| 7 | AutoERP | Purchase Receipt (beli) / Stock Entry (kebun sendiri) | dokumen stok tertaut |
| 8 | Kantor | Purchase Invoice, pembayaran | ERPNext biasa |

Yang penting di langkah 5: **tara sudah termasuk buah yang ditolak**, jadi neto
otomatis = buah yang benar-benar tinggal di pabrik. Buah ditolak tidak pernah
dibayar, tanpa perlu dihitung terpisah.

## 5. Uangnya dihitung bagaimana

Tiga hal berbeda, tiga tempat berbeda:

- **REJ (ditolak)** — naik lagi ke truk, terbawa tara, **di luar neto**. Tidak
  dibayar. Jumlahnya tetap dicatat buat statistik pemasok.
- **Sampah** — mengurangi **kilogram**, bukan harga.
- **Potongan mutu** — mengurangi **harga** lewat diskon di baris Purchase Receipt.

```
potongan %        = Σ (persen kriteria × bobotnya di Palm Mill Settings), dibatasi max
kg dibayar        = (neto − sampah) × (1 − potongan)
nilai             = kg dibayar × harga per kg
```

Bobot bawaan: Mentah **60**, Lewat Matang **15**, Tangkai Panjang **100** — artinya
tiap 1% tangkai panjang memotong 1% harga, tiap 1% mentah memotong 0,6%. Batas
atas 18%.

Contoh nyata (dikunci di test):

```
neto 9.160 kg, Mentah 9,95%, Tangkai Panjang 5,58%
potongan = 9,95×0,60 + 5,58×1,00 = 11,55%
dibayar  = 9.160 × (1 − 0,1155) = 8.102 kg  ×  Rp 2.850
```

## 6. Isi modulnya apa saja

| | Jumlah | Contoh |
|---|---|---|
| DocType | 11 | Weighbridge Ticket, Truck, Blok, AutoGrade Operator |
| Endpoint buat AutoGrade | 2 | `upsert_truck`, `upsert_visit` |
| Laporan | 1 | Oil Extraction Rate |
| Workspace | 1 | "Pabrik Kelapa Sawit" (7 kartu angka, 5 grafik, 10 pintasan) |
| Patch migrasi | 11 | `setup_palm_mill`, `palm_mill_language`, … |
| Test | 48 | `bench --site test_site run-tests --module erpnext.palm_mill.test_api` |

Rinciannya di [`data-model.md`](data-model.md).

## 7. Yang AutoERP **tidak** kerjakan

Supaya tidak salah cari:

- **Tidak menilai buah.** Itu AutoGrade (kamera + YOLO).
- **Tidak bicara ke timbangan atau PLC.** Program timbangan lapor ke AutoGrade,
  bukan ke ERP.
- **Tidak menyimpan foto janjang.** Cuma tautannya.
- **Tidak pernah dipasang on-prem di pabrik.** AutoERP hidup di server; pabrik
  boleh offline dan tetap bisa menimbang.

## 8. Lanjut ke mana

- Mau langsung pasang → [`installation.md`](installation.md)
- Mau paham datanya → [`data-model.md`](data-model.md)
- Mau paham aturan finalisasi → [`ticket-flow.md`](ticket-flow.md)
