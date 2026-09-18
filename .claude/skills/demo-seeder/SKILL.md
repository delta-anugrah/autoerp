---
name: demo-seeder
description: Use when seeding or resetting demo data for a showcase — "bikin demo buat klien", "isi data dummy", "reset demo", "seed site", "demo_mode", or when changing erpnext/palm_mill/demo.py. Also use before showing AutoERP and AutoGrade side by side, because the plate numbers must stay twinned across both repos.
---

# Seeder demo — dua sisi, plat wajib kembar

Demo ke klien memakai **dua seeder yang harus cocok**: AutoERP mengisi ERP Desk,
AutoGrade mengisi konsol operator. Platnya sama persis, jadi satu truk di layar
kiri adalah truk yang sama di layar kanan. Itu seluruh gunanya.

| Sisi | Perintah | Berkas |
|---|---|---|
| AutoERP | `bench --site <site> execute erpnext.palm_mill.demo.seed` | `erpnext/palm_mill/demo.py` |
| AutoGrade | `cd autograde && make demo` | `scripts/seed-console-demo.py` |

⚠️ **Mengubah plat di satu sisi berarti mengubahnya di sisi lain, dalam PR yang
sama.** Kalau tidak, truk di ERP tidak punya pasangan di konsol dan demonya
justru memperlihatkan sistem yang tidak nyambung.

## Menjalankan

```bash
bench --site <site> set-config demo_mode 1
bench --site <site> execute erpnext.palm_mill.demo.seed
```

Mengulang bersih: `erpnext.palm_mill.demo.reset`. Sisi AutoGrade: `make demo`
(`HARI=7` bawaan, `make demo AKSI=reset` untuk mengulang bersih; `PAKSA=1`
melewati penolakan database berisi — jangan dipakai kecuali yakin).

Akun — semuanya bersandi `sawit2026`:

| Layar | Akun |
|---|---|
| ERP Desk | `krani@` / `mandor@` / `manajer@demo.autoerp.test` |
| Konsol AutoGrade | `operator@` / `support@demo.autoerp.test` |

## Penjaga yang tidak boleh dilucuti

`seed()` memanggil `_check_allowed()`, yang **menolak jalan** kecuali site
bertanda `demo_mode`. Itu satu-satunya yang mencegah data karangan mendarat di
pembukuan sungguhan. `force=1` ada, tapi memakainya di site pabrik berarti
mencampur tiket palsu dengan tiket asli — dan tidak ada yang memisahkannya
kembali.

**Jangan pernah menjalankan seeder di PC pabrik.**

## Jebakan yang sudah memakan waktu

- **Mata uang.** Site `--install-app` lahir tanpa isi wizard, dan default
  currency-nya **INR**. Kalau tidak diperbaiki, tiap Purchase Receipt terkali
  ~184× tanpa peringatan apa pun. `set_defaults_currency()` di seeder menutup ini
  — jangan dihapus. Lihat `docs/gotchas.md` §19.
- **Idempoten.** Seeder harus bisa dijalankan dua kali tanpa menggandakan apa
  pun. Kalau menambah pembuatan dokumen, pakai pola "cek dulu, baru buat" seperti
  fungsi di sekitarnya.
- **Antrean.** `drain_queue()` ada karena dokumen yang dibuat massal menumpuk di
  antrean latar; tanpa itu angka di Desk belum lengkap saat demo dimulai.

## Kalau demo dipakai buat menunjukkan alur penuh

Alur kunjungan truk yang sungguhan diuji oleh
`../docs/runbooks/2026-09-16-pindah-v16/e2e_visit.py` di workspace sawit — dia
membuktikan satu kunjungan jadi Purchase Receipt (External) dan Stock Entry
(Internal). Jalankan itu, bukan seeder, kalau yang mau dibuktikan adalah
**kebenaran alurnya**; seeder cuma mengisi layar.
