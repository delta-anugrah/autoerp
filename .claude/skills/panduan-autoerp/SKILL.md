---
name: panduan-autoerp
description: Use when working on AutoERP (repo autoerp, the ERPNext version-16 fork with module palm_mill) — finding where something lives, running the bench or the tests, adding or changing a DocType, touching the AutoGrade endpoints, or before running any bench command. Also use when the user asks what AutoERP is, why the app is called erpnext, how a truck visit becomes a Purchase Receipt, or where a topic is documented.
---

# Panduan AutoERP — peta untuk pemegang baru

Sumber utama: **`docs/README.md`** dan tujuh panduan di sampingnya (Bahasa
Indonesia). Baca bagian yang relevan dari situ, jangan menyusun ulang dari kode.
Skill ini cuma peta: ke mana melihat, apa yang tidak boleh, dan fakta yang paling
sering ditanya ulang.

## Yang paling sering bikin salah paham

**Nama app di bench adalah `erpnext`, bukan `autoerp`.** Ini fork ERPNext, jadi
bench memasangnya sebagai `apps/erpnext`. Modul sawitnya di
`apps/erpnext/erpnext/palm_mill/`. Di bench, remote fork kita bernama `upstream`;
remote ERPNext asli bernama `erpnext`.

**Repo ini bukan bench.** Bench hidup di luar working tree (`~/autoerp-bench` atau
`~/frappe-bench`). `Makefile` menggerakkan bench itu, bukan `.`.

**Dasar fork `version-16`** sejak 2026-09-16. `develop` sudah tidak dipakai.

## Ke mana melihat

| Pertanyaan | Baca |
|---|---|
| AutoERP itu apa, buat siapa | `docs/overview.md` |
| Pasang dari nol (bench + site + seed) | `docs/installation.md`; versi panjangnya di workspace: `../docs/onboarding/4-instalasi-autoerp.md` |
| Perintah harian, `make up/stop/status` | `docs/operations.md`, dan komentar di `Makefile` |
| 11 DocType, field, relasi | `docs/data-model.md` |
| Tiket timbang sampai jadi Purchase Receipt / Stock Entry | `docs/ticket-flow.md` |
| Endpoint yang dipanggil AutoGrade | `docs/autograde-api.md` |
| Kontrak penuh AutoGrade ↔ AutoERP (rancangan Mas Samuel) | `docs/autograde-integration.md` |
| Cara berkontribusi, alur PR | `docs/contributing.md` |
| Gejala aneh → sebabnya | `docs/gotchas.md` |
| Setup dev yang lebih dalam | `docs/dev-setup.md` |

## Angka yang benar (diverifikasi 2026-09-17)

| | |
|---|---|
| DocType palm_mill | **11** (`erpnext/palm_mill/doctype/`) |
| Patch palm_mill | **11** (`erpnext/patches/v17_0/palm_mill_*` + `setup_palm_mill.py`) |
| Fungsi test | **48** dalam 12 berkas |
| `@frappe.whitelist` di palm_mill | **6** total, **3** di `api.py` |

Kalau menyebut angka ini di jawaban, hitung ulang — jangan percaya daftar ini
kalau kodenya sudah berubah.

## Yang tidak boleh

- **Jangan `bench migrate` di checkout yang tidak punya `erpnext/palm_mill`.**
  Frappe menghapus DocType yang tidak bisa dia impor, **beserta tabelnya**, tanpa
  pesan. Ini juga yang menghapus Workspace publik tanpa berkas app.
- **Jangan `bench start` dua kali.** Yang kedua gagal merebut port redis, satu
  anak mati, lalu honcho mematikan seluruh grupnya — terbaca seperti crash
  padahal bench pertama masih melayani. `make up` menolak ini; `bench start`
  langsung tidak.
- **Jangan `create_integration_user` ulang** untuk melihat kunci AutoGrade — itu
  merotasi secret dan mematikan kunci lama. Pakai `make key-show`.
- **Jangan `bench set-config -g default_site`.** Frappe lalu mengabaikan Host
  header, semua `*.localhost:8000` dilayani site default, dan kunci site lain
  jadi 401 tanpa pesan.
- **Jangan `docker compose down -v`** pada ERP lokal mesin Linux lama — volume
  `autoerp_db-data` berisi data bos dan dumpnya sudah tidak ada di disk.

## Jawaban cepat

- **Nyalakan bench:** `make up` (latar belakang, menunggu site menjawab) atau
  `make start` (di depan, log di layar). Kalau bench-mu bukan bawaan, tulis sekali
  di `Makefile.local` (`BENCH = ...`, `SITE = ...`) — sesudah itu `make up` polos
  cukup. `make status` memberi tahu bench mana yang benar-benar dilayani.
- **Site baru lahir tanpa patch.** `install_app()` menandai semua patch selesai
  tanpa menjalankannya, jadi site baru berbahasa Inggris, 3 desimal, dan **tidak
  bisa menerima TBS** (gagal 417). Tiga perintah penawarnya ada di
  `../docs/onboarding/4-instalasi-autoerp.md` §6. Ini utang **E5** di
  `../docs/TODO-AUTOGRADE-AUTOERP.md`.
- **Tes:** `bench --site <site> run-tests --app erpnext --module <modul>`.
  ⚠️ `--test` bisa exit 0 padahal nol test jalan — periksa jumlah yang dilaporkan.
- **Sesudah mengubah `.po`:** `bench build` (atau `compile-po-to-mo --app erpnext
  --force`) lalu `clear-cache`. `bench migrate` **tidak** mengompilasi terjemahan.
- **Alur kerja repo:** branch baru dari `staging` → PR ke `staging`. Rilis
  `staging` → `main` dengan **merge commit**, jangan squash. Judul dan body PR
  wajib Bahasa Inggris; commit dan docs boleh Indonesia.

## Ikuti rancangan Mas Samuel

Kontraknya `docs/autograde-integration.md`; AutoGrade tinggal menyambung.
Cocokkan field DocType, endpoint, dan aturan turunan dengan kode `palm_mill`
**sebelum** menulis kode integrasi. Kalau dokumen dan kode bertentangan, **ikuti
kode**, lalu catat bedanya.

Butiran kiriman — jangan dibalik: **per janjang** tetap di edge (bukti), **rekap
per truk** masuk ERP lewat `upsert_visit` (angka pembukuan). ERP itu buku besar,
bukan event store.
