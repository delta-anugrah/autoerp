# Copyright (c) 2026, AutoERP and Contributors
# See license.txt

"""`make reset-data-fresh` mengosongkan site, jadi penjaganya yang dites.

Target ini membuang seluruh isi site: tiket, kunjungan, Purchase Receipt beserta
jurnalnya, semua master, semua user selain Administrator, dan berkas unggahan.
Tanpa backup, atas permintaan operator 2026-09-18 — sama seperti pasangannya di
AutoGrade.

Yang dijaga di sini bukan perilakunya (itu `bench reinstall`, punya Frappe), tapi
empat hal yang membuatnya tidak mengosongkan site yang salah:

* dua target terpisah — `reset-data` cuma melihat, `reset-data-fresh` menghapus;
* yang menghapus minta **nama site diketik**, bukan y/n. `make reset-data-fresh
  SITE=...` yang salah tunjuk adalah cara paling mudah mengosongkan site yang
  keliru, dan mengetik nama site memaksa orangnya membaca nama itu sekali lagi;
* memakai `bench reinstall`, **bukan `drop-site`** — `site_config.json` harus
  selamat, karena di situ ada kunci API AutoGrade dan sandi database;
* peringatannya menyebut kunci AutoGrade harus diterbitkan ulang, karena user
  integrasinya ikut terhapus dan PC pabrik akan ditolak 401 tanpa itu.
"""

import pathlib
import re

from frappe.tests import IntegrationTestCase

MAKEFILE = (pathlib.Path(__file__).resolve().parents[2] / "Makefile").read_text()


def _target(nama: str) -> str:
	"""Isi satu target Makefile, sampai target berikutnya."""
	blok = re.search(rf"^{nama}:\n(.*?)(?=^[a-zA-Z][a-zA-Z0-9_-]*:)", MAKEFILE, re.S | re.M)
	assert blok, f"target {nama!r} tidak ditemukan"
	return blok.group(1)


class IntegrationTestResetData(IntegrationTestCase):
	def test_dua_target_terpisah(self):
		"""`reset-data` melihat, `reset-data-fresh` menghapus."""
		self.assertIn("\nreset-data:\n", MAKEFILE)
		self.assertIn("\nreset-data-fresh:\n", MAKEFILE)

	def test_target_yang_dilihat_tidak_mengubah_apa_pun(self):
		"""Nama yang mirip adalah cara paling mudah kehilangan data karena salah
		ketik, jadi yang bernama pendek justru yang aman."""
		blok = _target("reset-data")
		self.assertNotIn("reinstall", blok, "target lihat-saja ikut mengosongkan site")
		self.assertNotIn("drop-site", blok)

	def test_yang_menghapus_minta_nama_site_diketik(self):
		"""Bukan y/n: satu huruf bisa terkirim dari riwayat perintah. Nama site
		yang diketik memaksa orangnya membaca sekali lagi site mana yang kena —
		`SITE=` yang salah tunjuk tidak akan cocok."""
		blok = _target("reset-data-fresh")
		self.assertIn("read jawab", blok, "tidak ada konfirmasi")
		self.assertIn('"$(SITE)"', blok, "konfirmasinya tidak mencocokkan nama site")
		self.assertIn("exit 1", blok, "jawaban salah tidak membatalkan")
		self.assertLess(
			blok.index("read jawab"), blok.index("reinstall"),
			"site dikosongkan sebelum jawaban dibaca",
		)

	def test_memakai_reinstall_bukan_drop_site(self):
		"""`drop-site` ikut menghapus `site_config.json`, dan memasang ulangnya
		berarti menerbitkan kunci API baru — AutoGrade di PC pabrik ditolak 401
		sampai `ERP_KEY`-nya ikut diganti. `reinstall` membuang isinya saja."""
		blok = _target("reset-data-fresh")
		self.assertIn("reinstall", blok)
		self.assertNotIn("drop-site", blok)

	def test_peringatan_menyebut_kunci_autograde_harus_diterbitkan_lagi(self):
		"""User integrasi ikut terhapus. Tanpa `make key-new` sesudahnya, PC
		pabrik mengirim janjang ke site yang menolaknya — dan itu terlihat
		sebagai 401 di log line, jauh dari orang yang menjalankan perintah ini."""
		gabungan = _target("reset-data") + _target("reset-data-fresh")
		self.assertIn("key-new", gabungan)
