# Copyright (c) 2026, AutoERP and contributors
# For license information, please see license.txt

"""`demo.off()` deletes the demo tickets and stops — it must never re-seed.

Read as source, not run against a database: these are the properties that make the
function safe to point at a site, and every one of them is decidable from the code.
A test that needed a live site could not run in CI, and this is exactly the kind of
function nobody wants to discover is wrong by running it on the wrong site.

Three things are load-bearing:

* `off` must not call `seed`. `reset` deletes and immediately re-seeds; if `off`
  did too, "clean up after the showcase" would quietly leave the demo in place.
* `off` must go through `_check_allowed`, like `seed` and `reset`. Without it a
  typo in `--site` points a deletion at a production site.
* The deletion is filtered by `autograde_visit_id LIKE 'DEMO-%'` — an explicit
  marker written into the row, not a guess from plate or company. AutoGrade's own
  seeder filters by plate, and there `BG 9911 ZA` (demo) and `BG 9911 ZZ` (a real
  truck) differ by one letter.
"""

import ast
import pathlib
import unittest

DEMO = pathlib.Path(__file__).resolve().parent / "demo.py"


def _fungsi(nama):
	pohon = ast.parse(DEMO.read_text(encoding="utf-8"))
	for simpul in pohon.body:
		if isinstance(simpul, ast.FunctionDef) and simpul.name == nama:
			return simpul
	raise AssertionError(f"demo.py tidak punya fungsi {nama}()")


def _dipanggil(simpul):
	return {
		n.func.id
		for n in ast.walk(simpul)
		if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
	}


class TestDemoOff(unittest.TestCase):
	def test_off_tidak_mengisi_ulang(self):
		"""Pembeda satu-satunya dari `reset`."""
		dipanggil = _dipanggil(_fungsi("off"))

		self.assertNotIn("seed", dipanggil, "off() memanggil seed() — itu reset, bukan off")
		self.assertIn("wipe_visits", dipanggil)

	def test_reset_memang_masih_mengisi_ulang(self):
		"""Kalau ini gagal, keduanya jadi sama dan salah satunya tidak ada gunanya."""
		self.assertIn("seed", _dipanggil(_fungsi("reset")))

	def test_off_lewat_penjaga_demo_mode(self):
		"""Tanpa ini, satu salah ketik `--site` mengarahkan penghapusan ke situs produksi."""
		self.assertIn("_check_allowed", _dipanggil(_fungsi("off")))

	def test_penghapusan_disaring_penanda_eksplisit(self):
		"""Bukan menebak dari plat atau perusahaan: `autograde_visit_id LIKE 'DEMO-%'`."""
		sumber = ast.unparse(_fungsi("wipe_visits"))

		self.assertIn("autograde_visit_id", sumber)
		self.assertIn("VISIT_PREFIX", sumber)

	def test_off_bisa_dipanggil_seperti_seed_dan_reset(self):
		"""`bench execute` mengoper kwargs; ketiganya harus menerima `force` dan `quiet`."""
		for nama in ("seed", "reset", "off"):
			arg = {a.arg for a in _fungsi(nama).args.args}
			self.assertIn("force", arg, f"{nama}() tanpa force=")
			self.assertIn("quiet", arg, f"{nama}() tanpa quiet=")
