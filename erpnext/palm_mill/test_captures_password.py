# Copyright (c) 2026, AutoERP and Contributors
# See license.txt

"""The password that unlocks `captures.smagri.id`, and the endpoint the gate asks.

`captures.smagri.id` serves the grading photos straight out of Cloudflare R2, with
no login at all: plate number, supplier, tonnage and every capture of every truck,
to anyone holding the link. A Cloudflare Worker now sits in front of it and asks
for a password; this module is where that password is set and checked.

**The Worker never holds the password.** It posts a candidate here and gets back
`{"ok": true}` or `{"ok": false}` -- nothing else, ever. One source of truth, and
no copy of the secret sitting in Cloudflare's config where a second person can
read it and the two can drift apart.

Three things are asserted here, and each one has been a real breach somewhere:

1. **The answer is a boolean, never the password.** An endpoint that echoes back
   what it compared against is an endpoint that hands the secret to whoever asks
   with the wrong password first.
2. **The comparison is constant-time.** `==` on a secret returns sooner the earlier
   it differs, and that difference is measurable over a network. `compare_digest`
   is what the codebase already uses for this and it is what has to be used here.
3. **A krani can neither read nor change it.** `Weighbridge Operator` has access to
   Palm Mill Settings -- deliberately, they need the deduction rules. Two separate
   things keep the password out of their hands, and it is worth being exact about
   which does what, because they fail differently:

   - The `Password` **fieldtype** is what hides the value. It stores the secret in
     `__Auth`, not in the Settings column, and every read path hands back
     `**************`. Measured: dropping the permlevel changes nothing here.
   - `permlevel 1` is what stops them **writing** it. Without it a krani could
     overwrite the password and lock everyone else out of the photos.

   Both are pinned below, by calling the paths rather than by reading the schema.

The gate is also the *whole* lock: blank password means every request is refused,
not that the door stands open. A site that has not set one yet is a site whose
photos are not reachable, which is the safe direction to fail.
"""

import ast
from pathlib import Path

import frappe
from frappe.tests import IntegrationTestCase

from erpnext.palm_mill import captures_password
from erpnext.palm_mill.captures_password import FIELD, SETTINGS, check, set_password

PERMLEVEL_RAHASIA = 1
SETTINGS_DOCTYPE = SETTINGS


def _settings_json() -> dict:
	import json

	path = (
		Path(frappe.get_app_path("erpnext"))
		/ "palm_mill"
		/ "doctype"
		/ "palm_mill_settings"
		/ "palm_mill_settings.json"
	)
	return json.loads(path.read_text(encoding="utf-8"))


def _field(fieldname: str) -> dict:
	for f in _settings_json()["fields"]:
		if f["fieldname"] == fieldname:
			return f
	raise AssertionError(f"field {fieldname} tidak ada di Palm Mill Settings")


class IntegrationTestCapturesPassword(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		set_password("")

	def tearDown(self):
		frappe.set_user("Administrator")
		set_password("")

	# ------------------------------------------------------------ bentuk field

	def test_field_ada_dan_bertipe_password(self):
		"""`Data` would print the password in plain text on the form and in the
		database. `Password` stores it encrypted and renders as dots."""
		self.assertEqual(_field(FIELD)["fieldtype"], "Password")

	def test_field_ada_di_field_order(self):
		# A field missing from field_order exists in the table but never appears on
		# the form -- the admin has nowhere to type it.
		self.assertIn(FIELD, _settings_json()["field_order"])

	def test_field_dikunci_permlevel_satu(self):
		"""Yang ditahan permlevel adalah MENULIS, bukan membaca -- membacanya sudah
		ditahan fieldtype `Password`. Tanpa permlevel, krani bisa menimpa sandinya
		dan mengunci semua orang lain di luar."""
		self.assertEqual(_field(FIELD).get("permlevel"), PERMLEVEL_RAHASIA)

	def test_hanya_system_manager_yang_punya_permlevel_satu(self):
		"""Permlevel hanya berlaku kalau ADA baris permission di level itu, dan
		baris itu cuma untuk System Manager (= profil Admin Pabrik)."""
		perms = _settings_json()["permissions"]
		level_satu = [p for p in perms if p.get("permlevel") == PERMLEVEL_RAHASIA]
		self.assertEqual([p["role"] for p in level_satu], ["System Manager"])

	def test_weighbridge_operator_tidak_punya_permlevel_satu(self):
		perms = _settings_json()["permissions"]
		krani = [p for p in perms if p["role"] == "Weighbridge Operator"]
		self.assertTrue(krani, "baris Weighbridge Operator hilang dari Settings")
		for p in krani:
			self.assertNotEqual(p.get("permlevel"), PERMLEVEL_RAHASIA)

	# --------------------------------------------- krani benar-benar tidak bisa baca

	# The tests above read the schema; these call the paths a person actually has.
	# Measured 2026-09-24: with the permlevel removed these still pass, because the
	# `Password` fieldtype masks the value on its own. That is the point of having
	# both -- the schema tests pin the intent, these pin the effect, and knowing
	# which one protects what is the difference between a real lock and a believed
	# one. The permlevel earns its place on the WRITE test below.

	def _krani(self) -> str:
		email = "krani-uji@contoh.test"
		if not frappe.db.exists("User", email):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": "Krani Uji",
					"send_welcome_email": 0,
					"roles": [{"role": "Weighbridge Operator"}],
				}
			).insert(ignore_permissions=True)
		return email

	def test_krani_tidak_melihat_sandi_lewat_form(self):
		"""`frappe.client.get` adalah yang dipakai Desk dan REST. Kalau sandinya
		lolos di sini, ia lolos ke layar mana pun yang bisa dibuka krani."""
		from frappe.client import get as client_get

		set_password("rahasia-pabrik")
		frappe.set_user(self._krani())
		nilai = client_get(SETTINGS_DOCTYPE).get(FIELD)
		self.assertNotEqual(nilai, "rahasia-pabrik")
		self.assertIn(nilai, (None, "", "**************"))

	def test_krani_tidak_melihat_sandi_lewat_get_value(self):
		from frappe.client import get_value as client_get_value

		set_password("rahasia-pabrik")
		frappe.set_user(self._krani())
		nilai = (client_get_value(SETTINGS_DOCTYPE, FIELD) or {}).get(FIELD)
		self.assertNotEqual(nilai, "rahasia-pabrik")

	def test_krani_tidak_bisa_menimpa_sandinya(self):
		"""Inilah yang benar-benar dikerjakan permlevel -- dan cara ia mengerjakannya
		tidak seperti yang disangka.

		Frappe **tidak melempar** untuk field di atas permlevel: ia MEMBUANG field itu
		dari perubahan dan menyimpan sisanya, tanpa galat. `set_value` menjawab sukses
		dan sandinya tidak berubah. Jadi yang diperiksa di sini nilainya sesudahnya,
		bukan ada-tidaknya exception -- menunggu exception akan membuat tes ini hijau
		bahkan ketika permlevel-nya dicabut.

		Izin tulis tingkat dokumen sengaja DIBERIKAN dulu. Tanpa itu krani ditolak
		lebih awal oleh `write: 0` di barisnya sendiri, permlevel tidak pernah
		ditanya, dan tes ini lulus karena alasan yang salah -- terukur 2026-09-24.
		"""
		from frappe.client import set_value

		set_password("rahasia-pabrik")
		baris = frappe.db.get_value(
			"DocPerm",
			{"parent": SETTINGS_DOCTYPE, "role": "Weighbridge Operator", "permlevel": 0},
			"name",
		)
		self.assertTrue(baris, "baris izin krani hilang dari Palm Mill Settings")
		frappe.db.set_value("DocPerm", baris, "write", 1)
		frappe.clear_cache()
		try:
			frappe.set_user(self._krani())
			self.assertTrue(
				frappe.has_permission(SETTINGS_DOCTYPE, "write"),
				"prasyarat tes gagal: krani belum punya izin tulis tingkat dokumen",
			)
			set_value(SETTINGS_DOCTYPE, SETTINGS_DOCTYPE, FIELD, "dibajak")
		finally:
			frappe.set_user("Administrator")
			frappe.db.set_value("DocPerm", baris, "write", 0)
			frappe.clear_cache()

		# Sandinya tidak berubah: yang lama masih membuka, yang dipaksakan tidak.
		self.assertEqual(check("rahasia-pabrik"), {"ok": True})
		self.assertEqual(check("dibajak"), {"ok": False})

	def test_kolom_database_tidak_memuat_sandinya(self):
		"""Fieldtype `Password` menyimpan sandinya di tabel `__Auth`, bukan di kolom
		Settings. Kalau ini berubah jadi `Data`, sandinya muncul di kolom -- dan ikut
		ke setiap backup, setiap dump, setiap restore."""
		set_password("rahasia-pabrik")
		self.assertNotEqual(frappe.db.get_single_value(SETTINGS_DOCTYPE, FIELD), "rahasia-pabrik")

	def test_dekripsi_tidak_terbuka_lewat_http(self):
		"""`get_decrypted_password` mengembalikan teks polos tanpa memeriksa
		permlevel. Itu aman HANYA selama ia tidak bisa dipanggil dari luar."""
		from frappe.utils.password import get_decrypted_password

		self.assertNotIn(get_decrypted_password, frappe.whitelisted)

	# -------------------------------------------------------------- perbandingan

	def test_sandi_benar_diterima(self):
		set_password("rahasia-pabrik")
		self.assertEqual(check("rahasia-pabrik"), {"ok": True})

	def test_sandi_salah_ditolak(self):
		set_password("rahasia-pabrik")
		self.assertEqual(check("rahasia-salah"), {"ok": False})

	def test_sandi_beda_panjang_ditolak(self):
		# `compare_digest` menolak panjang berbeda tanpa membocorkan panjangnya.
		set_password("rahasia-pabrik")
		self.assertEqual(check("r"), {"ok": False})

	def test_jawaban_tidak_pernah_memuat_sandinya(self):
		"""Kunci: apa pun yang dikembalikan, sandinya tidak boleh ikut. Endpoint
		yang menggemakan pembandingnya adalah endpoint yang membagikan sandi."""
		set_password("rahasia-pabrik")
		for kandidat in ("rahasia-pabrik", "salah", ""):
			hasil = check(kandidat)
			self.assertNotIn("rahasia-pabrik", str(hasil))
			self.assertEqual(set(hasil), {"ok"})

	def test_beda_huruf_besar_kecil_ditolak(self):
		set_password("Rahasia")
		self.assertEqual(check("rahasia"), {"ok": False})

	def test_spasi_di_ujung_tidak_dipangkas(self):
		"""Kalau dipangkas, dua sandi berbeda jadi sandi yang sama -- dan admin
		yang sengaja menaruh spasi tidak pernah tahu."""
		set_password("rahasia ")
		self.assertEqual(check("rahasia"), {"ok": False})
		self.assertEqual(check("rahasia "), {"ok": True})

	# ------------------------------------------------------- pintu terkunci rapat

	# Blank password = the lock is not configured yet. Failing *closed* is the only
	# safe reading: failing open would turn "admin has not got round to it" into
	# "the photos are public again", which is exactly the state being fixed.
	def test_sandi_kosong_menolak_semua(self):
		set_password("")
		for kandidat in ("", "apa saja", "rahasia-pabrik"):
			self.assertEqual(check(kandidat), {"ok": False})

	def test_kandidat_kosong_ditolak_walau_sandi_terpasang(self):
		set_password("rahasia-pabrik")
		self.assertEqual(check(""), {"ok": False})

	def test_kandidat_none_ditolak(self):
		# Worker mengirim JSON; field yang hilang sampai ke sini sebagai None,
		# bukan string. Itu tidak boleh jadi TypeError -- dan tidak boleh lolos.
		set_password("rahasia-pabrik")
		self.assertEqual(check(None), {"ok": False})

	def test_kandidat_bukan_string_ditolak(self):
		set_password("rahasia-pabrik")
		for kandidat in (123, True, [], {}):
			self.assertEqual(check(kandidat), {"ok": False})

	# ---------------------------------------------------------- baca sumbernya

	def test_memakai_compare_digest_bukan_sama_dengan(self):
		"""Dibaca dari sumbernya, bukan diukur waktunya: mengukur waktu di CI
		berisik dan lolos-gagal acak. Yang dipastikan: `compare_digest` dipanggil."""
		pohon = ast.parse(Path(captures_password.__file__).read_text(encoding="utf-8"))
		nama = {
			n.attr if isinstance(n, ast.Attribute) else n.id
			for n in ast.walk(pohon)
			if isinstance(n, ast.Attribute | ast.Name)
		}
		self.assertIn("compare_digest", nama)

	def test_endpoint_terdaftar_sebagai_whitelist(self):
		"""Frappe mencatatnya di himpunan modul, bukan sebagai atribut fungsi --
		jadi yang diperiksa registry-nya, bukan tiruannya."""
		self.assertIn(check, frappe.whitelisted)

	def test_endpoint_dibuka_untuk_tamu(self):
		"""Worker Cloudflare tidak punya akun Frappe. Tanpa `allow_guest` gerbang
		selalu 403 dan tak seorang pun bisa membuka foto."""
		self.assertIn(check, frappe.guest_methods)

	def test_endpoint_hanya_menerima_post(self):
		"""GET menaruh sandi di URL, dan URL masuk ke log akses, riwayat browser,
		dan header Referer. POST menaruhnya di body."""
		self.assertEqual(frappe.allowed_http_methods_for_whitelisted_func[check], ["POST"])

	def test_endpoint_dibatasi_lajunya(self):
		"""Sandi tunggal + tanpa batas laju = tebak sampai ketemu. Frappe
		menyimpan hitungannya di Redis, jadi ini nyata, bukan hiasan."""
		sumber = Path(captures_password.__file__).read_text(encoding="utf-8")
		self.assertIn("rate_limit", sumber)

	def test_set_password_bukan_endpoint(self):
		"""Menyetel sandi dilakukan dari form Settings, yang sudah dijaga
		permlevel. Membukanya sebagai endpoint menambah pintu kedua yang harus
		dijaga sendiri -- dan itu pintu yang MENULIS."""
		self.assertFalse(hasattr(set_password, "__dict__") and set_password.__dict__.get("allow_guest"))
		self.assertNotIn(
			"captures_password.set_password",
			(frappe.get_hooks("override_whitelisted_methods") or {}),
		)
