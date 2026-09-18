---
name: doctype-palm-mill
description: Use when adding, renaming, or changing a DocType, field, or permission inside erpnext/palm_mill — including "tambah field", "bikin DocType baru", "kenapa field ini tidak muncul", "field ini mau dihapus", or migrating an existing site to a schema change. Also use before running bench migrate on a palm_mill change.
---

# Mengubah skema palm_mill

Modul ini hidup **di dalam fork ERPNext**, bukan app terpisah. Jadi setiap
perubahan skema harus bertahan terhadap `bench migrate`, dan terhadap rebase ke
`version-16` berikutnya.

## Aturan yang dilanggar paling sering

**Site lama tidak berubah sendiri.** Menambah field di `.json` cuma mengubah kode.
Site yang sudah ada baru ikut sesudah `bench --site <site> migrate`. Kalau
perubahannya butuh data lama diisi/dipindah, tulis **patch**, jangan
mengandalkan migrate.

**Site baru tidak menjalankan patch sama sekali.** `install_app()` menandai semua
patch selesai tanpa mengeksekusinya. Jadi apa pun yang cuma ada di patch **tidak
berlaku di site baru** — termasuk site produksi. Kalau kebijakannya harus berlaku
di mana-mana, taruh juga di `after_install`. Ini utang **E5**.

**Jangan `bench migrate` di checkout tanpa `erpnext/palm_mill`.** Frappe menghapus
DocType yang tidak bisa dia impor **beserta tabelnya**, diam-diam.

## Pola yang dipakai modul ini

| | |
|---|---|
| `module` di setiap `.json` | `Palm Mill` |
| Penamaan | `field:<fieldname>` kalau ada kunci alami (contoh: Truck = `field:plate_number`) |
| Role | `System Manager`, `Weighbridge Operator`, `Palm Mill Integration` — jangan mengarang role baru tanpa alasan |
| Lokasi | `erpnext/palm_mill/doctype/<snake_case>/` |
| Patch | `erpnext/patches/v17_0/palm_mill_<topik>.py`, didaftarkan di `patches.txt` |

DocType di modul ini **bukan** `custom` — dia berkas app, ikut git, ikut rebase.

## Field yang tidak dipakai: sembunyikan, jangan hapus

Field bawaan ERPNext seperti supplier/batch/warehouse **tidak bisa dihapus** —
akuntansi, kontrak API, dan telusur bergantung padanya. Sembunyikan lewat
Property Setter, dan **tiga properti sekaligus**: `hidden` saja tidak cukup
(field tetap wajib / tetap ikut laporan). Lihat memory proyek
`project_field_tidak_dipakai_autoerp`.

## Sesudah mengubah skema

```bash
bench --site <site> migrate          # terapkan ke site
bench --site <site> clear-cache
bench build                          # hanya kalau menyentuh JS atau .po
```

Terjemahan: `bench migrate` **tidak** mengompilasi `.po`. Sesudah menyentuh
terjemahan, `bench build` atau `compile-po-to-mo --app erpnext --force`, lalu
`clear-cache`. Baris `Translation` dikirim sebagai **fixtures** (`hooks.py`) dan
mengalahkan setiap `.po`.

## Presisi angka

`float_precision` = **2**, diset oleh `palm_mill_precision`. Pabrik membaca
kilogram dan persen paling banyak dua angka di belakang koma. Jangan menaikkan ini
per-field tanpa alasan; satu setelan ini mengatur semua Float dan Percent.

## Uji

```bash
bench --site <site> run-tests --app erpnext --module erpnext.palm_mill.doctype.<nama>.test_<nama>
```

⚠️ `--test` bisa keluar dengan status 0 padahal **nol test dijalankan**. Selalu
baca jumlah test yang dilaporkan, jangan percaya exit code saja.

Sesudah mengubah skema yang menyentuh alur kunjungan, jalankan juga uji ujung-ke-ujung
`../docs/runbooks/2026-09-16-pindah-v16/e2e_visit.py` di workspace sawit — dia
membuktikan satu kunjungan truk benar-benar jadi Purchase Receipt dan Stock Entry.
