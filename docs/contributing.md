# Kontribusi

## Alur branch

```
branch baru  →  PR ke staging  →  PR rilis staging → main
```

- Kerjaan harian masuk lewat **PR ke `staging`**, tidak pernah langsung ke `main`.
- PR rilis `staging` → `main` pakai **merge commit**, bukan squash.
- **Judul dan body PR wajib bahasa Inggris.** Isi commit dan dokumen boleh
  bahasa Indonesia.
- Commit pakai format conventional: `feat(palm_mill):`, `fix(palm_mill):`,
  `test(palm_mill):`, `docs:`, `chore:`.

Karena alur rilis pakai merge commit, `main` selalu punya merge commit yang
tidak ada di `staging`. Itu normal, bukan divergensi. Cara cek yang benar:

```bash
git merge-base --is-ancestor origin/staging origin/main   # semua isi staging sudah rilis?
git diff --stat origin/staging origin/main                # kosong = nol beda isi
```

Jangan percaya `git cherry` / patch-id — squash membuat patch-id berbeda walau
isinya identik.

## Gaya kode

Ikut ERPNext upstream, jangan diubah:

- **Indentasi tab** untuk Python, JavaScript, CSS
- Panjang baris **110**
- Python: Ruff (kutip ganda, indentasi tab)
- JavaScript: Prettier 2.7.1
- JSON: indentasi spasi, size 1, tanpa newline akhir

```bash
ruff check erpnext/palm_mill && ruff format erpnext/palm_mill
pre-commit run --all-files
```

## Struktur DocType

```
palm_mill/doctype/nama_doctype/
├── nama_doctype.json     # skema — sumber kebenaran tabel
├── nama_doctype.py       # controller server
├── nama_doctype.js       # perilaku form (opsional)
└── test_nama_doctype.py  # test
```

JSON-nya yang membuat tabel lewat `bench migrate`, bukan sebaliknya.

Blok `# begin: auto-generated types` … `# end:` di controller dihasilkan
otomatis — jangan disunting tangan.

## Test

Butuh site khusus. **Jangan pernah di site berisi data sungguhan** — setup test
ERPNext menghapus transaksi.

```bash
bench new-site test_site --admin-password admin
bench --site test_site install-app erpnext

bench --site test_site run-tests --module erpnext.palm_mill.test_api
bench --site test_site run-tests --module erpnext.palm_mill.test_qr_card
bench --site test_site run-tests --module erpnext.palm_mill.doctype.weighbridge_ticket.test_weighbridge_ticket
bench --site test_site run-tests --module erpnext.palm_mill.doctype.autograde_operator.test_autograde_operator
bench --site test_site run-tests --module erpnext.palm_mill.doctype.truck.test_truck
```

48 test di modul ini:

| Berkas | Jumlah | Menjaga apa |
|---|---|---|
| `test_api.py` | 11 | kunjungan tiga kiriman, kiriman ulang setelah final, adopsi tiket ketikan tangan, jendela pencocokan, wajib punya peran integrasi |
| `test_qr_card.py` | 6 | isi QR, plat menyimpang, **regex kembar dengan AutoGrade** |
| `doctype/weighbridge_ticket/` | 8 | status, rumus potongan, batas + sampah, Purchase Receipt, Internal → Stock Entry, finalisasi timeout, cancel mengosongkan tautan |
| `doctype/autograde_operator/` | 18 | hashing, penghapusan sandi mentah, normalisasi email, izin peran |
| `doctype/truck/` | 5 | plat unik, plat aneh diperingatkan tapi tetap tersimpan |

`test_fixtures.py` menyediakan fixture bersama dan **mengunci contoh hitungan**:
neto 9.160 kg → potongan 11,55% → 8.102 kg dibayar.

Berkas `test_*.py` di master kebun (blok, divisi, kebun, sertifikasi,
sumber_tbs, palm_mill_settings) masih kerangka kosong tanpa test.

⚠️ `bench run-tests` pernah mentok di mesin MacBook ini (`Payment Gateway`),
dan `--test` bisa keluar dengan kode 0 padahal nol test jalan. Periksa
keluarannya, jangan cuma exit code.

## Patch

Perubahan yang butuh menyentuh data site yang sudah ada masuk sebagai patch:

1. Tulis di `erpnext/patches/v17_0/nama_patch.py` dengan fungsi `execute()`
2. Daftarkan di `erpnext/patches.txt`
3. Idempoten — patch bisa jalan ulang

Sekarang ada 19 patch `palm_mill_*`.

⚠️ Site **baru** tidak menjalankan patch sama sekali (`install_app` menandainya
selesai). Kalau perubahanmu juga harus berlaku di site baru, taruh di
`setup.py` `after_install()` **dan** di patch.

## CI

PR memicu: linter pre-commit (Ruff + Prettier + ESLint), Semgrep, dan 4 kontainer
test paralel di MariaDB.

`triage` merah di **setiap** PR fork ini — utang lama dari upstream, bukan
salah kodemu dan bukan penghalang.

Dua kegagalan CI lama sudah **diperbaiki**, jadi kalau ketemu lagi itu regresi,
bukan hal yang sudah diketahui:

- **Patch Test** dulu selalu merah karena `patch.yml` mem-`fetch` `$GITHUB_BASE_REF`
  dari `frappe/frappe`, yang tidak punya `staging`/`main`. Sekarang dipetakan ke
  `version-16` (`.github/workflows/patch.yml:155`).
- `install.sh` dulu memasang `payments --branch develop`. Sekarang `version-16`
  (`.github/helper/install.sh:362`), dikunci `test_ci_config.py`.

## Menambah string yang dilihat pengguna

Tulis **bahasa Inggris di kode**, lalu:

```bash
bench generate-pot-file --app erpnext
bench update-po-files --app erpnext --locale id     # dan --locale en
# isi msgstr di erpnext/locale/id.po
bench compile-po-to-mo --app erpnext --force
bench --site <site> migrate && bench --site <site> clear-cache
```

Jangan menambah msgid dengan tangan. Nilai yang **tersimpan** di database itu
data — terjemahkan tampilannya, jangan pernah ganti namanya.

String yang dimiliki **Frappe** (bukan ERPNext) tidak bisa ditimpa dari katalog
ERPNext; itu masuk `erpnext/fixtures/translation.json`.

## Sebelum kirim PR

```bash
ruff check erpnext/palm_mill && ruff format erpnext/palm_mill
pre-commit run --all-files
bench --site test_site run-tests --module erpnext.palm_mill.test_api
git status                    # pastikan JSON tidak ikut ter-export tanpa sengaja
```

Yang terakhir penting: `developer_mode` menulis balik ke repo saat kamu
mengedit DocType atau sidebar lewat UI.
