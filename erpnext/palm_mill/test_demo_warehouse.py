# Copyright (c) 2026, AutoERP and contributors
# For license information, please see license.txt

"""Gudang yang dipilih seeder demo harus benar-benar bisa menerima barang.

Dibaca sebagai sumber, bukan dijalankan terhadap database, dengan alasan yang sama
seperti `test_demo_off`: sifat ini bisa diputuskan dari kodenya, dan tes yang
menuntut site hidup tidak akan jalan di CI.

Yang ditahan di sini, dan kenapa:

* `hide_seed_masters()` (`setup.py`) **menonaktifkan** `Stores`, `Finished Goods`,
  `Goods In Transit`, dan `Work In Progress` di setiap site. Seeder yang memilih
  `Stores - <ABBR>` hanya karena baris itu ADA akan menunjuk gudang mati.
* `All Warehouses - <ABBR>` adalah **group node** — wadah, bukan tempat barang.
  ERPNext menolaknya dengan "Group node warehouse is not allowed to select for
  transactions", dan penolakan itu baru muncul saat orang menekan Receive Stock,
  jauh setelah seeder mengaku berhasil.

Dua-duanya sudah terjadi di site nyata 2026-09-21 (`app.smagri.id`), dan biayanya
satu sesi penelusuran. Di demo akibatnya lebih mahal: layar pertama yang dilihat
klien.
"""

import ast
import pathlib
import unittest

PALM_MILL = pathlib.Path(__file__).resolve().parent
DEMO = PALM_MILL / "demo.py"


def _fungsi(pohon, nama):
	for simpul in ast.walk(pohon):
		if isinstance(simpul, ast.FunctionDef) and simpul.name == nama:
			return simpul
	raise AssertionError(f"fungsi {nama} tidak ada di demo.py")


class TestDemoWarehouse(unittest.TestCase):
	def setUp(self):
		self.pohon = ast.parse(DEMO.read_text(encoding="utf-8"))
		self.warehouse = _fungsi(self.pohon, "_warehouse")
		self.sumber = ast.unparse(self.warehouse)

	def test_tidak_memilih_gudang_yang_dinonaktifkan(self):
		"""`hide_seed_masters` mematikan gudang bawaan; memilihnya = menunjuk yang mati."""
		self.assertIn(
			"disabled",
			self.sumber,
			"_warehouse() tidak pernah memeriksa `disabled` — akan memilih gudang yang "
			"sudah dimatikan hide_seed_masters()",
		)

	def test_tidak_memilih_group_node(self):
		"""Group node ditolak ERPNext saat transaksi, bukan saat dipilih.

		Diperiksa lewat `is_group: 0` di saringannya, bukan sekadar kata `is_group`
		muncul di suatu tempat — versi lama pun memuatnya, di baris yang tidak pernah
		terpakai karena baris di atasnya sudah mengembalikan `All Warehouses`.
		"""
		self.assertIn(
			"'is_group': 0",
			self.sumber,
			"_warehouse() tidak menyaring dengan `is_group: 0` — bisa mengembalikan "
			"`All Warehouses`, yang ditolak dengan 'Group node warehouse is not allowed'",
		)

	def test_all_warehouses_tidak_pernah_jadi_pilihan(self):
		"""Group node itu sah sebagai INDUK gudang baru, tidak sah sebagai hasil.

		Membaca tiap `return` dan menolak yang mengembalikan namanya begitu saja —
		persis yang dilakukan versi lama. `parent_warehouse` di dalam `get_doc`
		dikecualikan: di situ nama yang sama justru benar.
		"""
		for simpul in ast.walk(self.warehouse):
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

	def test_membuat_gudang_kalau_tidak_ada_yang_layak(self):
		"""Site yang keempat gudang bawaannya mati tidak punya satu pun yang bisa dipakai.

		Mengembalikan None di situ membuat seeder mengaku berhasil dan meninggalkan
		`tbs_warehouse` kosong — kegagalan yang baru terlihat saat klien menekan tombol.
		"""
		self.assertIn(
			"Warehouse",
			self.sumber,
			"_warehouse() tidak membuat gudang sendiri",
		)
		self.assertTrue(
			any(isinstance(s, ast.Call) and "insert" in ast.unparse(s) for s in ast.walk(self.warehouse))
			or "get_doc" in self.sumber,
			"_warehouse() tidak pernah membuat gudang — site tanpa gudang layak akan "
			"mendapat tbs_warehouse kosong",
		)
