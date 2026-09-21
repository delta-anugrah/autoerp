# Copyright (c) 2026, AutoERP and contributors
# For license information, please see license.txt

"""Site baru harus lahir dengan satu gudang yang benar-benar bisa menerima TBS.

Ini kembaran `test_demo_warehouse` untuk site NON-demo — yang dipakai pelanggan.
Seeder demo sudah diperbaiki (autoerp #39); jalur install belum, dan lubangnya sama
persis:

`setup_wizard_complete()` memanggil `hide_seed_masters()`, yang **menonaktifkan**
keempat gudang bawaan ERPNext (`Stores`, `Finished Goods`, `Goods In Transit`,
`Work In Progress`). Tidak ada yang membuat penggantinya. Yang tersisa hidup cuma
`All Warehouses - <ABBR>`, dan itu **group node** — wadah, bukan tempat barang.

Akibatnya site baru punya NOL gudang yang bisa menerima barang, dan penerimaan TBS
mustahil sampai seseorang membuat gudang dengan tangan. Terbukti di `app.smagri.id`
2026-09-21: keempat gudang non-group `disabled: 1`, dan `Create -> Receive Stock`
menjawab "Group node warehouse is not allowed to select for transactions".

Dibaca sebagai sumber, bukan dijalankan terhadap database, dengan alasan yang sama
seperti `test_demo_off` dan `test_demo_warehouse`: sifat ini bisa diputuskan dari
kodenya, dan tes yang menuntut site hidup tidak akan jalan di CI.
"""

import ast
import pathlib
import unittest

PALM_MILL = pathlib.Path(__file__).resolve().parent
SETUP = PALM_MILL / "setup.py"


def _fungsi(pohon, nama):
	for simpul in ast.walk(pohon):
		if isinstance(simpul, ast.FunctionDef) and simpul.name == nama:
			return simpul
	raise AssertionError(f"fungsi {nama} tidak ada di setup.py")


def _dipanggil(simpul) -> set[str]:
	"""Nama fungsi yang dipanggil langsung di dalam `simpul`."""
	nama = set()
	for anak in ast.walk(simpul):
		if isinstance(anak, ast.Call) and isinstance(anak.func, ast.Name):
			nama.add(anak.func.id)
	return nama


class TestSetupWarehouse(unittest.TestCase):
	def setUp(self):
		self.pohon = ast.parse(SETUP.read_text(encoding="utf-8"))

	def test_ada_fungsi_yang_membuat_gudang_tbs(self):
		"""Tanpa ini, site baru tidak punya satu pun gudang yang bisa menerima barang."""
		fungsi = _fungsi(self.pohon, "ensure_ffb_warehouse")
		sumber = ast.unparse(fungsi)
		self.assertIn(
			"Warehouse",
			sumber,
			"ensure_ffb_warehouse() tidak menyentuh Warehouse sama sekali",
		)

	def test_menyaring_gudang_mati_dan_group_node(self):
		"""Dua saringan yang dua-duanya sudah memakan waktu di site nyata.

		`disabled: 0` karena `hide_seed_masters` mematikan gudang bawaan; `is_group: 0`
		karena group node ditolak ERPNext saat transaksi, bukan saat dipilih.
		"""
		sumber = ast.unparse(_fungsi(self.pohon, "ensure_ffb_warehouse"))
		self.assertIn(
			"'disabled': 0",
			sumber,
			"ensure_ffb_warehouse() tidak menyaring `disabled: 0` — bisa menunjuk gudang "
			"yang sudah dimatikan hide_seed_masters()",
		)
		self.assertIn(
			"'is_group': 0",
			sumber,
			"ensure_ffb_warehouse() tidak menyaring `is_group: 0` — bisa mengembalikan "
			"`All Warehouses`, yang ditolak 'Group node warehouse is not allowed'",
		)

	def test_all_warehouses_tidak_pernah_jadi_hasil(self):
		"""Group node sah sebagai INDUK gudang baru, tidak sah sebagai hasil."""
		fungsi = _fungsi(self.pohon, "ensure_ffb_warehouse")
		for simpul in ast.walk(fungsi):
			if not (isinstance(simpul, ast.Return) and simpul.value is not None):
				continue
			teks = ast.unparse(simpul.value)
			if "parent_warehouse" in teks:
				continue  # membuat gudang BARU di bawah group node: benar
			self.assertNotIn(
				"All Warehouses",
				teks,
				"sebuah `return` mengembalikan `All Warehouses`, yang group node",
			)

	def test_menunjuk_gudang_itu_di_palm_mill_settings(self):
		"""Gudang yang ada tapi tidak ditunjuk tetap meninggalkan penerimaan TBS mati.

		`tbs_warehouse` adalah field yang dibaca jalur tiket; membuat gudang tanpa
		mengisinya cuma memindahkan kegagalan satu langkah ke hilir.
		"""
		sumber = ast.unparse(_fungsi(self.pohon, "ensure_ffb_warehouse"))
		self.assertIn(
			"tbs_warehouse",
			sumber,
			"ensure_ffb_warehouse() tidak pernah mengisi `tbs_warehouse` di Palm Mill "
			"Settings — gudangnya dibuat tapi tidak dipakai",
		)

	def test_dipanggil_sesudah_hide_seed_masters(self):
		"""Harus di `setup_wizard_complete`, bukan `after_install`.

		Alasannya sama dengan `hide_seed_masters` sendiri (lihat docstring-nya): gudang
		bawaan baru ada setelah wizard membuat Company. Dipanggil dari `after_install`
		fungsi ini tidak menemukan apa pun untuk disaring DAN tidak punya company untuk
		membuat gudang baru.
		"""
		wizard = _fungsi(self.pohon, "setup_wizard_complete")
		self.assertIn(
			"ensure_ffb_warehouse",
			_dipanggil(wizard),
			"setup_wizard_complete() tidak memanggil ensure_ffb_warehouse() — site baru "
			"tetap lahir tanpa gudang yang bisa menerima barang",
		)

	def test_dijalankan_sesudah_gudang_bawaan_dimatikan(self):
		"""Urutan menentukan hasilnya.

		Dijalankan SEBELUM `hide_seed_masters`, fungsi ini akan menemukan `Stores` masih
		hidup, menunjuknya, dan `hide_seed_masters` mematikannya sesaat kemudian —
		`tbs_warehouse` menunjuk gudang mati dan tidak ada yang mengeluh.
		"""
		wizard = _fungsi(self.pohon, "setup_wizard_complete")
		urutan = [
			anak.func.id
			for anak in ast.walk(wizard)
			if isinstance(anak, ast.Call) and isinstance(anak.func, ast.Name)
		]
		self.assertIn("hide_seed_masters", urutan)
		self.assertIn("ensure_ffb_warehouse", urutan)
		self.assertLess(
			urutan.index("hide_seed_masters"),
			urutan.index("ensure_ffb_warehouse"),
			"ensure_ffb_warehouse() dipanggil SEBELUM hide_seed_masters() — akan menunjuk "
			"`Stores` yang dimatikan sesaat kemudian",
		)


if __name__ == "__main__":
	unittest.main()
