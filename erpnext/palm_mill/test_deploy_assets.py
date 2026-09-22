# Copyright (c) 2026, AutoERP and Contributors
# See license.txt

"""Aset hasil build harus mendarat di folder yang benar-benar dilayani.

Image dasar punya `entrypoint.sh` yang, **tiap container start**, menghapus
`sites/assets` lalu menggantinya dengan symlink ke `frappe-bench/assets`:

    rm -rf sites/assets && ln -s /home/frappe/frappe-bench/assets sites/assets

Sementara `bench build` menulis ke `sites/assets`. Selama build keduanya folder
terpisah, jadi tanpa langkah penyatuan, hasil build dibuang mentah-mentah begitu
container jalan.

**Gagalnya tidak terlihat sama sekali.** Yang paling terasa `assets.json`, peta
nama-ber-hash yang dibaca Desk: peta lama menunjuk `erpnext.bundle.ALITV7QQ.js`
sementara bundle yang ada bernama `erpnext.bundle.KIPLZ2KM.js`. Tidak ada error,
tidak ada 404 yang terlihat, browser cuma memakai salinan lama dari cache.

Terbukti di produksi 2026-09-22: setiap perubahan JavaScript sejak 17 September
tidak pernah sampai ke layar. Yang pertama terlihat adalah kartu angka bernilai
nol yang mencetak "Rp NaN" — penambalnya sudah ikut di image sejak lama dan tidak
pernah dimuat.

⚠️ **Dua jalan keluar yang sudah dicoba dan TIDAK bekerja**, jangan diulang:

1. `bench build` di server. `node_modules` sengaja dihapus dari image, jadi
   berhenti di "Could not resolve onscan.js".
2. Menyalin dari penampungan lewat `configurator` di compose. Penyalinannya
   berhasil, lalu `entrypoint.sh` menimpanya dengan symlink beberapa detik
   kemudian. Container keluar dengan kode 0 dan tidak ada yang memberi tahu.
"""

import pathlib

from frappe.tests import IntegrationTestCase

ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTAINERFILE = ROOT / "deploy/Containerfile"
COMPOSE = ROOT / "deploy/droplet/docker-compose.prod.yml"

# Ke mana `bench build` menulis, dan dari mana runtime membaca.
BUILD_KE = "/home/frappe/frappe-bench/sites/assets"
RUNTIME_DARI = "/home/frappe/frappe-bench/assets"
SKRIP = "deploy/merge_assets.py"


class IntegrationTestDeployAssets(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		if not CONTAINERFILE.exists() or not COMPOSE.exists():
			self.skipTest("berkas deploy tidak ada di checkout ini")
		self.containerfile = CONTAINERFILE.read_text()
		self.compose = COMPOSE.read_text()

	def test_image_membangun_aset(self):
		"""Langkah 1. Tanpa ini tidak ada apa pun untuk disatukan."""
		self.assertIn("bench build --app erpnext --production", self.containerfile)

	def test_hasil_build_disatukan_ke_folder_runtime(self):
		"""Langkah 2, dan inti dari seluruh berkas test ini.

		Tanpa langkah ini `bench build` tetap sukses, image tetap jadi, deploy tetap
		hijau — dan asetnya tetap tidak pernah dipakai.
		"""
		self.assertIn("merge_assets.py", self.containerfile)
		self.assertTrue((ROOT / SKRIP).exists(), f"{SKRIP} hilang")

	def test_penyatuan_terjadi_sesudah_build(self):
		"""Urutan terbalik berarti yang disatukan adalah aset lama."""
		build = self.containerfile.index("bench build --app erpnext --production")
		satukan = self.containerfile.index("merge_assets.py")
		self.assertLess(build, satukan)

	def test_peta_digabung_bukan_ditimpa(self):
		"""Peta hasil build cuma memuat kunci erpnext (8); peta runtime memuat
		seluruh app (44), termasuk `desk.bundle.js`. Menimpanya membuat Desk
		kehilangan bundle-nya sendiri dan berhenti memuat apa pun.

		Ketahuan saat mensimulasikan langkah ini di dalam image sebelum dirilis.
		"""
		skrip = (ROOT / SKRIP).read_text()
		self.assertIn("{**lama, **baru}", skrip)

	def test_symlink_ke_diri_sendiri_dilewati(self):
		"""Sebagian entri di `sites/assets/` sudah symlink ke `assets/`. Menyalinnya
		berarti menyalin berkas ke dirinya sendiri, dan `shutil` berhenti dengan
		"are the same file" untuk ratusan berkas sekaligus."""
		skrip = (ROOT / SKRIP).read_text()
		self.assertIn("item.resolve() == tujuan.resolve()", skrip)

	def test_build_dibatalkan_kalau_peta_menunjuk_berkas_hantu(self):
		"""Peta yang menunjuk berkas yang tidak ada adalah persis kegagalan yang
		bikin masalah ini tidak ketahuan berhari-hari. Diperiksa selagi build
		masih bisa dibatalkan, bukan ditemukan di produksi."""
		skrip = (ROOT / SKRIP).read_text()
		self.assertIn("PETA MENUNJUK BERKAS YANG TIDAK ADA", skrip)
		self.assertIn("return 1", skrip)

	def test_penyatuan_tidak_dibungkam(self):
		"""`|| true` di sini mengembalikan persis kegagalan senyap yang bikin
		masalah ini tidak ketahuan berhari-hari."""
		baris = next(ln for ln in self.containerfile.splitlines() if "merge_assets.py" in ln and "RUN" in ln)
		self.assertNotIn("|| true", baris)
		self.assertNotIn("2>/dev/null", baris)

	def test_compose_tidak_mencoba_menyalin_aset_sendiri(self):
		"""Sudah dicoba dan tidak bekerja: `entrypoint.sh` menimpanya dengan
		symlink beberapa detik sesudahnya, tanpa satu pun pesan.

		Dibiarkan ada, baris itu terbaca seperti pengaman kedua padahal tidak
		pernah berpengaruh.
		"""
		self.assertNotIn("image-assets", self.compose)

	def test_node_modules_memang_dihapus_dari_image(self):
		"""Alasan kenapa `bench build` di server BUKAN jalan keluarnya.

		Kalau baris ini hilang, catatan 'tidak bisa build di server' jadi bohong
		dan orang berikutnya akan membuang waktu mengikutinya.
		"""
		self.assertIn("rm -rf apps/erpnext/node_modules", self.containerfile)

	def test_alasannya_tertulis_di_skrip(self):
		"""Satu langkah `cp` terlihat seperti sesuatu yang bisa dirapikan.

		Yang menahannya cuma penjelasan; tanpa itu langkah ini akan dihapus orang
		yang merasa sedang membersihkan, dan gejalanya baru muncul berhari-hari
		kemudian sebagai "kenapa perbaikan JS saya tidak kelihatan".
		"""
		skrip = (ROOT / SKRIP).read_text()
		self.assertIn("entrypoint.sh", skrip)
		self.assertIn("assets.json", skrip)

	def test_alasannya_tertulis_di_containerfile(self):
		"""Satu baris `cp` terlihat seperti sesuatu yang bisa dirapikan.

		Yang menahannya cuma komentar; tanpa itu baris ini akan dihapus orang yang
		merasa sedang membersihkan, dan gejalanya baru muncul berhari-hari kemudian
		sebagai "kenapa perbaikan JS saya tidak kelihatan".
		"""
		self.assertIn("entrypoint.sh", self.containerfile)
		self.assertIn("assets.json", self.containerfile)
