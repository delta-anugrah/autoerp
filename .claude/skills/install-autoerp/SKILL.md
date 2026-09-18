---
name: install-autoerp
description: Pasang AutoERP (fork ERPNext version-16, modul palm_mill) dari clone sampai satu kunjungan truk jadi Purchase Receipt — bench lokal MacBook, site kosong, atau nanti droplet. Pakai kalau user bilang "install AutoERP dari 0", "setup bench baru", "bikin site baru", "clone autoerp", "kenapa TBS gagal 417", "site-nya bahasa Inggris", atau lagi debug instalasi AutoERP yang macet.
---

# Pasang AutoERP dari nol

Manual langkah-demi-langkah buat manusia: `docs/onboarding/4-instalasi-autoerp.md`
⚠️ Dua rujukan di bawah ada di repo **`sawit`** (workspace internal), bukan di repo ini:
`docs/runbooks/2026-09-16-pindah-autoerp-ke-version-16.md` (cerita lengkap + cara mundur)
dan `docs/runbooks/2026-09-16-pindah-v16/` (skrip seed, wizard-args, uji kunjungan).
Kalau tidak punya aksesnya, skill ini tetap cukup untuk memasang dari nol — yang di sana
hanya latar belakang dan skrip pembantu.

Skill ini isinya yang **nggak** ada di manual: cara mandu sesinya, gerbang yang
nggak boleh dilewat, dan jebakan yang bikin instalasi kelihatan sukses padahal
gagal.

## Mode kerja

Guided. User yang ngetik di terminalnya, paste output, kamu baca. **Satu blok
perintah, tunggu hasil, baru lanjut.** Tiap step di manual punya baris **Cek** —
kalau cek-nya beda dari yang ditulis, berhenti di situ. Jangan lanjut ke step
berikutnya "sambil lihat nanti": step 6–8 di atas site yang salah cuma bikin
diagnosisnya kabur.

Kamu boleh menjalankan `bench --site … execute …` dan `git` sendiri kalau user
minta — itu read-only atau idempotent. Yang **tidak** boleh kamu jalankan sendiri:
`bench new-site` di site yang sudah ada, `drop-site`, `down -v`, `bench migrate` di
checkout yang tidak punya `erpnext/palm_mill` (Frappe **menghapus DocType beserta
tabelnya**, senyap).

## Fakta yang harus kamu pegang

- Dasar fork: **`version-16`** sejak 2026-09-16 (autoerp #8/#9). `develop` sudah
  tidak dipakai. Pin `frappe >=16.21.0,<17.0.0`, Python **3.14**, Node **≥24**.
- Nama app di bench adalah **`erpnext`**, bukan `autoerp`. Modul sawit ada di
  `apps/erpnext/erpnext/palm_mill/`. Remote di bench bernama **`upstream`**
  (= fork kita), remote ERPNext asli bernama `erpnext`.
- Repo privat → clone wajib **SSH** (`git@github.com:delta-anugrah/autoerp.git`),
  https gagal.
- Alur kerja: branch baru **dari `staging`** → PR ke `staging` → rilis `staging` →
  `main` dengan merge commit.
- Site produksi `app.smagri.id` akan lahir **kosong** — jadi jalur "site kosong"
  di manual adalah jalur produksi, bukan sekadar latihan.

## Sebelum mulai: cek ini dulu

Tanyain di awal, karena kalau salah satu tidak ada, instalasi mati di tengah:

- `python3.14`, `node ≥24`, `mariadb ≥11`, `redis`, `bench ≥5.31`, **`uv` dan
  `pkgconf`** (`brew install uv pkgconf` — tanpa ini `bench init` mati separuh
  jalan dan tidak rollback)
- Akses SSH ke `delta-anugrah/autoerp`
- MariaDB: `innodb_snapshot_isolation = OFF` di `[mysqld]`, dan grant `PUBLIC`
  pada `test\_%` **sudah dicabut** (lihat jebakan #3)
- Bench lain di mesin yang sama sudah **`make stop`** — dua bench rebutan port 8000

⚠️ `make stop` bench lama **ikut mematikan Redis**. Bench baru butuh Redis hidup saat
`new-site` (step 3) tapi harus mati lagi saat `bench start` (step 4). Lihat jebakan #9.

## Gerbang keras — berhenti kalau gagal

| Setelah | Cek | Kalau beda |
|---|---|---|
| `bench init` | `grep __version__ apps/frappe/frappe/__init__.py` → `16.x` | bukan v16 = branch salah, ulang dengan `--frappe-branch version-16` |
| `bench init` | `grep "bench serve" Procfile` → `--port 8000` | 8001 = ada bench tetangga; betulkan port (manual §1) |
| `bench get-app` | `ls apps/erpnext/erpnext/palm_mill/doctype \| wc -l` → `12` | 0 = branch salah / clone `main` lama; **jangan `migrate` apa pun** |
| sebelum `bench new-site` | `redis-cli -p 13000 ping` + `-p 11000 ping` → dua `PONG` | tanpa Redis, `after_install` mati `Error 61`; 3 menit terbuang |
| `bench new-site … --install-app erpnext` | `frappe.db.count Sumber TBS` → `2` | 0 = `after_install` tidak jalan, ulang new-site |
| `bench start` | proses tetap hidup, tidak ada `stopped (rc=1)` | Redis manual masih pegang port → matikan dulu (jebakan #9) |
| `bench new-site … --install-app erpnext` | `frappe.db.get_single_value System Settings language` → `id`; `Stock Settings enable_serial_and_batch_no_for_item` → `1` | bukan itu = `after_install` tidak jalan penuh, ulang new-site; **tidak ada lagi patch manual** sejak autoerp #17 |
| `e2e_visit.py` | tiket `Finalised` + Purchase Receipt | 417 "Activate Serial and Batch" = kebijakan situs tidak terpasang, cek baris di atas; 417 "Perusahaan … tidak dikenal" = nama company beda, pakai `ERP_COMPANY=` |
| setup wizard | mata uang company → `IDR` | `INR` = bawaan wizard; **ulangi wizard**, jangan perbaiki belakangan (jebakan #15) |
| sesudah wizard | `get_all_roles()` → **7** nama | 49 = `hide_unused_roles` tidak jalan; site lahir sebelum fitur ini, jalankan patch `palm_mill_role_visibility` |
| sebelum serah terima | admin pelanggan sudah bisa masuk | belum = site diserahkan dengan `Administrator` bersama (bagian "Serah terima") |

## Jebakan yang bikin gagal diam-diam

1. **Site kosong tidak menjalankan patch** — tapi kebijakan situs **sudah tidak**
   terpengaruh. `install_app()` tetap menandai semua patch selesai tanpa
   mengeksekusinya; sejak autoerp #17 bahasa `id`, presisi 2 desimal, dan Stock
   Settings `enable_serial_and_batch_no_for_item` ikut `after_install`, jadi
   **jangan jalankan patch itu tangan lagi** — cukup verifikasi lewat tabel di atas.
   ⚠️ Pembersihan gudang/Item Group seed berjalan dari hook `setup_wizard_complete`,
   **sesudah wizard**, karena gudangnya baru dibuat oleh wizard itu sendiri. Kalau
   site dipakai tanpa menjalankan wizard, gudang seed memang masih terlihat.
2. **`bench set-config -g default_site`** → Frappe mengabaikan Host header, semua
   `*.localhost:8000` dilayani site default, kunci site lain jadi 401 tanpa pesan.
   Jangan pernah set; `bench use` sudah cukup untuk CLI.
3. **Grant `PUBLIC` bawaan MariaDB pada `test\_%`** → user site lain ikut melihat
   kolom `test_*.tabDocType`, dan `new-site` mati dengan
   `Unknown column 'protect_attached_files' in 'INSERT INTO'`. Obat:
   `REVOKE ALL PRIVILEGES ON \`test\_%\`.* FROM PUBLIC;`. Di MacBook Abel sudah
   dicabut; di mesin baru belum.
4. **`bench init` di sebelah bench lain memilih port 8001/9001/13001/11001.**
   Betulkan satu `set-config` per baris — **jangan dari loop zsh**, zsh tidak
   memecah `"key value"` jadi dua argumen dan menulis key sampah ke config.
5. **Tidak ada password root MariaDB** yang perlu disimpan: user macOS adalah
   superuser lewat socket. `--db-root-username "$USER" --db-socket /tmp/mysql.sock`,
   prompt password tekan Enter. Jangan pernah taruh `root_password` di
   `common_site_config.json`.
6. **`bench execute frappe.db.set_single_value`** kwarg-nya `fieldname`, bukan
   `field`. Salah nama = diam-diam tidak ke-set kalau stderr dibuang.
7. **`bench migrate` tidak mengompilasi terjemahan.** Sesudah menyentuh `.po`:
   `bench build` (atau `compile-po-to-mo --app erpnext --force`) + `clear-cache`.
8. **Redis: hidup saat `new-site`, mati saat `bench start`.** Dua kegagalan berbeda dari
   satu sumber. (a) `new-site` tanpa Redis → `after_install` ERPNext memanggil
   `frappe.enqueue` lewat `set_single_defaults` → `Error 61 connecting to
   127.0.0.1:11000`, install mati setelah semua DocType terpasang. (b) `bench start`
   dengan Redis manual masih hidup → `Address already in use` → honcho mematikan
   **seluruh grupnya** (`stopped (rc=1)` lalu SIGTERM ke web/worker/socketio). Gejala (b)
   terbaca seperti bench rusak; sebenarnya cuma rebutan port. Urutannya:
   `redis-server config/redis_*.conf --daemonize yes` → `new-site` →
   `redis-cli -p 13000 shutdown nosave; redis-cli -p 11000 shutdown nosave` → `bench start`.

9. **Rollback `new-site` bisa deadlock.** Jawab `y` pada "do you want to rollback the
   site?" dan rollback menggantung tanpa batas: proses `new-site` masih memegang koneksi
   `Sleep` ke DB yang hendak di-`DROP`, dan `DROP DATABASE` menunggu metadata lock yang
   tidak akan pernah lepas. Dari terminal lain: `SHOW PROCESSLIST`, `KILL <id koneksi
   Sleep>`, tunggu DROP selesai, pastikan `SHOW DATABASES LIKE 'autoerp'` kosong sebelum
   mengulang. **Jangan** Ctrl-C lalu langsung `new-site` lagi — DB sisa bikin gagal.

10. **`file_watcher_port` 6787 milik `~/frappe-bench`.** Bench kedua harus 6789.

11. **`e2e_visit.py` menyandera nama perusahaan.** Default `COMPANY = "PT Sawit Rambang
    Lestari"` (baris 20, override lewat env `ERP_COMPANY`). Manual dulu menulis nama itu
    sebagai contoh "mis." di wizard, jadi orang mengisi nama lain lalu kena 417
    **"Perusahaan … tidak dikenal"** pada cek visit — 4 cek pertama lolos duluan, jadi
    kelihatan seperti kegagalan di tengah alur. Tanyakan nama perusahaan yang dipakai di
    wizard **sebelum** menjalankan e2e, lalu sertakan `ERP_COMPANY="<nama itu>"`. Jangan
    suruh user bikin ulang site.

12. **Kunci AutoGrade tidak boleh membaca `Scheduled Job Type`** — dan itu benar.
    `e2e_visit.py` dulu mengecek pendaftaran `finalize_due_tickets` lewat
    `frappe.client.get_list` memakai kunci integrasi; Frappe menolak dengan
    `PermissionError`, skrip menelannya jadi list kosong, lalu melapor **"job tidak
    terdaftar"** padahal job-nya ada dan aktif. Diperbaiki 2026-09-17: cek HTTP sekarang
    menegaskan penolakannya, pendaftarannya diperiksa dari bench. Kalau ketemu laporan
    lama soal ini, jangan kejar scheduler-nya — periksa dulu dari bench.

13. **`e2e_visit.py` dulu tidak boleh dijalankan dua kali di site yang sama.** Cek
    "exactly one ticket for B 7154 QY" menghitung tiket **per plat**, padahal truk yang
    sama memang boleh datang lagi — run kedua selalu FAIL dan terbaca seperti tiket
    dobel. Diperbaiki 2026-09-17: hitungannya sekarang per `autograde_visit_id` run itu.
    Kalau melihat laporan "2 tickets", periksa dulu `creation`-nya: dua waktu berbeda =
    dua kunjungan, bukan cacat.

14. **Sesi Claude lain di bench yang sama.** Kalau `git status` di `apps/erpnext`
   kotor padahal kamu tidak mengedit, itu sesi lain — jangan `checkout --`,
   simpan diff-nya dulu, tanya user.

15. **Mata uang wizard bawaannya INR, bukan IDR.** Kalau terlewat, setiap angka
   rupiah dibaca sebagai rupee dan tiap transaksi meleset ~184× — tanpa satu pun
   peringatan. Memperbaikinya sesudah ada transaksi jauh lebih mahal daripada
   mengisinya benar sekali. `wizard-args.json` sudah menulis `"currency": "IDR"`;
   yang berisiko adalah wizard yang diisi manual lewat browser.

16. **Jangan pakai kolom `Disabled` pada Role untuk menyembunyikan role.** Frappe
   menghapus role itu dari **semua** user saat di-disable (`Role.remove_roles`), dan
   meng-enable kembali **tidak** memulihkan satu pun. Terukur di site nyata:
   `Sales User` 51 pemegang → 0 → tetap 0. Yang dipakai AutoERP adalah
   `restrict_to_domain`, yang tidak menyentuh `Has Role` sama sekali. Penjaga di
   `hide_unused_roles` tidak menjangkau penyuntingan manual dari Desk.

## Dua jalur site

| | Site kosong | Site demo (dump) |
|---|---|---|
| Untuk | latihan **dan** produksi | lihat Desk penuh data (3.848 tiket, OER) |
| Data | seed minimum `seed_v16_site.py` | `gh release download sawit-data-2026-09-09` lalu `restore` + `migrate` |
| Patch `palm_mill_*` | **tidak** jalan, tapi kebijakan situs sudah lewat `after_install` (#17) | jalan saat `migrate` |
| Catatan | — | dump skema develop; `migrate` ke v16 terbukti jalan 2026-09-16 |

## Serah terima: admin pelanggan dan role yang terlihat

Site yang diserahkan hanya dengan `Administrator` adalah site yang setiap
perubahannya bertanda tangan akun bersama — activity log tidak bisa menyebut siapa
mengerjakan apa. Jadi ini bukan langkah opsional.

```bash
cd autoerp && make admin-new EMAIL=admin@pelanggan.co.id NAMA="Admin Pelanggan"
```

Yang tercetak **tautan reset, bukan kata sandi**. Kirim tautannya; biarkan mereka yang
memilih sandinya. Perintahnya idempoten: dijalankan ulang hanya menerbitkan tautan baru
(`roles_added` kosong).

Sesudah admin pelanggan bisa masuk dan membuat satu user sendiri, **kunci
`Administrator`**: User → Administrator → nonaktifkan, atau setel ulang sandinya ke
nilai yang disimpan di tempat rahasia dan tidak dipakai sehari-hari.

**Role yang ditawarkan form User: 7, bukan 49.**

`System Manager` · `Weighbridge Operator` · `Palm Mill Integration` ·
`Purchase User` · `Stock User` · `Script Manager` · `Workspace Manager`

Dua nama terakhir ada di daftar bukan karena pabrik memakainya, melainkan karena Frappe
menyebut keduanya di kodenya sendiri — `Script Manager` menjaga Server Script dan Report,
`Workspace Manager` menjaga penyuntingan workspace publik termasuk workspace mill.

Sisanya **tidak dimatikan**, hanya disembunyikan lewat `restrict_to_domain` ke domain
`Palm Mill Advanced` yang tidak pernah diaktifkan. Semuanya tetap hidup penuh, dan
`frappe.get_roles` tidak pernah membaca kolom itu.

Memunculkan kembali — dua cara, keduanya dari `Administrator`:

- satuan: buka Role → kosongkan `Restrict To Domain` → Save
- semuanya: Domain Settings → aktifkan `Palm Mill Advanced`

⚠️ Jangan pakai kolom `Disabled` untuk ini — lihat jebakan #16.

**Akun `support` AutoGrade hanya bisa dibuat `Administrator`.** Role itu membuka lima
layar diagnostik di konsol dan diperuntukkan bagi yang merawat perangkat lunak pabrik,
bukan pelanggan. Akun `support` yang sudah ada tetap bisa disunting siapa pun yang boleh
menulis DocType-nya, supaya backoffice bisa memperbaiki nama atau menonaktifkannya.

## Bukti selesai

Bukan "site kebuka". Selesai = `e2e_visit.py` melaporkan tiket `Finalised` dengan
Purchase Receipt (External) **dan** Stock Entry (Internal), lalu di Desk →
Tiket Timbang keduanya terlihat. Kalau user cuma sampai login, tulis jelas mana
yang belum dibuktikan.

Untuk site yang **diserahkan ke pelanggan**, tambah dua hal lagi: admin pelanggan
sudah bisa masuk dan membuat satu user sendiri, dan `Administrator` sudah dikunci.
