# Dokumentasi AutoERP

AutoERP adalah **fork ERPNext `version-16`** yang dipakai sebagai pembukuan pabrik
kelapa sawit. Semua yang khusus sawit hidup di satu modul: `erpnext/palm_mill/`.

⚠️ **Nama app di bench tetap `erpnext`, bukan `autoerp`.** Bench memasangnya sebagai
`apps/erpnext`, dan semua path Python `erpnext.*`. Ini disengaja supaya merge dari
upstream dan setiap `frappe.get_app("erpnext")` tetap jalan.

## Baca yang mana?

| Kamu | Mulai dari |
|---|---|
| Baru pertama kali dengar AutoERP | [`overview.md`](overview.md) — 10 menit, tanpa perlu install |
| Mau memasang di laptop | [`installation.md`](installation.md) |
| Mau tahu isi datanya apa saja | [`data-model.md`](data-model.md) |
| Mau tahu jalan TBS dari truk sampai jadi uang | [`ticket-flow.md`](ticket-flow.md) |
| Menyambungkan AutoGrade / sistem lain | [`autograde-api.md`](autograde-api.md) |
| Sudah terpasang, mau kerja harian | [`operations.md`](operations.md) |
| Mau ubah kode dan kirim PR | [`contributing.md`](contributing.md) |
| Menerbitkan token langganan untuk sebuah pabrik | [`lisensi-autograde.md`](lisensi-autograde.md) |
| Error dan tidak tahu kenapa | [`gotchas.md`](gotchas.md) — semua jebakan yang pernah memakan waktu |

## Dokumen rancangan (bukan panduan)

| Berkas | Isi |
|---|---|
| [`autograde-integration.md`](autograde-integration.md) | Rancangan asli kontrak AutoGrade ↔ AutoERP dari Mas Samuel. Panjang (589 baris) dan sebagian sudah berbeda dari kode. **Kalau bertentangan, kode yang menang** — bedanya dicatat di `autograde-api.md` §Beda dengan rancangan. |

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
