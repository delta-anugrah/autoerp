---
name: erpnext-frappe
description: Referensi fitur & arsitektur ERPNext / Frappe Framework untuk workspace sawit. Use when the user asks about ERPNext, Frappe, DocType, bench, BOM co-product, whitelabel ERP, lisensi GPL ERPNext, lokalisasi Indonesia (e-Faktur/Coretax/PPN), atau lagi menimbang ERPNext sebagai ERP pabrik sawit / pengganti-pendamping Palmgrade.
---

# ERPNext / Frappe — Referensi Workspace Sawit

## Overview

ERPNext **bukan platform, tapi aplikasi**. Dia numpang di **Frappe Framework**
(repo terpisah). Semua yang terasa "framework" — ORM, permission, REST API,
background job, print engine, **dan mesin whitelabel** — punyanya Frappe, bukan
ERPNext. Salah alamat di sini bikin orang fork ERPNext padahal cukup bikin app
sendiri.

Aturan tunggal yang paling menghemat waktu: **jangan pernah fork ERPNext.**
Bikin app baru (`bench new-app`) yang duduk di atasnya dan override lewat
`hooks.py`. 400.000 baris Python dengan rilis mingguan bukan sesuatu yang bisa
kita rawat.

## Kondisi sekarang (2026-09-16) — baca ini dulu, sisanya referensi

- **AutoERP = fork ERPNext** `delta-anugrah/autoerp`, dasar **`version-16`** (pindah
  dari `develop` 2026-09-16, autoerp #8/#9). Modul sawit `erpnext/palm_mill/`.
  Saran "jangan fork" di bawah **sudah dibalik** oleh keputusan user 2026-09-13 —
  jangan ditawarkan ulang; harganya tercatat di PROGRESS §"Dasar fork".
- Checkout: `sawit/autoerp` (remote `origin`). Bench MacBook `~/frappe-bench`
  (`apps/erpnext`, remote **`upstream`** = fork kita; remote ERPNext asli `erpnext`).
- Pin `frappe >=16.21.0,<17.0.0`, Python 3.14, Node ≥24, MariaDB 12.
- Pasang dari nol / debug instalasi → skill **`install-autoerp`** +
  `docs/onboarding/4-instalasi-autoerp.md`.
- Sinkron upstream: `git fetch erpnext version-16 && git merge` lewat PR; `id.po`/`en.po`
  **jangan `--theirs`** (runbook 2026-09-16 §7).

## Versi: yang dipilih

| Branch | Status |
|---|---|
| `version-16` | ✅ **dipakai** — rilis stabil, dapat patch |
| `develop` (v17-dev) | ❌ ditinggalkan 2026-09-16: belum rilis, nol tag, tanpa patch keamanan |
| `version-15` | ❌ tidak ada Co-Product BOM |

## Konsep inti (yang beda dari framework lain)

| Istilah | Artinya |
|---|---|
| **DocType** | Model + tabel + form + permission, satu definisi JSON. Bukan cuma tabel. |
| **Child table** | DocType dengan `istable: 1`. Tidak punya halaman sendiri, selalu nempel di parent. 252 dari 534 DocType ERPNext adalah child. |
| **Single** | DocType `issingle: 1` — satu baris global, dipakai untuk Settings. Datanya di `tabSingles`, bukan tabel sendiri. |
| **Submittable** | `is_submittable: 1` → punya `docstatus`: **0 draft, 1 submitted, 2 cancelled**. Dokumen submitted tidak bisa diedit, cuma di-cancel lalu di-amend. Semua transaksi akuntansi & stok begini. |
| **Naming series** | Pola penomoran (`ACC-SINV-.YYYY.-`). Variabel yang tersedia: `FY, TFY, ABBR, MM, DD, YY, YYYY, JJJ, WW`. |
| **bench** | CLI + direktori kerja. Satu bench = banyak app + banyak site. |
| **site** | Satu database + satu set config. Multi-tenant terjadi di level site. |
| **Workspace** | Halaman navigasi modul di UI. 15 buah di ERPNext. |

## Isi ERPNext (angka terverifikasi dari repo)

- **21 modul**, **534 DocType** (282 master + 252 child), **184 laporan**,
  **77 print format**, **15 workspace**
- ~400.000 baris Python, ~82.000 baris JavaScript
- Daftar lengkap per modul: [references/inventory.md](references/inventory.md)

Modul terbesar: Accounts (92 master), Stock (45), Setup (28), Manufacturing (19),
CRM (15), Selling (12), Buying (10), Projects (10), Quality Management (8).

**Yang TIDAK ada di repo ini:**

| Hilang | Di mana |
|---|---|
| HR & Payroll | App terpisah `frappe/hrms` |
| Agriculture | Dicabut dari core sejak v14, app terpisah, praktis tidak dirawat |
| Healthcare, Non Profit, Hospitality, Shopify, Exotel | Semua dipisah jadi app sendiri di v13–v15 |
| Lokalisasi Indonesia | Lihat bagian di bawah — praktis nol |

## Fit untuk pabrik sawit (PKS)

### Yang sudah ada dan pas

**Co-Product costing — ini temuan utamanya.** Tabel `BOM Secondary Item`
(child dari BOM) punya:

- `secondary_item_type` — `Co-Product` / `By-Product` / `Scrap` /
  `Additional Finished Good`
  (⚠️ di **v16** nama fieldnya masih `type`; berubah jadi `secondary_item_type`
  di develop/v17)
- `cost_allocation_per` — persen biaya dibebankan ke tiap output
- `process_loss_per` / `process_loss_qty` — susut proses per item

`bom.py::validate_total_cost_allocation` memaksa **total alokasi BOM + semua
secondary item = 100%**. Itu model joint-cost allocation. Pemetaannya:

```
BOM: TBS (1000 kg)
  → CPO           co-product,  cost_allocation_per ≈ 82
  → Palm Kernel   co-product,  cost_allocation_per ≈ 18
  → Cangkang/Fiber by-product, cost_allocation_per = 0
  → process_loss_percentage untuk susut
```

Harga pokok CPO dan kernel keluar dari GL, bukan spreadsheet.

**Quality Inspection sebagai jembatan grading.** DocType `Quality Inspection`
punya child `Quality Inspection Reading` dengan sampai 10 pembacaan per
parameter, `min_value`/`max_value`, dan `formula_based_criteria` +
`acceptance_formula` (field Code). Artinya kriteria terima/tolak bisa berupa
ekspresi, bukan cuma rentang. Parameter Palmgrade (matang, mentah, lewat matang,
tandan kosong, brondolan, pasir) memetakan langsung ke Readings, dan rumus
potongan bisa ditulis sebagai acceptance formula. Sudah bisa ditaut ke Purchase
Receipt lewat `reference_type` / `reference_name`.

**Stock Entry purposes** yang relevan: `Manufacture`, `Repack`,
`Material Transfer for Manufacture`, `Material Consumption for Manufacture`,
`Disassemble`.

### Yang harus dibangun sendiri

Tidak ada di ERPNext, semuanya jadi DocType di app kita:

- **Jembatan timbang** — tiket bruto/tara/netto, integrasi indikator timbangan
- **Sortasi & potongan TBS** saat penerimaan
- **Kontrak plasma/inti** dan skema bagi hasil
- **OER / KER harian**
- **Traceability ISPO/RSPO** sampai level blok kebun

### Batas peran

ERPNext = lapisan komersial + akuntansi di cloud. Palmgrade = lapisan pabrik
on-prem. Sambungannya REST API, bukan integrasi database. Lihat bagian lisensi
di bawah — pembagian ini juga yang paling aman secara GPL.

## Lisensi: GPLv3, dan kenapa ini menentukan model bisnis

ERPNext berlisensi **GNU GPL v3** — copyleft, **bukan AGPL**. Bedanya menentukan:

| Cara kirim | Distribusi? | Wajib buka source? |
|---|---|---|
| SaaS di cloud kita (klien akses browser) | Tidak | **Tidak** — hosting tidak memicu GPLv3 |
| Dipasang di PC pabrik klien / on-prem | Ya | **Ya** — klien berhak minta source turunan kita |
| Image Docker dikirim ke klien | Ya | **Ya** — image adalah bentuk distribusi |

⚠️ **Ini menabrak model Palmgrade sekarang.** Kita mengirim on-prem ke PC pabrik
dan mengunci dengan lisensi Ed25519. Kalau ERPNext ikut masuk paket on-prem yang
sama, setiap pabrik penerima berhak minta source turunan kita **dan** berhak
melepas license guard-nya. GPL tidak melarang kita memasang guard, tapi juga
tidak memberi kekuatan hukum untuk melarang mereka mencopotnya.

Jalan keluar lazim: **ERPNext cloud-only sebagai SaaS**, komponen on-prem tetap
Palmgrade (kode kita, lisensi kita), keduanya bicara lewat API.

*Ini pembacaan teknis atas teks lisensi, bukan nasihat hukum. Konfirmasi ke
penasihat hukum sebelum jadi komitmen komersial.*

**Merek dagang** (`TRADEMARK_POLICY.md`) — terpisah dari GPL dan sering ketuker.
Nama & logo "ERPNext" tidak boleh jadi bagian nama produk, layanan, perusahaan,
atau domain. Boleh menyebut untuk menjelaskan jasa ("konsultan ERPNext"). Untuk
kita ini bukan hambatan — kebijakan ini justru **mewajibkan** rebranding.

## Whitelabel: checklist konkret

Beban aslinya ringan. Cuma **48 baris** literal `"ERPNext"` di Python di luar
test helper, dan mayoritas pesan patch deprecation lama + komentar.

### Lapis 1 — setting database, nol kode

`Website Settings`: `app_name`, `app_logo`, `favicon`, `splash_image`,
`brand_html`, `banner_image`, `footer_logo`, `footer_powered`, `copyright`,
`website_theme`
`System Settings`: `app_name`
`Navbar Settings`: isi dropdown bantuan

Tersimpan per site → bisa beda per klien tanpa build ulang.

### Lapis 2 — app sendiri, override lewat `hooks.py`

```python
app_logo_url = "/assets/palmgrade_erp/images/logo.svg"
website_context = {
    "favicon": "/assets/palmgrade_erp/images/favicon.svg",
    "splash_image": "/assets/palmgrade_erp/images/logo.svg",
}
add_to_apps_screen = [{...}]
app_include_css = "palmgrade_erp.bundle.css"   # tema desk
email_brand_image = "assets/palmgrade_erp/images/logo.jpg"
after_install = "palmgrade_erp.install.after_install"   # timpa sisa branding
```

### Lapis 3 — sisa yang menempel di ERPNext

Timpa lewat `after_install` app kita, jangan diedit di tempat:

- `setup/install.py::add_standard_navbar_items` — menanam 4 item
  (Documentation, User Forum, Frappe School, Report an Issue)
- `setup/install.py::add_app_name` — set `app_name = "ERPNext"`
- `setup/install.py::default_mail_footer` — footer email menaut ke frappe.io
- `templates/includes/footer/footer_powered.html`
- 7 berkas gambar di `erpnext/public/images/` (`erpnext-logo.svg`,
  `erpnext-favicon.svg`, `erpnext-logo.png`, `erpnext-logo-blue.png`,
  `v16/erpnext.svg`, dll)

## Lokalisasi Indonesia: praktis nol

Halaman marketing menyebut PPN, PPh, e-Faktur, BPJS. Yang benar-benar ada **di
dalam kode** cuma dua berkas:

| Berkas | Isi |
|---|---|
| `accounts/.../chart_of_accounts/verified/id_chart_of_accounts.json` | COA: Aktiva, Passiva, Modal, Beban, Penjualan — dasar, tidak spesifik industri |
| `setup/setup_wizard/data/country_wise_tax.json` | PPN Keluaran 11% + PPN Masukan 11%, hardcoded (perlu dicek terhadap aturan berjalan) |

Tidak ada `regional/indonesia`. Modul `regional` cuma punya Australia, Italia,
Afrika Selatan, Turki, UAE, AS. Tidak ada e-Faktur, Coretax, PPh 21 TER, BPJS.

**Terjemahan `id.po`:**

| Repo | String | Diterjemahkan | Cakupan |
|---|---|---|---|
| frappe (framework) | 6.241 | 5.665 | 90% |
| erpnext (aplikasi) | 10.490 | 2.910 | **27%** |

Efek nyata: menu & dialog sistem sudah Indonesia, tapi istilah bisnis — nama
DocType, label field, judul laporan, pesan validasi — mayoritas masih Inggris.
Sekitar 7.580 string perlu digarap (Crowdin upstream, atau override lokal).

**Opsi pihak ketiga:** `agile-technica/erpnext-indonesia-localization` — Coretax
XML exporter + importer VAT Output dari DJP. Agile Technica satu-satunya partner
resmi Frappe tier bronze di Indonesia. **Audit dulu** sebelum jadi dependensi.

## Extending: hook yang dipakai

Semua di `hooks.py` app kita. Yang paling sering:

| Hook | Untuk |
|---|---|
| `doc_events` | Hook siklus hidup (`validate`, `on_submit`, `on_cancel`, …) per DocType |
| `extend_doctype_class` | Tambah method ke controller lewat mixin — **lebih aman** dari override |
| `override_doctype_class` | Ganti total kelas controller. Pakai kalau mixin tidak cukup |
| `override_whitelisted_methods` | Ganti endpoint API bawaan |
| `permission_query_conditions` / `has_permission` | Filter baris & cek akses per dokumen |
| `scheduler_events` | Cron (`hourly`, `daily`, `cron`) |
| `fixtures` | Ekspor Custom Field / Property Setter / master ikut app |
| `after_install`, `after_migrate` | Timpa hasil install ERPNext (termasuk branding) |
| `jinja` | Method & filter tambahan untuk print format |
| `boot_session`, `extend_bootinfo` | Sisipkan data ke sesi klien |

**REST API** (dari Frappe, bukan ERPNext):

```
GET|POST|PUT|DELETE  /api/resource/<DocType>[/<name>]
POST                 /api/method/<dotted.path.to.whitelisted_fn>
Authorization: token <api_key>:<api_secret>
```

Plus DocType `Webhook` untuk dorongan keluar. Cukup untuk integrasi
Palmgrade → ERPNext; **jangan** integrasi level database.

## Perintah bench yang sering dipakai

```bash
bench new-app palmgrade_erp                  # bikin app sendiri
bench get-app https://github.com/frappe/erpnext --branch version-16
bench new-site pks.localhost
bench --site pks.localhost install-app erpnext palmgrade_erp
bench --site pks.localhost migrate           # jalankan patch + sinkron schema
bench build --app palmgrade_erp              # rebuild aset
bench --site pks.localhost console           # REPL Python dengan frappe siap
bench --site pks.localhost mariadb           # shell DB
bench --site pks.localhost backup --with-files
bench start                                  # dev server
bench restart                                # produksi (supervisor)
```

## Kesalahan umum

| Kesalahan | Akibat | Yang benar |
|---|---|---|
| Fork ERPNext untuk whitelabel | Konflik merge tiap rilis | **Sudah diputuskan fork** (2026-09-13); sinkron bulanan lewat PR, jangan `git pull` langsung |
| Clone branch `development` | Working tree kosong, gagal senyap | Branch-nya `develop` |
| Bangun PKS di `version-15` | Tidak ada Co-Product, cuma Scrap Items | `version-16` |
| Edit DocType inti ERPNext langsung | Hilang saat `bench migrate` | Custom Field + Property Setter, ekspor lewat `fixtures` |
| Install v16 manual di atas OS lama | Python 3.14 tidak tersedia | `frappe_docker` resmi (deploy `app.smagri.id`) |
| Anggap ERPNext = AGPL | Salah menakar risiko SaaS | GPLv3 — hosting aman, distribusi tidak |
| Kirim ERPNext on-prem tanpa putusan lisensi | Klien berhak source + boleh copot license guard | Cloud-only, on-prem tetap Palmgrade |
| Cari HR/Payroll di repo ini | Tidak ketemu | App terpisah `frappe/hrms` |
| Pakai `Scrap` untuk kernel | Salah alokasi biaya | `Co-Product` + `cost_allocation_per` |

## Yang belum diuji

Belum ada instance yang dinaikkan. Dua hal ini menentukan kelayakan dan harus
dijawab sebelum komitmen:

1. Apakah alokasi biaya co-product benar-benar menghasilkan **jurnal yang bisa
   diaudit**, bukan cuma angka di layar.
2. Beban ERPNext saat **volume transaksi harian PKS** masuk penuh.

Uji dengan menaikkan satu instance v16 lewat `frappe_docker`, lalu jalankan satu
hari operasi PKS betulan: terima TBS dari tiga pemasok dengan potongan berbeda,
satu Work Order co-product, jual CPO, cek harga pokoknya.

## Sumber

Dibaca langsung dari `frappe/erpnext` @ `84a32c40f4f` (branch `develop`,
2026-08-25), berkas `version-16` & `version-15` dari GitHub raw, dan
`frappe/frappe` `version-16` untuk hook & Website Settings. Kajian lengkap:
halaman "ERPNext vs ERP Kita" (https://claude.ai/code/artifact/9597946d-cbe1-46a2-95b8-589c76e8c3f2),
yang juga memuat bandingan dengan ERP lama di `Projects/erp-next/`. (Artifact lama sudah mati, dicek
2026-08-25.)
