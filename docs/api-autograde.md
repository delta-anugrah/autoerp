# API — menyambungkan AutoGrade ke AutoERP

Kode: `erpnext/palm_mill/api.py`. **AutoGrade satu-satunya sistem luar yang
bicara ke AutoERP.** Program timbangan lapor ke AutoGrade, bukan ke sini.

## Autentikasi

Header Frappe biasa:

```
Authorization: token <api_key>:<api_secret>
Content-Type: application/json
```

Akunnya **System User** dengan peran `Palm Mill Integration` + `Purchase User` +
`Stock User`. Dua peran terakhir wajib karena finalisasi membuat Purchase
Receipt / Stock Entry lewat pemeriksaan izin ERPNext biasa.

Membuat akunnya:

```bash
bench --site pks.localhost execute erpnext.palm_mill.setup.create_integration_user \
  --kwargs '{"email": "autograde@pks.local", "full_name": "AutoGrade"}'
```

⚠️ **Jangan jalankan ulang perintah itu cuma buat melihat kuncinya** — dia
**merotasi** `api_secret`, dan semua AutoGrade yang masih memegang yang lama
langsung 401. Buat melihat tanpa merotasi:

```bash
make key-show     # mencetak ERP_API_KEY= dan ERP_API_SECRET= siap tempel ke .env
```

## Endpoint

Cuma **dua** yang dipakai AutoGrade. Keduanya POST-only; GET dijawab 403.

### `upsert_truck` — plat baru jadi truk

```
POST /api/method/erpnext.palm_mill.api.upsert_truck
```

| Argumen | Wajib | Catatan |
|---|---|---|
| `plate_number` | ya | |
| `autograde_id` | tidak | |
| `supplier` | tidak | cuma dipakai kalau truknya **baru** |
| `vehicle_class` | tidak | |
| `capacity` | tidak | **diterima lalu diabaikan** |
| `site` | tidak | nama Company |

Balasan: `{"name", "supplier", "vehicle_class"}`

**Truk yang sudah ada tidak pernah ditimpa.** AutoERP pemilik master data; yang
diisi cuma `autograde_id` kalau masih kosong.

### `upsert_visit` — satu kunjungan truk

```
POST /api/method/erpnext.palm_mill.api.upsert_visit
```

Dikirim AutoGrade **tiga kali** per kunjungan (`stage`: `gate`, `grading`,
`departed`) dan **diulang tiap hari** sebagai jaring pengaman. Tiap kiriman
adalah **penggantian penuh** untuk bagian yang dibawanya.

| Argumen | Wajib | Isi |
|---|---|---|
| `visit_id` | ya | kunci utama pencocokan |
| `truck` | ya | objek: `plate_number` / `erp_name`, `autograde_id` |
| `weighing` | ya | objek: `time_in` (**wajib**), `time_out`, `gross_kg`, `tare_kg`, `driver_name` |
| `grading` | tidak | objek: `counts`, `pct`, `assignment_id`, `detail_url` |
| `site` | tidak | Company |
| `supplier_erp_name` | tidak | |
| `scale_ticket_no` | tidak | nomor slip timbangan |
| `stage` | tidak | jejak saja |
| `emitted_at` | tidak | |

Contoh isi:

```json
{
  "visit_id": "b7c1…",
  "stage": "grading",
  "truck": {"plate_number": "B 1234 XY", "autograde_id": "…"},
  "weighing": {"time_in": "2026-09-10T07:12:00+07:00", "gross_kg": 14560},
  "grading": {
    "assignment_id": "…",
    "counts": {"total": 412, "acc": 371, "rej": 41,
               "mentah": 41, "tangkai_panjang": 23, "manual_reject": 3},
    "pct": {"mentah": 9.95, "tangkai_panjang": 5.58},
    "detail_url": "https://captures.smagri.id/viewer.html?visit=…"
  }
}
```

Balasan: `{"ticket", "status", "truck", "finalised", "stage"}` — atau dengan
`note` / `revised` kalau tiketnya sudah final.

⚠️ **`weighing.time_in` wajib.** Dia yang menentukan tanggal pembukuan tiket.
Tanpa itu permintaan ditolak.

### Endpoint lain (bukan buat AutoGrade)

| Metode | Buat apa |
|---|---|
| `erpnext.palm_mill.api.set_language` | tombol ganti bahasa id/en di navbar |
| `erpnext.palm_mill.qr_card.cards` | halaman cetak kartu QR |
| `…weighbridge_ticket.make_stock_documents` | tombol "Receive Stock" |

**Tidak ada satu pun `allow_guest`** di modul ini.

## Tarik master data — REST bawaan Frappe

Tidak ada endpoint khusus. AutoGrade menarik pakai REST biasa dengan kursor
`modified`:

```
GET /api/resource/Supplier?fields=[...]&filters=[["modified",">","<kursor>"]]
    &limit_page_length=500&order_by=modified asc
GET /api/resource/Truck?fields=["name","plate_number","plate_normalized",...]
GET /api/resource/AutoGrade Operator?fields=["email","full_name","role","active","password_hash"]
```

Itulah kenapa `Palm Mill Integration` punya izin **baca** di `AutoGrade Operator`,
dan kenapa `password_hash` disimpan sebagai field `Data` biasa — supaya bisa
ditarik dan diverifikasi di pabrik saat internet putus.

## Jejak tiap panggilan

Dekorator `logged` di kedua endpoint:

- **Berhasil** → satu baris **Integration Request** (`service_name = "AutoGrade"`,
  menunjuk ke tiketnya)
- **Gagal** → **Error Log** berisi payload penuh + traceback, lalu error
  dilempar ulang

Jadi kalau AutoGrade bilang "sudah saya kirim", cek Integration Request di Desk.

## Kartu QR truk

Sejak 2026-09-17 kartu QR **dicetak dari ERP Desk**, bukan dari konsol pabrik —
backoffice mendaftarkan truknya di sini, jadi tombol cetaknya di sini juga.
Konsol AutoGrade tetap punya endpoint `qr.png` sebagai cadangan kalau internet
pabrik mati dan ada truk baru datang.

- Dari form truk: tombol **Print QR Card**
- Dari daftar truk: pilih beberapa → **Print QR Cards**
- Halaman `/truck_qr_cards?trucks=[...]`, cetak lewat dialog browser

**Isi kodenya `plate_normalized` saja.** Bukan id ERP (truk pinjaman belum punya
id, dan gerbang harus tetap jalan saat sambungan ke server putus — plat berarti
sesuatu sendiri, `TRK-0042` tidak). Bukan supplier atau sopir juga: keduanya
berubah di ERP setelah kartu tertempel di kaca, dan kartunya jadi berbohong.

⚠️ **Regex plat wajib kembar.** `SCANNABLE_PLATE` di `erpnext/palm_mill/utils.py`
harus identik dengan `_BENTUK_PLAT` di `domain/qr.py` milik AutoGrade. Test
`test_scannable_plate_matches_autograde` mengunci itu — kalau diubah di sini,
ubah di sana **dalam PR yang sama**.

Plat yang tidak lolos regex tetap boleh disimpan (cuma peringatan), tapi kartunya
tidak dicetak dan truk itu ditimbang tanpa scan.

## Beda dengan rancangan `autograde-integration.md`

Rancangan itu ditulis 2026-09-10 dan sebagian sudah didahului kode.
**Kalau bertentangan, kode yang menang.**

| Rancangan bilang | Kenyataannya |
|---|---|
| "tiga endpoint" (§7.1) | **dua** POST untuk AutoGrade (`upsert_truck`, `upsert_visit`) |
| Ada "Interface D" (dirujuk di §E dan §5) | **Tidak pernah didefinisikan.** Dilebur ke interface C — satu pesan kunjungan membawa timbangan dan sortasi sekaligus |
| DocType `TBS Grading Rule` (single) | Yang ada: `Palm Mill Settings` (single) + tabel anak `Palm Mill Grading Rule` |
| `source` = Manual / AutoGrade | Ada nilai ketiga: `Scale` |
| Status tiket tanpa `Cancelled` | `Cancelled` ada |
| Kriteria AI termasuk `Sampah` (§7.1) | Kode: cuma `Mentah`, `Tangkai Panjang`, `Matang`. **Sampah ditimbang, bukan dilihat kamera** — belum disamakan (item E2) |
| "Weighbridge Ticket tanpa controller logic" (§0) | Benar saat ditulis; sekarang controllernya 461 baris |
| Branch `feat/palm-mill-module` | Sudah merge; kerjaan sekarang di `staging` |

## Menguji tanpa AutoGrade

```bash
KEY=$(make key-show | sed -n 's/^ERP_API_KEY=//p')
SECRET=$(make key-show | sed -n 's/^ERP_API_SECRET=//p')

curl -s -X POST http://pks.localhost:8000/api/method/erpnext.palm_mill.api.upsert_visit \
  -H "Authorization: token $KEY:$SECRET" \
  -H 'Content-Type: application/json' \
  -d '{
    "visit_id": "coba-001",
    "truck": {"plate_number": "B 1234 XY"},
    "weighing": {"time_in": "2026-09-17T07:00:00+07:00", "gross_kg": 14560}
  }'
```

Lalu kirim lagi dengan `tare_kg`, `time_out`, dan bagian `grading` — tiketnya
harus tetap satu dan akhirnya jadi `Finalised`.
