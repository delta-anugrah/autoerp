# Copyright (c) 2026, AutoERP and contributors
# For license information, please see license.txt

"""The demo carries a mill administrator, and its roles come from the profile.

Read as source, not run against a database, for the same reason as `test_demo_off`:
these properties are decidable from the code, and a test needing a live site could
not run in CI.

What is load-bearing:

* The demo must show the account a client actually administers with. `Administrator`
  is the site's own superuser and is meant to be put away after handover, so a demo
  that only offers it teaches the wrong habit.
* The admin's roles must be `ROLE_PROFILES[PROFILE_ADMIN]`, not a list typed out
  again here. Those two drifted once already (autoerp #26): the profile gained the
  module roles and a second copy did not, and the account opened a blank workspace.
* `System Manager` is what separates this account from `manajer@`. Without it the
  admin cannot create users, which is the one thing the demo is meant to show.
"""

import ast
import pathlib
import unittest

PALM_MILL = pathlib.Path(__file__).resolve().parent
DEMO = PALM_MILL / "demo.py"


def _modul(path):
	return ast.parse(path.read_text(encoding="utf-8"))


def _tetapan(pohon, nama):
	"""Nilai sebuah assignment tingkat modul, sebagai simpul AST."""
	for simpul in pohon.body:
		if isinstance(simpul, ast.Assign):
			for target in simpul.targets:
				if isinstance(target, ast.Name) and target.id == nama:
					return simpul.value
	raise AssertionError(f"{path_nama(pohon)} tidak punya {nama}")


def path_nama(_pohon):
	return "demo.py"


def _desk_users():
	"""DESK_USERS sebagai daftar tuple python, email dan nama saja."""
	simpul = _tetapan(_modul(DEMO), "DESK_USERS")
	baris = []
	for el in simpul.elts:
		email = el.elts[0].value
		baris.append((email, ast.unparse(el)))
	return baris


def _fungsi(nama):
	for simpul in _modul(DEMO).body:
		if isinstance(simpul, ast.FunctionDef) and simpul.name == nama:
			return simpul
	raise AssertionError(f"demo.py tidak punya fungsi {nama}()")


def _sumber_user(email):
	"""Baris DESK_USERS untuk satu email, sebagai teks — assert, bukan StopIteration."""
	for e, sumber in _desk_users():
		if e == email:
			return sumber
	raise AssertionError(f"DESK_USERS tidak memuat {email}")


def _profil_admin():
	"""ROLE_PROFILES[PROFILE_ADMIN] dibaca dari sumber `setup.py`.

	Lewat AST, bukan `import`: mengimpor modul itu menarik `frappe`, yang hanya ada di
	dalam bench. Berkas ini sengaja bisa dijalankan di mesin mana pun.
	"""
	pohon = _modul(PALM_MILL / "setup.py")
	nama_konstanta = {}
	for simpul in pohon.body:
		if isinstance(simpul, ast.Assign) and isinstance(simpul.value, ast.Constant):
			for t in simpul.targets:
				if isinstance(t, ast.Name):
					nama_konstanta[t.id] = simpul.value.value

	for simpul in pohon.body:
		if not isinstance(simpul, ast.Assign):
			continue
		if not any(isinstance(t, ast.Name) and t.id == "ROLE_PROFILES" for t in simpul.targets):
			continue
		# `strict=` baru ada di Python 3.10; berkas ini sengaja jalan di mesin mana pun,
		# dan dict AST selalu memberi keys dan values sepanjang.
		for kunci, nilai in zip(simpul.value.keys, simpul.value.values):  # noqa: B905
			if isinstance(kunci, ast.Name) and nama_konstanta.get(kunci.id) == "Admin Pabrik":
				return [el.value for el in nilai.elts]
	raise AssertionError("setup.py tidak punya ROLE_PROFILES[PROFILE_ADMIN]")


class TestDemoAdmin(unittest.TestCase):
	def test_demo_punya_admin_perusahaan(self):
		"""Tanpa ini demo hanya menawarkan `Administrator`, yang justru harus disimpan."""
		email = [e for e, _ in _desk_users()]

		self.assertIn(
			"admin@demo.autoerp.test",
			email,
			"DESK_USERS tanpa admin perusahaan — klien tidak punya akun untuk menambah user",
		)

	def test_role_admin_diturunkan_dari_profil(self):
		"""Daftar yang diketik ulang pernah melenceng dari profilnya (autoerp #26)."""
		sumber = _sumber_user("admin@demo.autoerp.test")

		self.assertIn(
			"ADMIN_USER_ROLES",
			sumber,
			"role admin diketik ulang, bukan diturunkan dari ROLE_PROFILES[PROFILE_ADMIN]",
		)

	def test_admin_role_memuat_system_manager(self):
		"""Yang membedakannya dari `manajer@`: hanya ini yang bisa menambah user."""
		self.assertIn("System Manager", _profil_admin())

	def test_manajer_justru_tanpa_system_manager(self):
		"""Kalau keduanya sama, menambahkan akun admin tidak menunjukkan apa pun."""
		sumber = _sumber_user("manajer@demo.autoerp.test")

		self.assertNotIn(
			"System Manager",
			sumber,
			"manajer@ memegang System Manager — batas antara manajer dan admin hilang",
		)

	def test_empat_akun_desk_dan_semuanya_khas(self):
		"""krani, mandor, manajer, admin — empat tingkat, tanpa email kembar."""
		email = [e for e, _ in _desk_users()]

		self.assertEqual(len(email), 4, f"DESK_USERS bukan empat akun: {email}")
		self.assertEqual(len(set(email)), len(email), "ada email kembar di DESK_USERS")
		for e in email:
			self.assertTrue(e.endswith("@demo.autoerp.test"), f"{e} di luar domain demo")

	def test_ringkasan_mencetak_seluruh_desk_users(self):
		"""Akun yang tidak tercetak tidak akan pernah dipakai orang.

		Yang dipatok bukan namanya, tapi bahwa ringkasan **mengiterasi** `DESK_USERS` —
		daftar yang diketik ulang di situ akan ketinggalan pada penambahan berikutnya,
		persis cara `ADMIN_USER_ROLES` pernah melenceng dari profilnya.
		"""
		ringkas = ast.unparse(_fungsi("summary"))

		self.assertIn("DESK_USERS", ringkas, "ringkasan tidak membaca DESK_USERS")
		self.assertIn("Desk logins", ringkas)
