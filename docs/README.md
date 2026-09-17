# Dokumentasi AutoERP

AutoERP adalah **fork ERPNext `version-16`** yang dipakai sebagai pembukuan pabrik
kelapa sawit. Semua yang khusus sawit hidup di satu modul: `erpnext/palm_mill/`.

⚠️ **Nama app di bench tetap `erpnext`, bukan `autoerp`.** Bench memasangnya sebagai
`apps/erpnext`, dan semua path Python `erpnext.*`. Ini disengaja supaya merge dari
upstream dan setiap `frappe.get_app("erpnext")` tetap jalan.

## Baca yang mana?

| Kamu | Mulai dari |
|---|---|
| Baru pertama kali dengar AutoERP | [`pengenalan.md`](pengenalan.md) — 10 menit, tanpa perlu install |
| Mau memasang di laptop | [`instalasi.md`](instalasi.md) |
| Mau tahu isi datanya apa saja | [`model-data.md`](model-data.md) |
| Mau tahu jalan TBS dari truk sampai jadi uang | [`alur-tiket.md`](alur-tiket.md) |
| Menyambungkan AutoGrade / sistem lain | [`api-autograde.md`](api-autograde.md) |
| Sudah terpasang, mau kerja harian | [`operasional.md`](operasional.md) |
| Mau ubah kode dan kirim PR | [`kontribusi.md`](kontribusi.md) |
| Error dan tidak tahu kenapa | [`jebakan.md`](jebakan.md) — semua jebakan yang pernah memakan waktu |

## Dokumen rancangan (bukan panduan)

| Berkas | Isi |
|---|---|
| [`autograde-integration.md`](autograde-integration.md) | Rancangan asli kontrak AutoGrade ↔ AutoERP dari Mas Samuel. Panjang (578 baris) dan sebagian sudah berbeda dari kode. **Kalau bertentangan, kode yang menang** — bedanya dicatat di `api-autograde.md` §Beda dengan rancangan. |
| [`dev-setup.md`](dev-setup.md) | Panduan lama membangun site dari dump database privat. Masih berguna kalau kamu memang butuh dump itu; untuk instalasi biasa pakai `instalasi.md`. |

## Peta singkat

```
┌─ PC pabrik (boleh offline) ─────────┐      ┌─ Server ──────────────────┐
│  AutoGrade                          │      │  AutoERP  ← dokumen ini   │
│  kamera + AI + PLC + timbangan      │─────▶│  Frappe/ERPNext + MariaDB │
│  konsol operator (port 8100)        │ HTTP │  ERP Desk (port 8000)     │
└─────────────────────────────────────┘      └───────────────────────────┘
```

Yang dikirim ke AutoERP adalah **rekap per truk**, bukan per janjang. Foto dan
verdict tiap janjang tetap di PC pabrik sebagai bukti; AutoERP cuma menerima
tautan ke sana. Alasannya: ERP itu buku besar, bukan event store.

## Istilah

| Istilah | Artinya |
|---|---|
| TBS | Tandan Buah Segar — buah sawit yang dibeli pabrik |
| Janjang | Satu tandan TBS |
| Bruto / tara / neto | Berat truk isi / kosong / selisihnya = TBS yang masuk |
| Potongan | Persentase pengurangan harga karena mutu buah jelek |
| Sortasi / grading | Penilaian mutu buah |
| OER / KER | Oil / Kernel Extraction Rate — rendemen minyak dan inti |
| Sumber TBS | `Internal` (kebun sendiri) atau `External` (dibeli) |
| bench | Perkakas CLI Frappe yang menjalankan site |
| DocType | Definisi tabel + form di Frappe |
| Desk | Antarmuka admin ERPNext di browser |
