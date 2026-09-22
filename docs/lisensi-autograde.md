# Lisensi AutoGrade

Cara menerbitkan token langganan untuk sebuah pabrik, dan apa yang terjadi kalau
langganannya habis.

Dokumen ini untuk **kita**, bukan pelanggan. Token cuma bisa diterbitkan dari site
yang kita pegang.

---

## 1. Cara kerjanya, dalam satu gambar

Analoginya SIM. Yang bisa mencetak cuma polisi, karena cuma polisi yang punya cap.
Siapa pun bisa **memeriksa** SIM asli atau palsu tanpa punya cap itu.

```
AutoERP (app.smagri.id)          PC pabrik (offline)
┌───────────────────────┐        ┌────────────────────────┐
│ kunci PRIVAT          │        │ kunci PUBLIK           │
│ → menandatangani      │ token  │ → memeriksa saja       │
│                       │ ──────▶│                        │
│ Administrator saja    │ (copy) │ autograde.sh licence   │
└───────────────────────┘        └────────────────────────┘
```

Kunci privat cuma ada di `site_config.json` site kita. Pabrik cuma memegang kunci
publik, jadi bisa memeriksa tapi **tidak bisa mengarang izin sendiri** — dan itu
penting, karena operator pabrik ada di grup `docker`, yang setara root.

Verifikasi di pabrik **100% offline**, nol HTTP. PC pabrik tidak pernah menanyakan
apa pun ke server.

---

## 2. Menerbitkan token

1. Masuk ke <https://app.smagri.id> sebagai **Administrator**.
2. Buka **AutoGrade Licence** → **New**.
3. Isi:

   | Kolom | Isi |
   |---|---|
   | Company | ⚠️ **harus sama persis** dengan `ERP_COMPANY` di `.env` PC pabrik |
   | Active Until | tanggal terakhir langganan, misal 30 Juni 2027 |
   | Grace Days | 60 (bawaan) |
   | Warning Days | 30 (bawaan) |
   | Status | `ACTIVE` |

4. **Save**, lalu tombol **Issue Token**.
5. Tombol **Copy Install Command** menyalin baris yang siap ditempel:

   ```
   autograde.sh licence eyJhbGciOiJFZERTQSIs...
   ```

6. Lewat AnyDesk, tempel baris itu di terminal PC pabrik, Enter.

Skrip memeriksa tanda tangannya **sebelum** menulis apa pun, lalu memasang ulang
container. Memasang ulang wajib: `.env` baru cuma menempel saat container dibuat
ulang, dan **reboot saja tidak cukup** — container lama dipakai ulang lengkap
dengan env lamanya.

### Kenapa satu baris tidak bisa diterbitkan dua kali

Sekali token dicetak, syaratnya beku. Pabrik sedang memegang salinan
bertanda tangan dari syarat itu, dan tidak ada cara memberitahunya bahwa syaratnya
berubah. Mau memperpanjang? **Buat baris baru.** Baris lama tetap tersimpan sebagai
riwayat: pabrik mana dapat apa, kapan, oleh siapa.

---

## 3. Yang terjadi di pabrik

| Keadaan | Kamera | Layar konsol |
|---|---|---|
| Masih lama | grading normal | diam |
| 30 hari terakhir | grading normal | banner **kuning**: habis N hari lagi |
| Lewat tanggal, dalam 60 hari tenggang | **grading normal** | banner **oranye**: berhenti N hari lagi |
| Tenggang habis | **berhenti** | banner **merah**: grading dihentikan |

Saat tenggang habis, tiga hal terjadi sekaligus tanpa perintah siapa pun: worker
deteksi berhenti mengambil frame, heartbeat ke PLC mati, dan HTTP line menjawab
403. Karena tidak ada grading, coil ACC/REJ berhenti berdenyut dengan sendirinya,
jadi buah lewat tanpa disortir.

**Data tidak hilang.** SQLite, foto capture, dan antrean ke ERP tetap di disk.
Begitu token baru dipasang, grading lanjut dari tempat berhenti.

⚠️ **Fail closed.** Token yang tidak terbaca (rusak, salah copy, kunci publik tidak
cocok) diperlakukan **sama dengan habis**: kamera diam. Kebalikannya berarti token
rusak = gratis.

Kalau `LICENSE_ENABLED=false`, tidak ada gerbang sama sekali dan konsol tidak
menampilkan apa pun soal langganan.

---

## 4. Memasang kunci privat di site

Sekali saja, per site penerbit. **Jangan** di site demo atau site pelanggan.

```bash
ssh autoerpprod
# site_config.json itu JSON, jadi PEM ditulis SATU BARIS dengan \n literal.
bench --site app.smagri.id set-config autograde_license_private_key '-----BEGIN PRIVATE KEY-----\nMC4...\n-----END PRIVATE KEY-----\n'
bench --site app.smagri.id set-config autograde_license_kid v1
```

⚠️ **Jangan pernah menempel kunci privat ke chat.** Pernah kejadian 2026-08-21 dan
seluruh pasangan kunci harus dirotasi. Salurkan langsung lewat `ssh`.

Site tanpa kunci ini menolak menerbitkan dengan pesan "This site does not issue
AutoGrade licences" — itu perilaku yang benar, bukan kerusakan.

---

## 5. Kalau mau ganti pasangan kunci

Kunci publik ditanam di **tiga** tempat dan ketiganya harus nilai yang sama:

| Berkas | Konstanta | Repo |
|---|---|---|
| `src/palmgrade/core/config.py` | `LICENSE_PUBLIC_KEY_BAKED` | autograde |
| `docs/runbooks/files/autograde.sh` | `LICENSE_PUBLIC_KEY_BAKED` | sawit |
| `src/utils/license.ts` | `BAKED_IN_LICENSE_PUBLIC_KEY` | palmgrade-api (pensiun) |

**Urutannya tidak boleh dibalik:** image yang memverifikasi kunci baru harus sudah
live di pabrik **sebelum** token baru dicetak. Kalau dibalik, token baru ditolak PC
pabrik karena image lama masih memegang kunci lama.

Rinciannya: `sawit/docs/runbooks/2026-08-21-rotasi-kunci-lisensi-reset-db.md`.

---

## 6. Kalau token ditolak di pabrik

Skrip menjawab dengan kalimat, bukan kode. Artinya:

| Pesan | Sebabnya | Yang dikerjakan |
|---|---|---|
| "nggak berbentuk token" | copy terpotong, ada spasi atau baris baru | copy ulang utuh |
| "Tanda tangan nggak cocok" | ada karakter berubah saat copy, atau kunci berbeda | terbitkan ulang, copy pakai tombol |
| "sudah kedaluwarsa" | tanggalnya sudah lewat sebelum dipasang | terbitkan baris baru |
| "belum punya kunci publik" | `LICENSE_PUBLIC_KEY` kosong dan image terlalu lama | naikkan versi AutoGrade |

Token lama **tetap terpasang apa adanya** kalau yang baru ditolak. Pabrik tidak
berhenti karena salah paste.

---

## 7. Yang sengaja tidak dikerjakan

- **Kirim token otomatis ke PC pabrik.** PC-nya offline dan tidak punya SSH masuk.
  Sekali per pelanggan per tahun tidak layak diotomasi.
- **AutoERP menolak `upsert_visit` dari pabrik yang lisensinya habis.** Gerbang
  yang sesungguhnya ada di kamera; kalau kamera berhenti, tidak ada yang dikirim.
  Datanya sudah ada di DocType ini kalau nanti memang perlu.
