# Copyright (c) 2026, AutoERP and Contributors
# See license.txt

"""Aset yang dibangun harus punya jalan dari image ke volume.

`sites/` adalah volume di produksi, jadi `sites/assets/` **bertahan lintas rilis**
sementara berkas aset datang dari image yang baru. Tiap build menghasilkan nama
ber-hash baru (`erpnext.bundle.<HASH>.js`) beserta `assets.json` yang memetakannya,
jadi tanpa penyalinan eksplisit volume menyimpan peta lama yang menunjuk berkas
yang sudah tidak ada.

**Gagalnya tidak terlihat sama sekali**: tidak ada error, tidak ada 404, browser
cuma memuat bundle basi dari cache. Terbukti di produksi 2026-09-22 — `assets.json`
tertanggal 17 September masih menunjuk `erpnext.bundle.ALITV7QQ.js` sementara image
`v1.0.5` membawa `KIPLZ2KM`. Akibatnya setiap perbaikan JavaScript sejak tanggal itu
tidak pernah sampai ke layar; yang pertama terlihat adalah kartu angka bernilai nol
yang mencetak "Rp NaN" walau penambalnya sudah ikut di image.

Rantainya tiga langkah dan ketiganya harus ada. Test di bawah mengunci satu-satu,
karena memutus salah satunya tidak menghasilkan satu pun pesan.
"""

import pathlib

from frappe.tests import IntegrationTestCase

ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTAINERFILE = ROOT / "deploy/Containerfile"
COMPOSE = ROOT / "deploy/droplet/docker-compose.prod.yml"

# Tempat penampungan di luar `sites/`. Harus di luar, karena volume menutupi
# seluruh isi `sites/` milik image begitu container jalan.
STASH = "/opt/image-assets"


class IntegrationTestDeployAssets(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		if not CONTAINERFILE.exists() or not COMPOSE.exists():
			self.skipTest("berkas deploy tidak ada di checkout ini")
		self.containerfile = CONTAINERFILE.read_text()
		self.compose = COMPOSE.read_text()

	def test_image_membangun_aset(self):
		"""Langkah 1. Tanpa ini tidak ada apa pun untuk disalin."""
		self.assertIn("bench build --app erpnext --production", self.containerfile)

	def test_image_menyimpan_aset_di_luar_sites(self):
		"""Langkah 2. `sites/` ketutup volume, jadi salinannya harus di luar.

		Ini yang hilang sampai 2026-09-22: aset dibangun dengan benar lalu
		terkubur volume, tanpa jejak apa pun di log.
		"""
		self.assertIn(STASH, self.containerfile)
		self.assertRegex(self.containerfile, rf"cp -a\s+\S*sites/assets\s+{STASH}")

	def test_configurator_menyalin_aset_ke_volume(self):
		"""Langkah 3. Dijalankan tiap deploy, sebelum service lain hidup."""
		self.assertIn(f"cp -a {STASH}/. sites/assets/", self.compose)

	def test_penyalinan_terjadi_sebelum_set_config(self):
		"""Urutan penting: `configurator` keluar sesudah perintah terakhirnya, dan
		service lain menunggu dia SELESAI. Penyalinan yang tertaruh di belakang
		perintah yang bisa gagal berarti aset tidak tersalin di hari yang buruk."""
		salin = self.compose.index(f"cp -a {STASH}/. sites/assets/")
		config = self.compose.index("bench set-config -g db_host")
		self.assertLess(salin, config)

	def test_penyalinan_tidak_dibungkam(self):
		"""`|| true` di sini akan mengembalikan persis kegagalan senyap yang
		bikin masalah ini tidak ketahuan berhari-hari."""
		baris = next(ln for ln in self.compose.splitlines() if f"cp -a {STASH}/. sites/assets/" in ln)
		self.assertNotIn("|| true", baris)
		self.assertNotIn("2>/dev/null", baris)

	def test_node_modules_memang_dihapus_dari_image(self):
		"""Alasan kenapa `bench build` di server BUKAN jalan keluarnya.

		Kalau baris ini hilang, catatan 'tidak bisa build di server' jadi bohong
		dan orang berikutnya akan membuang waktu mengikutinya.
		"""
		self.assertIn("rm -rf apps/erpnext/node_modules", self.containerfile)

	def test_alasannya_tertulis_di_compose(self):
		"""Penyalinan satu baris ini terlihat seperti sesuatu yang bisa dirapikan.

		Yang menahannya cuma komentar; tanpa itu baris ini akan dihapus orang
		yang merasa sedang membersihkan.
		"""
		self.assertIn("volume", self.compose.lower())
		self.assertIn("assets.json", self.compose)
