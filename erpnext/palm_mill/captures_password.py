# Copyright (c) 2026, AutoERP and contributors
# For license information, please see license.txt

"""The one password that unlocks `captures.smagri.id`, and the check the gate asks.

`captures.smagri.id` serves the grading photos straight out of Cloudflare R2. Until
now it served them to *anyone holding the link* -- plate number, supplier, tonnage
and every capture of every truck, no login at all (R1, open since 2026-09-20). A
Cloudflare Worker now stands in front of that bucket and asks for a password. This
module is where the password is set, and where the Worker comes to ask.

**The Worker never holds the password.** It posts a candidate to `check` and gets
back `{"ok": true}` or `{"ok": false}`. Nothing else crosses, ever. That is what
makes AutoERP the single source of truth: the admin changes it in one place and the
gate follows, with no second copy in Cloudflare's config for the two to drift apart
from, and no Cloudflare API token sitting on the droplet.

⚠️ **The price of that choice, stated plainly: AutoERP down = photos unopenable.**
Deliberate. The alternative -- caching the answer at the edge -- is a gate that
keeps letting people in after the password has been changed, which is the one
failure a password is bought to prevent.

One password per company, not per person (decision 2026-09-23). The viewers are a
handful of internal staff; the threat being closed is a *leaked link*, not an
insider, and per-person credentials are a half-measure next to Cloudflare Access,
which is what goes in at handover (R1) on top of this.
"""

from hmac import compare_digest

import frappe
from frappe.rate_limiter import rate_limit

#: The field on Palm Mill Settings. Named here so the tests and the Worker-facing
#: docs cannot drift from the schema by a typo.
FIELD = "captures_password"

SETTINGS = "Palm Mill Settings"

#: Guesses per IP per hour. A single shared password with no ceiling is a password
#: that gets found by trying; Frappe counts these in Redis, so the limit is real.
#: Generous enough that a person mistyping twice never notices it.
GUESS_LIMIT = 20
GUESS_WINDOW_SECONDS = 60 * 60


def stored_password() -> str:
	"""The configured password, or `""` when this site has not set one.

	`get_password` is the only way to it. A `Password` field keeps the secret in the
	`__Auth` table; the Settings column itself holds the literal mask
	`**************`, so every ordinary read path -- the form, `frappe.client.get`,
	`get_value`, a database dump -- hands back asterisks and not the password.
	Measured on 2026-09-24, and it is why a leaked backup is not a leaked password.
	"""
	try:
		return frappe.get_cached_doc(SETTINGS).get_password(FIELD, raise_exception=False) or ""
	except Exception:
		# A password that cannot be decrypted (restored site, rotated encryption
		# key) must read as "not set" -- which locks the door, not opens it.
		frappe.log_error(title="captures: sandi tidak terbaca")
		return ""


def set_password(value: str) -> None:
	"""Set or clear the password. Called from the form; deliberately not whitelisted.

	Writing is already guarded where it belongs, by two layers that were measured
	rather than assumed (2026-09-24):

	1. `Weighbridge Operator` has `write: 0` on Palm Mill Settings, so a krani never
	   reaches the field at all.
	2. Should that ever be loosened, the field sits at `permlevel 1` and only
	   `System Manager` -- the role behind the `Admin Pabrik` profile -- holds that
	   level. Frappe then **drops the field from the update and saves the rest
	   without error**, so the attempt reads as success and changes nothing.

	A whitelisted setter would be a third door onto the same secret, one that
	writes, guarded by its own separate code. There is no reason to open it.
	"""
	doc = frappe.get_doc(SETTINGS)
	setattr(doc, FIELD, value or "")
	doc.flags.ignore_mandatory = True
	# `save` clears the document cache itself, so a change made in Desk is seen by
	# the next request in every other worker process -- verified across processes,
	# because a stale cache here would mean a changed password that still lets the
	# old one in, which is the one thing a password change has to deliver.
	doc.save(ignore_permissions=True)


def matches(candidate: object, stored: str) -> bool:
	"""Does `candidate` equal `stored`? The whole decision, and nothing else.

	Split out from `check` on purpose. This function touches no database, no
	session and no request, so it is testable without a site -- which means the
	rules below are pinned by tests that run anywhere, in milliseconds, including
	on a machine that has never had bench installed.

	Every branch here refuses. That is the design: the only path to `True` is a
	non-empty stored password and a candidate that matches it byte for byte.
	"""
	if not stored or not isinstance(candidate, str) or not candidate:
		# `compare_digest` is skipped here on purpose: there is no secret whose
		# timing could leak. Either nothing is configured, or the caller sent
		# something that is not a password -- neither depends on `stored`.
		return False

	# Constant-time. `==` on a string returns at the first differing byte, and that
	# difference is measurable across a network; `compare_digest` does not.
	#
	# Both sides are encoded first. `compare_digest` on `str` raises TypeError for
	# any character above U+00FF, so a password with an emoji or an "ā" in it would
	# turn every check into a 500 -- and only for the sites unlucky enough to have
	# picked one. On `bytes` it compares cleanly whatever was typed.
	return compare_digest(candidate.encode("utf-8"), stored.encode("utf-8"))


# Semgrep menandai SETIAP endpoint tamu untuk ditinjau manusia, dan itu benar --
# ini satu-satunya di `palm_mill`. Yang ditinjau, dan kenapa dibiarkan terbuka:
#
# * Kenapa harus tamu: penanyanya Cloudflare Worker, yang tidak punya akun Frappe.
#   Memberinya akun berarti menaruh kredensial API di tepi jaringan -- persis yang
#   dihindari rancangan ini.
# * Yang bisa dilakukan penyerang: menebak satu sandi, 20 kali per IP per jam.
#   Tidak ada data yang bisa dibaca, tidak ada yang bisa ditulis.
# * Yang TIDAK pernah keluar: jawabannya `{"ok": bool}` dan tidak pernah yang lain
#   -- tidak ada sandi, tidak ada panjangnya, tidak ada pesan galat yang berbeda
#   antara "sandi salah" dan "sandi belum diatur". Dipatok tes di tiga lapis.
# * Bandingnya waktu-tetap (`compare_digest` pada bytes), jadi lamanya jawaban
#   tidak membocorkan berapa huruf yang sudah benar.
# * Menulis TIDAK ikut terbuka: `set_password` sengaja tidak di-whitelist, dan
#   sebuah tes menolak kalau ia pernah jadi endpoint.
#
# Dengan batas laju di baris berikutnya, ini lebih sempit daripada layar login
# Frappe sendiri, yang juga terbuka untuk tamu dan menerima tebakan sandi.
# nosemgrep: frappe-semgrep-rules.rules.security.guest-whitelisted-method
@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=GUESS_LIMIT, seconds=GUESS_WINDOW_SECONDS, methods=["POST"])
def check(password: str | None = None) -> dict:
	"""Is this the password? Answers `{"ok": bool}` and nothing else, ever.

	`allow_guest` because the caller is a Cloudflare Worker, which has no Frappe
	account and cannot be given one without putting API credentials at the edge --
	the very thing this design avoids.

	Returning only a boolean is the whole contract. An endpoint that echoes back
	what it compared against hands the secret to the first caller who guesses
	wrong, and that is a mistake made often enough that a test pins it here.

	Blank stored password means **refuse everything**. A site whose admin has not
	set one yet is a site whose photos are unreachable -- never one whose photos
	are open again, which is the state being fixed.
	"""
	return {"ok": matches(password, stored_password())}
