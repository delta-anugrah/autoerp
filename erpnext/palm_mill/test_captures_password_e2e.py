# Copyright (c) 2026, AutoERP and Contributors
# See license.txt

"""The gate over real HTTP — exactly the request the Cloudflare Worker will send.

The other two files stop short of the wire. `test_captures_password_unit.py` pins
the comparison with no site at all; `test_captures_password.py` calls the Python
function with a session already established. Neither one proves the thing the
Worker actually depends on: that an **unauthenticated POST from the open internet**
reaches this endpoint and comes back with an answer.

That gap is not academic. Between the function and the wire sit request routing,
the whitelist registry, guest handling, the HTTP-method allowlist, CSRF, and JSON
serialisation — and every one of them can refuse a call that works perfectly when
invoked in Python. A gate that 403s every request is indistinguishable, from the
mill's side, from a gate that is simply broken: nobody can open the photos either
way.

So these tests go through `FrappeAPITestCase`, which drives the full WSGI stack
the same way a real request does.

⚠️ **What the Worker must send, pinned here so it cannot drift:**

    POST https://app.smagri.id/api/method/erpnext.palm_mill.captures_password.check
    Content-Type: application/json
    {"password": "<what the viewer typed>"}

    200 {"message": {"ok": true}}    -> show the photos
    200 {"message": {"ok": false}}   -> ask again

Note the envelope: Frappe wraps every whitelisted return value in `message`. A
Worker reading `body.ok` instead of `body.message.ok` gets `undefined`, which is
falsy, which means **nobody can ever get in** — and the endpoint looks healthy the
whole time. `test_bentuk_jawaban_persis_yang_dibaca_worker` is the test that stops
that from shipping.
"""

import json

import frappe
from frappe.tests.test_api import FrappeAPITestCase

from erpnext.palm_mill.captures_password import GUESS_LIMIT, set_password

METHOD = "erpnext.palm_mill.captures_password.check"
SANDI = "rahasia-pabrik-e2e"


class E2ETestCapturesPasswordGate(FrappeAPITestCase):
	"""Satu kelas, satu pertanyaan: apa yang benar-benar terjadi di kabel?"""

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		set_password(SANDI)
		frappe.db.commit()
		self._reset_rate_limit()

	@staticmethod
	def _reset_rate_limit():
		"""Kembalikan jatah tebakan ke nol sebelum tiap tes.

		⚠️ Ini ditambahkan karena berkas ini pernah membuat dirinya sendiri gagal:
		20 tebakan per IP per jam adalah batas yang nyata, dan satu jalanan penuh
		tes menghabiskannya, lalu tujuh tes berikutnya merah dengan 429 — yang
		terbaca persis seperti gerbangnya rusak. Itu sekaligus bukti paling kuat
		bahwa pembatasannya memang hidup di jalur HTTP; `test_batas_tebakan_nyata`
		di bawah menegaskannya dengan sengaja.

		Kuncinya `rl:{cmd}:{ip}:{detik}`. Dihapus dengan pola `*` lewat
		`delete_keys`, bukan `delete_value`: yang terakhir memasang awalan site
		SEKALI LAGI pada kunci yang sudah lengkap, jadi ia menghapus kunci yang
		tidak pernah ada dan diam-diam tidak melakukan apa-apa. Terukur 2026-09-24
		— hitungannya tetap di 62 sesudah "penghapusan" yang dilaporkan berhasil.
		"""
		frappe.cache.delete_keys(f"rl:{METHOD}:")

	def tearDown(self):
		frappe.set_user("Administrator")
		set_password("")
		frappe.db.commit()
		super().tearDown()

	def _post(self, password, **kwargs):
		"""POST tanpa satu pun kredensial — persis seperti Worker."""
		return self.post(self.method(METHOD), {"password": password}, **kwargs)

	# --------------------------------------------------- jalur utama, tanpa login

	def test_tamu_tanpa_login_bisa_menanyakan_sandinya(self):
		"""Yang paling penting dari seluruh berkas ini.

		Worker Cloudflare tidak punya akun Frappe dan tidak boleh diberi satu pun
		kredensial. Kalau permintaan ini 403, gerbangnya menolak semua orang
		selamanya dan tidak ada satu pun foto yang bisa dibuka.
		"""
		jawaban = self._post(SANDI)
		self.assertEqual(jawaban.status_code, 200, jawaban.data[:400])
		self.assertEqual(jawaban.json["message"], {"ok": True})

	def test_sandi_salah_dijawab_200_bukan_401(self):
		"""Sengaja 200 dengan `ok: false`, bukan 401/403.

		Gerbangnya adalah Worker, bukan Frappe: Worker yang memutuskan mau
		menampilkan layar sandi lagi. Menjawab 4xx membuat Worker harus menebak
		mana "sandi salah" dan mana "ERP-nya rusak" — dua hal yang butuh perlakuan
		sangat berbeda.
		"""
		jawaban = self._post("salah-sekali")
		self.assertEqual(jawaban.status_code, 200, jawaban.data[:400])
		self.assertEqual(jawaban.json["message"], {"ok": False})

	def test_bentuk_jawaban_persis_yang_dibaca_worker(self):
		"""Kontrak lintas-sistem. Worker membaca `body.message.ok`.

		Frappe membungkus nilai balik dalam `message`. Worker yang membaca `body.ok`
		mendapat `undefined` -> falsy -> tidak ada yang pernah bisa masuk, sementara
		endpoint-nya terlihat sehat sepenuhnya. Ditulis lengkap di sini supaya
		perubahan bentuk jawaban gagal DI SINI, bukan di pabrik.
		"""
		body = json.loads(self._post(SANDI).data)
		self.assertIsInstance(body, dict)
		self.assertIn("message", body)
		self.assertEqual(body["message"], {"ok": True})
		self.assertIsInstance(body["message"]["ok"], bool)

	def test_jawaban_tidak_pernah_memuat_sandinya(self):
		"""Diperiksa pada BYTE MENTAH, bukan pada dict yang sudah di-parse.

		Sandinya bisa bocor lewat jalan yang tidak terlihat di `json`: pesan galat,
		jejak tumpukan, header `X-Frappe-*`, atau log server yang ikut terkirim.
		Yang diperiksa di sini seluruh badan jawaban apa adanya.
		"""
		for kandidat in (SANDI, "salah", ""):
			jawaban = self._post(kandidat)
			self.assertNotIn(SANDI.encode(), jawaban.data)
			self.assertNotIn(SANDI.encode(), json.dumps(dict(jawaban.headers)).encode())

	# ------------------------------------------------------------ pintu tertutup

	def test_sandi_kosong_di_site_menolak_semua(self):
		"""Site yang adminnya belum mengisi = foto tidak bisa dibuka, bukan terbuka."""
		frappe.set_user("Administrator")
		set_password("")
		frappe.db.commit()
		for kandidat in ("", "apa saja", SANDI):
			jawaban = self._post(kandidat)
			self.assertEqual(jawaban.status_code, 200, jawaban.data[:200])
			self.assertEqual(jawaban.json["message"], {"ok": False}, f"{kandidat!r} lolos")

	def test_tanpa_field_password_ditolak_bukan_500(self):
		"""Worker yang salah kirim harus dapat jawaban, bukan galat server.

		500 di sini akan terbaca sebagai "ERP mati" oleh Worker, dan membuat orang
		mengejar masalah yang tidak ada.
		"""
		jawaban = self.post(self.method(METHOD), {})
		self.assertEqual(jawaban.status_code, 200, jawaban.data[:400])
		self.assertEqual(jawaban.json["message"], {"ok": False})

	def test_password_bukan_string_ditolak_dan_tidak_pernah_meloloskan(self):
		"""Di kabel, yang menolak DULUAN bukan kode ini.

		Terukur 2026-09-24, dan hanya terlihat dari lapisan E2E: annotasi
		`password: str | None` membuat `validate_argument_types` milik Frappe
		menolak tipe yang salah dengan **417 FrappeTypeError**, sebelum `check`
		sempat dipanggil. Dua lapis tes yang lain memanggil fungsinya langsung, jadi
		keduanya melewati penjaga itu tanpa pernah melihatnya.

		Dicatat begini, bukan "dipaksa jadi 200", karena 417 memang jawaban yang
		benar: Worker kita selalu mengirim string, jadi tipe yang salah berarti
		Worker-nya yang rusak — dan itu harus berisik, bukan diam-diam dijawab
		"sandi salah" sehingga orang mengejar sandi yang sebenarnya benar.

		Yang WAJIB, apa pun kodenya: tidak satu pun dari ini boleh terbaca sebagai
		izin masuk.
		"""
		for kandidat in (123, True, [], {"a": 1}):
			jawaban = self._post(kandidat)
			self.assertNotEqual(jawaban.status_code, 500, f"{kandidat!r}: {jawaban.data[:200]}")
			terbuka = jawaban.status_code == 200 and jawaban.json.get("message") == {"ok": True}
			self.assertFalse(terbuka, f"{kandidat!r} MELOLOSKAN gerbang")

	def test_password_null_dijawab_bukan_dibuang(self):
		"""`None` lolos dari penjaga tipe (annotasinya `str | None`) dan sampai ke
		kode ini, jadi jawabannya harus rapi: 200 `ok: false`, bukan galat."""
		jawaban = self._post(None)
		self.assertEqual(jawaban.status_code, 200, jawaban.data[:400])
		self.assertEqual(jawaban.json["message"], {"ok": False})

	def test_sandi_non_ascii_tidak_meledak_di_kabel(self):
		"""Bug nyata yang diperbaiki 2026-09-24: `compare_digest` pada `str`
		melempar TypeError untuk karakter di atas U+00FF, dan di jalur HTTP itu
		muncul sebagai 500 — hanya di site yang sandinya kebetulan beraksen."""
		for sandi in ("rahasia🌴", "sandi-ā", "Ñoño"):
			frappe.set_user("Administrator")
			set_password(sandi)
			frappe.db.commit()
			benar = self._post(sandi)
			self.assertEqual(benar.status_code, 200, f"{sandi!r}: {benar.data[:200]}")
			self.assertEqual(benar.json["message"], {"ok": True}, f"{sandi!r} gagal cocok")
			self.assertEqual(self._post("salah").json["message"], {"ok": False})

	# ------------------------------------------------------------- batas tebakan

	def test_batas_tebakan_nyata_di_jalur_http(self):
		"""Satu sandi bersama tanpa langit-langit adalah sandi yang ketemu dengan
		dicoba. Di sini dibuktikan langit-langitnya benar-benar turun di kabel.

		Bukan hiasan: berkas ini pernah membuat dirinya sendiri merah karena batas
		ini, sebelum `_reset_rate_limit` ada. Yang diperiksa: tebakan ke-(N+1)
		ditolak 429, dan ditolaknya BUKAN dengan `ok: true`.
		"""
		self._reset_rate_limit()
		for ke in range(GUESS_LIMIT):
			jawaban = self._post("salah")
			self.assertEqual(jawaban.status_code, 200, f"tebakan ke-{ke + 1} sudah ditolak")

		lewat = self._post("salah")
		self.assertEqual(lewat.status_code, 429, lewat.data[:200])

	def test_batas_tebakan_juga_menahan_sandi_yang_benar(self):
		"""Sesudah jatahnya habis, sandi yang BENAR pun ditolak.

		Inilah yang membuat batas ini berguna: penebak tidak bisa memakai jawaban
		"benar" sebagai jalan keluar dari pembatasan. Harganya nyata dan disengaja
		— orang yang salah ketik dua puluh kali harus menunggu satu jam.
		"""
		self._reset_rate_limit()
		for _ in range(GUESS_LIMIT):
			self._post("salah")

		jawaban = self._post(SANDI)
		self.assertEqual(jawaban.status_code, 429, jawaban.data[:200])
		self.assertNotIn(b'"ok": true', jawaban.data)
		self.assertNotIn(b'"ok":true', jawaban.data)

	# ------------------------------------------------------- metode dan penulisan

	def test_get_ditolak(self):
		"""GET menaruh sandi di URL, dan URL masuk ke log akses, riwayat peramban,
		dan header `Referer` situs berikutnya. Hanya POST yang diterima."""
		jawaban = self.get(self.method(METHOD), {"password": SANDI})
		self.assertNotEqual(jawaban.status_code, 200, jawaban.data[:200])

	def test_tamu_tidak_bisa_menyetel_sandinya_lewat_http(self):
		"""Membaca boleh tanpa login; menulis tidak pernah.

		`set_password` sengaja tidak di-whitelist. Kalau suatu saat ia ikut terbuka,
		siapa pun di internet bisa mengganti sandi foto seluruh pabrik.
		"""
		jawaban = self.post(
			self.method("erpnext.palm_mill.captures_password.set_password"),
			{"value": "dibajak"},
		)
		self.assertNotEqual(jawaban.status_code, 200, jawaban.data[:200])

		# Dan sandinya memang tidak berubah.
		frappe.set_user("Administrator")
		self.assertEqual(self._post(SANDI).json["message"], {"ok": True})

	def test_tamu_tidak_bisa_membaca_sandinya_lewat_api_dokumen(self):
		"""Jalur samping: ambil saja Palm Mill Settings lewat REST. Harus ditolak,
		dan kalaupun terjawab, tidak boleh memuat sandinya."""
		jawaban = self.get(self.resource("Palm Mill Settings", "Palm Mill Settings"))
		self.assertNotIn(SANDI.encode(), jawaban.data)
