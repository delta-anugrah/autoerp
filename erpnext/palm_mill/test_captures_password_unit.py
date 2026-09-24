# Copyright (c) 2026, AutoERP and contributors
# For license information, please see license.txt

"""The password comparison itself — no site, no bench, no database.

`matches()` is the whole decision behind `captures.smagri.id`: given what the
caller typed and what the mill configured, may these photos be shown? Everything
around it (the field, the endpoint, the permissions) is pinned by
`test_captures_password.py`, which needs a live site. This file needs nothing, so
these rules stay pinned on any machine, in milliseconds:

    python3 -m unittest discover -s erpnext/palm_mill \\
        -p "test_captures_password_unit.py" -t erpnext/palm_mill

That matters more than speed. The rule being pinned is "when do we hand over a
truckload of somebody's grading photos", and a test that only runs where MariaDB
and Redis happen to be up is a test that stops running the moment either is not.

⚠️ Deliberately NOT imported from `captures_password`, which imports `frappe` at
module level and therefore cannot load without a bench. The function is read out
of the source file and compiled on its own. If it ever grows a dependency on
`frappe`, the loader below fails loudly rather than skipping silently -- a skipped
security test is worse than a missing one, because it reads green.
"""

import ast
import pathlib
import unittest

SOURCE = pathlib.Path(__file__).parent / "captures_password.py"


def _load_matches():
	"""Compile `matches` alone, out of the module, without importing frappe.

	Pulls the single function definition out of the AST and executes just that.
	Anything it needs from the module's own imports has to be declared here, which
	is the point: the namespace below is the complete list of what this function is
	allowed to touch, and it does not include `frappe`.
	"""
	from hmac import compare_digest

	tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
	for node in tree.body:
		if isinstance(node, ast.FunctionDef) and node.name == "matches":
			namespace: dict = {"compare_digest": compare_digest}
			exec(compile(ast.Module([node], []), str(SOURCE), "exec"), namespace)
			return namespace["matches"]
	raise AssertionError("`matches` tidak ada lagi di captures_password.py")


matches = _load_matches()

SANDI = "rahasia-pabrik"


class TestCocokkanSandi(unittest.TestCase):
	"""Satu-satunya jalan ke `True`: sandi terpasang, dan ketikannya sama persis."""

	# --------------------------------------------------------------- yang lolos

	def test_sandi_sama_persis_lolos(self):
		self.assertTrue(matches(SANDI, SANDI))

	def test_sandi_satu_huruf_lolos(self):
		self.assertTrue(matches("a", "a"))

	def test_sandi_panjang_sekali_lolos(self):
		panjang = "x" * 4096
		self.assertTrue(matches(panjang, panjang))

	# --------------------------------------------------------------- yang ditolak

	def test_sandi_salah_ditolak(self):
		self.assertFalse(matches("salah", SANDI))

	def test_beda_satu_huruf_terakhir_ditolak(self):
		# Beda di ujung: inilah yang dibaca `==` paling lambat, dan alasan
		# `compare_digest` ada.
		self.assertFalse(matches("rahasia-pabrij", SANDI))

	def test_beda_satu_huruf_pertama_ditolak(self):
		self.assertFalse(matches("Rahasia-pabrik", SANDI))

	def test_awalan_benar_tetap_ditolak(self):
		"""Menebak sandi huruf demi huruf harus tidak ada gunanya."""
		for potong in range(1, len(SANDI)):
			self.assertFalse(matches(SANDI[:potong], SANDI), f"awalan {potong} huruf lolos")

	def test_sandi_ditambah_ekor_ditolak(self):
		self.assertFalse(matches(SANDI + "x", SANDI))

	def test_beda_huruf_besar_kecil_ditolak(self):
		self.assertFalse(matches(SANDI.upper(), SANDI))

	def test_spasi_di_ujung_tidak_dipangkas(self):
		# Kalau dipangkas, dua sandi berbeda jadi sandi yang sama diam-diam.
		self.assertFalse(matches(SANDI, SANDI + " "))
		self.assertFalse(matches(SANDI + " ", SANDI))
		self.assertTrue(matches(SANDI + " ", SANDI + " "))

	def test_spasi_di_depan_tidak_dipangkas(self):
		self.assertFalse(matches(" " + SANDI, SANDI))

	# ------------------------------------------------------ pintu terkunci rapat

	def test_sandi_belum_diatur_menolak_semua(self):
		"""Gerbang yang belum dikonfigurasi adalah gerbang TERTUTUP.

		Gagal ke arah terbuka akan mengubah "admin belum sempat mengisi" jadi
		"fotonya publik lagi" -- persis keadaan yang sedang diperbaiki.
		"""
		for kandidat in ("", " ", SANDI, "apa saja", "\n"):
			self.assertFalse(matches(kandidat, ""), f"{kandidat!r} lolos saat sandi kosong")

	def test_dua_duanya_kosong_tetap_ditolak(self):
		# Jebakan klasik: "" == "" itu True. Di sini harus tidak.
		self.assertFalse(matches("", ""))

	def test_kandidat_kosong_ditolak(self):
		self.assertFalse(matches("", SANDI))

	def test_kandidat_none_ditolak(self):
		# Worker mengirim JSON; field yang hilang sampai ke sini sebagai None.
		self.assertFalse(matches(None, SANDI))

	def test_kandidat_bukan_string_ditolak(self):
		"""JSON bisa membawa angka, boolean, daftar, objek. Tidak satu pun boleh
		lolos, dan tidak satu pun boleh jadi TypeError."""
		for kandidat in (0, 1, -1, True, False, [], {}, (), 3.14, b"bytes", object()):
			self.assertFalse(matches(kandidat, SANDI), f"{kandidat!r} lolos")

	def test_kandidat_bytes_yang_sama_tetap_ditolak(self):
		"""`b"rahasia" != "rahasia"`. Menerima bytes akan membuat dua tipe berbeda
		terbaca sama, dan itu jalan pintas yang tidak pernah diminta siapa pun."""
		self.assertFalse(matches(SANDI.encode(), SANDI))

	# --------------------------------------------------------- huruf non-ASCII

	def test_sandi_non_ascii_tidak_meledak(self):
		"""⚠️ Bug nyata, bukan bayangan: `compare_digest` pada `str` MELEMPAR
		TypeError untuk karakter di atas U+00FF.

		Admin yang mengetik sandi berisi "é", "ā", atau emoji akan membuat SETIAP
		permintaan foto menjawab 500 -- dan hanya di site yang kebetulan memilih
		sandi seperti itu. Diukur 2026-09-24, diperbaiki dengan membandingkan
		`bytes`, bukan `str`.
		"""
		for sandi in ("sandi-ā", "kataçSandi", "rahasia🌴", "パスワード", "Ñoño"):
			self.assertTrue(matches(sandi, sandi), f"{sandi!r} gagal cocok")
			self.assertFalse(matches(sandi + "x", sandi))
			self.assertFalse(matches("salah", sandi))

	def test_dua_bentuk_unicode_berbeda_tidak_disamakan(self):
		""" "é" bisa satu titik-kode atau dua (e + aksen). Keduanya tampak sama di
		layar tetapi byte-nya berbeda, dan tidak ada yang menormalkannya di sini --
		jadi yang tersimpan adalah persis yang diketik. Dicatat supaya perilaku ini
		diketahui, bukan ditemukan saat admin tidak bisa masuk."""
		satu = "caf\u00e9"  # é sebagai SATU titik-kode
		dua = "café"  # e + aksen gabung
		self.assertNotEqual(satu.encode(), dua.encode())
		self.assertFalse(matches(satu, dua))
		self.assertTrue(matches(satu, satu))

	# ------------------------------------------------------------ sifat umum

	def test_tidak_pernah_mengembalikan_selain_bool(self):
		"""Nilai "mirip benar" (1, "ya", daftar tak kosong) yang bocor ke pemanggil
		akan terbaca sebagai izin masuk di sisi Worker."""
		for kandidat, sandi in ((SANDI, SANDI), ("salah", SANDI), (None, ""), (1, SANDI)):
			self.assertIsInstance(matches(kandidat, sandi), bool)

	def test_tidak_mengubah_apa_pun_yang_diberikan(self):
		kandidat, sandi = SANDI, SANDI
		matches(kandidat, sandi)
		self.assertEqual(kandidat, SANDI)
		self.assertEqual(sandi, SANDI)

	def test_hasil_sama_kalau_dipanggil_berulang(self):
		# Tidak ada keadaan tersembunyi: percobaan ke-100 dijawab sama dengan yang
		# pertama. Pembatasan laju hidup di lapisan endpoint, bukan di sini.
		for _ in range(100):
			self.assertTrue(matches(SANDI, SANDI))
			self.assertFalse(matches("salah", SANDI))


class TestSumbernya(unittest.TestCase):
	"""Dibaca dari kode: sifat yang tidak bisa dibuktikan dengan memanggil."""

	def setUp(self):
		self.pohon = ast.parse(SOURCE.read_text(encoding="utf-8"))
		self.sumber = SOURCE.read_text(encoding="utf-8")

	def _fungsi(self, nama: str) -> ast.FunctionDef:
		for simpul in ast.walk(self.pohon):
			if isinstance(simpul, ast.FunctionDef) and simpul.name == nama:
				return simpul
		raise AssertionError(f"fungsi {nama} tidak ada")

	def test_memakai_compare_digest_bukan_sama_dengan(self):
		"""Diukur waktunya akan berisik dan lolos-gagal acak di CI; yang dipastikan
		di sini `compare_digest` benar-benar dipanggil di dalam `matches`."""
		dipanggil = {
			s.func.id
			for s in ast.walk(self._fungsi("matches"))
			if isinstance(s, ast.Call) and isinstance(s.func, ast.Name)
		}
		self.assertIn("compare_digest", dipanggil)

	def test_membandingkan_bytes_bukan_str(self):
		"""Inilah yang menahan TypeError non-ASCII. Hilang = 500 di site mana pun
		yang sandinya punya huruf beraksen."""
		fungsi = self._fungsi("matches")
		encode = [
			s
			for s in ast.walk(fungsi)
			if isinstance(s, ast.Call) and isinstance(s.func, ast.Attribute) and s.func.attr == "encode"
		]
		self.assertGreaterEqual(len(encode), 2, "kedua sisi harus di-encode dulu")

	def test_matches_tidak_menyentuh_frappe(self):
		"""Kalau `matches` mulai memanggil frappe, ia tidak bisa diuji tanpa site
		lagi -- dan berkas ini diam-diam berhenti menguji apa pun."""
		nama = {s.id for s in ast.walk(self._fungsi("matches")) if isinstance(s, ast.Name)}
		self.assertNotIn("frappe", nama)

	def test_check_tetap_menolak_tamu_menulis(self):
		"""`set_password` tidak boleh ikut ter-whitelist. Satu baris dekorator yang
		salah tempel membuka pintu tulis ke sandi ini."""
		fungsi = self._fungsi("set_password")
		self.assertEqual(fungsi.decorator_list, [], "set_password tidak boleh punya dekorator")

	def test_check_memanggil_matches(self):
		"""Endpoint tidak boleh punya salinan logikanya sendiri: dua tempat yang
		memutuskan hal yang sama akan berbeda suatu hari."""
		dipanggil = {
			s.func.id
			for s in ast.walk(self._fungsi("check"))
			if isinstance(s, ast.Call) and isinstance(s.func, ast.Name)
		}
		self.assertIn("matches", dipanggil)


if __name__ == "__main__":
	unittest.main()
