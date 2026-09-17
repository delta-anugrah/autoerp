# Alur tiket — dari truk sampai jadi dokumen stok

Semua logika di `erpnext/palm_mill/doctype/weighbridge_ticket/weighbridge_ticket.py`
(461 baris). Dokumen ini menjelaskan isinya tanpa perlu membaca kodenya.

## 1. Tiket yang mana? — pencocokan kunjungan

Masalahnya: AutoGrade mengirim **tiga kali** untuk satu truk (gerbang, sortasi
tutup, keluar), plus kiriman ulang harian. Semuanya harus mendarat di satu tiket.

`_find_ticket()` mencari berurutan, berhenti di yang pertama ketemu:

1. `autograde_visit_id` — kunci paling kuat
2. `scale_ticket_no` — tiket yang diketik tangan cuma punya ini
3. `autograde_assignment_id`
4. **Jendela waktu**: tiket draft truk yang sama, perusahaan sama, tanggal sama,
   yang rentang timbangnya (dilebarkan `match_window_hours`, bawaan 2 jam)
   bertumpang tindih
5. Tidak ada → tiket draft baru

⚠️ **Jebakan yang sudah pernah memakan tonase (diperbaiki PR #7).** Truk yang
sama bisa datang dua kali dalam dua jam. Kalau kunjungan kedua mengadopsi tiket
kunjungan pertama, tonase pertama tertimpa dan hilang dari pembukuan tanpa pesan
apa pun.

Aturannya sekarang: tiket yang **sudah** membawa `autograde_visit_id` atau
`scale_ticket_no` **berbeda** tidak pernah diadopsi. Kunci yang masih kosong
tetap bisa diadopsi — itu justru yang menyambungkan kiriman "keluar" dan tiket
ketikan tangan ke kunjungannya.

## 2. Berat masuk

`_apply_weighing()`:

- `time_in` **wajib** — dia yang menentukan tanggal tiket. Tanpa itu ditolak.
- Neto dihitung **hanya kalau tara sudah ada**; kalau belum, neto = 0 dan tiket
  duduk di `Waiting Weight`.
- `weight_received_at` dicap tiap kiriman.

Waktu ISO dengan offset dikonversi ke waktu lokal site lalu disimpan polos
(`to_site_datetime`).

## 3. Sortasi masuk

`_apply_grading()` **mengganti** tiga baris milik AI dan **membiarkan** baris
ketikan operator:

```
AI       : Mentah, Tangkai Panjang, Matang
operator : Sampah, Lewat Matang
```

`Matang` tidak dikirim AutoGrade — dihitung sebagai sisa:

```
Matang = max(0, 100 − Mentah − Tangkai Panjang − (baris operator))
```

Persentase diambil dari `pct` kalau dikirim, kalau tidak dihitung dari `counts`
dibagi `counts.total`.

## 4. Hitungan potongan

`compute_deductions()` — rumus lengkapnya:

```python
potongan = Σ ( persen[kriteria] / 100  ×  bobot[kriteria] / 100 )
potongan = min(potongan, max_potongan_pct / 100)          # batas 18%

berat_kg per baris  = neto × persen / 100
sampah_kg           = round(neto × persen_sampah / 100)
kg_dibayar          = round( (neto − sampah_kg) × (1 − potongan) )
nilai               = round( kg_dibayar × harga_per_kg, 2 )
```

Kalau sortasi tidak ada **dan** `grading_missing` menyala → pakai
`default_potongan_pct`. Kalau tidak ada dua-duanya → potongan 0.

**Harga** (`get_price()`): Item Price untuk `tbs_item` pada `ticket_date` —
harga khusus supplier dulu, baru harga umum di price list yang sama.

## 5. Finalisasi

`try_finalize()` — dipanggil setelah tiap kiriman AutoGrade **dan** oleh
scheduler tiap 15 menit.

```
Tidak jalan kalau: bukan draft, atau neto ≤ 0
Sortasi belum ada?
  └─ belum lewat grading_timeout_hours (6 jam sejak time_out)  → berhenti, tunggu
  └─ sudah lewat  → grading_missing = 1, lanjut
Hitung ulang, simpan
harga_per_kg ≤ 0?  → tulis Error Log, BERHENTI (tidak submit)
submit()  →  create_stock_documents()
```

⚠️ **Tiket tanpa harga tidak pernah difinalisasi**, cuma meninggalkan Error Log.
Kalau tiket menumpuk di `Ready`, cek Item Price TBS untuk tanggal itu duluan.

## 6. Dokumen stok

`create_stock_documents()` — idempoten, satu dokumen per tiket:

| Sumber TBS | Dokumen | Kenapa |
|---|---|---|
| `External` (dibeli) | **Purchase Receipt** | ada hutang ke pemasok |
| `Internal` (kebun sendiri) | **Stock Entry** (Material Receipt) | tidak ada pembayaran, cuma perpindahan |

**Purchase Receipt** (`make_purchase_receipt`):

| Isi | Dari |
|---|---|
| `qty` | neto − sampah_kg |
| `price_list_rate` | `harga_per_kg` |
| **`discount_percentage`** | **`potongan_pct`** ← ini cara potongan jadi uang |
| `batch_no` | `TBS-YYYYMMDD` (satu batch per hari terima) |
| `custom_grading_note` | ringkasan sortasi terbaca manusia |
| `posting_date` / `posting_time` | `ticket_date` / `time_in` |
| `custom_weighbridge_ticket` | nama tiket (tautan balik) |

Ditambah dimensi akuntansi yang ada (`sumber_tbs`, `sertifikasi`, dan bila ada
blok: `blok`, `kebun`, `divisi`). Field yang tidak ada di site itu dibuang
diam-diam (`only_known_fields`) supaya site tanpa dimensi tetap jalan.

**Stock Entry** (`make_stock_entry`): `Material Receipt`, `basic_rate` = harga
per kg, akun lawan `inti_expense_account`, cost center dicari dari nama
`"{kebun} Divisi {divisi}"`.

### Batch harian

`get_or_create_daily_batch()` → `TBS-YYYYMMDD`, satu per hari penerimaan.

⚠️ Batch dibuat **dengan referensi ke tiket pembuatnya**. Batch tanpa referensi
akan "diadopsi" Purchase Receipt pertama yang memakainya, dan ERPNext lalu
menghapusnya saat receipt itu dibatalkan — padahal tiket lain hari itu masih
memakai batch yang sama.

## 7. Membatalkan

Tiket menaut ke dokumen stok dan dokumen stok menaut balik — biasanya Frappe
menolak membatalkan keduanya. Hook `on_stock_document_cancel` melonggarkan itu:

1. Batalkan Purchase Receipt / Stock Entry → **boleh**, itu langkah sah pertama.
2. Tautan di tiket dikosongkan; tiket **tetap Finalised**.
3. Tombol **Receive Stock** muncul lagi untuk membuat penggantinya.

Peran `Palm Mill Integration` sengaja **tidak** punya izin cancel — pembatalan
adalah keputusan manusia.

## 8. Kiriman setelah finalisasi

`_after_finalisation()` — **tiket yang sudah final tidak pernah ditulis ulang.**

| Yang datang | Yang terjadi |
|---|---|
| Angka sama persis | dijawab "visit unchanged", selesai |
| Sortasi berubah | `grading_revised = 1` + Comment berisi sebelum→sesudah |
| Berat berubah | Comment saja |
| Tiket sudah dibatalkan | dijawab "ticket cancelled; visit ignored" |

Backoffice yang memutuskan apa yang harus dilakukan; sistem tidak mengubah
pembukuan sendiri.

## 9. Scheduler

`finalize_due_tickets()` tiap 15 menit (`hooks.py` `scheduler_events`):
menyapu semua draft ber-neto > 0 dan mencoba memfinalisasi. Commit per tiket
yang berhasil; yang gagal di-rollback dan ditulis ke Error Log — satu tiket
rusak tidak menghentikan sisanya.

⚠️ Scheduler hanya jalan kalau ada **worker**. `bench start` menjalankannya;
`bench serve` sendirian tidak.
