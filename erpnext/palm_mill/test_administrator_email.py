# Copyright (c) 2026, AutoERP and Contributors
# See license.txt

"""Akun Administrator tidak boleh lahir dengan alamat contoh.

Frappe memaku `admin@example.com` di `frappe/utils/install.py`, dan itu bukan
sekadar jelek dilihat: `example.com` adalah domain contoh milik IANA yang memang
tidak menerima surat. Apa pun yang dikirim ke sana hilang — termasuk tautan
atur-ulang sandi untuk akun paling berkuasa di site ini.

Nilainya tidak bisa disetel lewat `site_config` maupun flag `bench new-site`,
jadi satu-satunya jalan adalah menimpanya sesudah site jadi. Dua tempat, dan
keduanya wajib: `after_install` untuk site baru (yang tidak pernah menjalankan
patch) dan sebuah patch untuk site yang sudah jalan.
"""

import frappe
from frappe.tests import IntegrationTestCase

from erpnext.palm_mill.setup import (
	ADMINISTRATOR_EMAIL,
	set_administrator_email,
	set_administrator_timezone,
)

BAWAAN_FRAPPE = "admin@example.com"


class IntegrationTestAdministratorEmail(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		self.semula = frappe.db.get_value("User", "Administrator", "email")
		self.addCleanup(self._kembalikan)

	def _kembalikan(self):
		frappe.db.set_value("User", "Administrator", "email", self.semula, update_modified=False)

	def _pasang(self, email):
		frappe.db.set_value("User", "Administrator", "email", email, update_modified=False)

	def _baca(self):
		return frappe.db.get_value("User", "Administrator", "email")

	def test_alamat_contoh_diganti(self):
		self._pasang(BAWAAN_FRAPPE)

		set_administrator_email()

		self.assertEqual(self._baca(), ADMINISTRATOR_EMAIL)

	def test_alamat_kita_pakai_domain_sungguhan(self):
		"""`example.com` tidak menerima surat, jadi tautan reset sandi ke sana
		hilang tanpa jejak."""
		self.assertNotIn("example.com", ADMINISTRATOR_EMAIL)
		self.assertTrue(ADMINISTRATOR_EMAIL.endswith("@smagri.id"))

	def test_dijalankan_dua_kali_tidak_berubah(self):
		"""Patch jalan ulang tiap migrate."""
		self._pasang(BAWAAN_FRAPPE)
		set_administrator_email()
		set_administrator_email()

		self.assertEqual(self._baca(), ADMINISTRATOR_EMAIL)

	def test_alamat_yang_sudah_diganti_orang_dibiarkan(self):
		"""Kalau seseorang sudah menyetelnya ke alamat lain — sengaja — menariknya
		balik akan memutus notifikasi yang mungkin sudah mereka andalkan."""
		self._pasang("bos@pks-lain.co.id")

		set_administrator_email()

		self.assertEqual(self._baca(), "bos@pks-lain.co.id")

	def test_alamat_contoh_lain_ikut_diganti(self):
		"""`guest@example.com` dan kawan-kawannya sama saja: domain yang tidak
		menerima surat."""
		self._pasang("sesuatu@example.com")

		set_administrator_email()

		self.assertEqual(self._baca(), ADMINISTRATOR_EMAIL)

	def test_ikut_dipasang_saat_install(self):
		"""Site baru TIDAK pernah menjalankan patch (`install_app` menandainya
		selesai tanpa mengeksekusi apa pun), jadi kalau ini hilang dari
		`after_install`, setiap site berikutnya lahir dengan alamat contoh lagi.
		"""
		import pathlib

		import erpnext

		setup = (pathlib.Path(erpnext.__file__).parent / "palm_mill/setup.py").read_text()
		blok = setup[setup.index("def apply_site_policy") : setup.index("def set_administrator_email")]
		self.assertIn("set_administrator_email()", blok)

	def test_patch_terdaftar(self):
		"""Site yang sudah jalan cuma bisa dijangkau lewat patch."""
		import pathlib

		import erpnext

		patches = (pathlib.Path(erpnext.__file__).parent / "patches.txt").read_text()
		self.assertIn("palm_mill_administrator_email", patches)


class IntegrationTestAdministratorTimezone(IntegrationTestCase):
	"""Zona waktu Administrator harus mengikuti zona site.

	Frappe memberi user baru `Asia/Kolkata`. Kolom `time_zone` pada User menang
	atas System Settings, jadi setiap tanggal-jam yang dilihat Administrator
	digeser 1,5 jam dari waktu pabrik — tanpa tanda apa pun selain label kecil
	di sebelah kolom, dan dengan nilai di database yang sudah benar.

	Terlihat pertama kali di kolom "Grace Ends" layar lisensi (2026-09-22):
	tanggal yang menentukan kapan sebuah pabrik berhenti menggiling.
	"""

	def setUp(self):
		super().setUp()
		self.semula = frappe.db.get_value("User", "Administrator", "time_zone")
		self.addCleanup(
			lambda: frappe.db.set_value(
				"User", "Administrator", "time_zone", self.semula, update_modified=False
			)
		)

	def _pasang(self, zona):
		frappe.db.set_value("User", "Administrator", "time_zone", zona, update_modified=False)

	def _baca(self):
		return frappe.db.get_value("User", "Administrator", "time_zone")

	def test_zona_bawaan_frappe_diganti(self):
		self._pasang("Asia/Kolkata")

		set_administrator_timezone()

		zona_site = frappe.db.get_single_value("System Settings", "time_zone")
		self.assertEqual(self._baca(), zona_site)

	def test_mengikuti_zona_site_apa_pun_isinya(self):
		"""Bukan dipatok ke Asia/Jakarta: site pelanggan di zona lain harus tetap
		benar, dan memaku satu zona akan salah di sana."""
		self._pasang("Asia/Kolkata")
		semula_site = frappe.db.get_single_value("System Settings", "time_zone")
		self.addCleanup(frappe.db.set_single_value, "System Settings", "time_zone", semula_site)
		frappe.db.set_single_value("System Settings", "time_zone", "Asia/Makassar")

		set_administrator_timezone()

		self.assertEqual(self._baca(), "Asia/Makassar")

	def test_dijalankan_dua_kali_tidak_berubah(self):
		self._pasang("Asia/Kolkata")
		set_administrator_timezone()
		zona = self._baca()

		set_administrator_timezone()

		self.assertEqual(self._baca(), zona)

	def test_ikut_dipasang_saat_install(self):
		"""Site baru tidak pernah menjalankan patch, jadi tanpa baris ini setiap
		site berikutnya lahir dengan zona India lagi."""
		import pathlib

		import erpnext

		setup = (pathlib.Path(erpnext.__file__).parent / "palm_mill/setup.py").read_text()
		blok = setup[setup.index("def apply_site_policy") : setup.index("def set_administrator_email")]
		self.assertIn("set_administrator_timezone()", blok)

	def test_patch_terdaftar(self):
		import pathlib

		import erpnext

		patches = (pathlib.Path(erpnext.__file__).parent / "patches.txt").read_text()
		self.assertIn("palm_mill_administrator_timezone", patches)
