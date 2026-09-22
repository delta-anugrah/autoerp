# Copyright (c) 2026, AutoERP and Contributors
# See license.txt

"""Proves a token signed here is one AutoGrade will actually accept.

The two apps run on different machines and neither can import the other, so the
payload contract is written out in full below rather than imported. If a field is
renamed on either side, `test_payload_matches_autograde_contract` fails loudly -
which is the only thing standing between a rename and a mill that silently refuses
every token it is handed.

Verification here is deliberately *independent* of `license.sign`: the checks below
decode the JWS by hand and verify with the public half, the same way
`autograde/src/palmgrade/license/manager.py` does. Calling the signing code to check
the signing code would prove nothing.
"""

import json
from base64 import urlsafe_b64decode
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import frappe
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
	Encoding,
	NoEncryption,
	PrivateFormat,
	PublicFormat,
)
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, get_system_timezone, getdate, nowdate

from erpnext.palm_mill import license as licence_module
from erpnext.palm_mill.license import (
	CONF_KEY_ID,
	CONF_PRIVATE_KEY,
	SECONDS_PER_DAY,
	build_payload,
	end_of_day_epoch,
	issue,
	sign,
)
from erpnext.palm_mill.test_fixtures import COMPANY, setup_palm_mill

# Copied from AutoGrade `src/palmgrade/license/types.py` (class LicensePayload).
# Written out rather than imported: see the module docstring.
AUTOGRADE_PAYLOAD_FIELDS = {
	"company_id",
	"company_name",
	"status",
	"nbf",
	"iat",
	"exp",
	"license_expires_at",
	"warning_days_before_expiry",
	"grace_days_after_expiry",
	"server_time",
	"nonce",
	"kid",
}

# AutoGrade's `_verify_jws` rejects anything whose header disagrees with this shape.
AUTOGRADE_JWS_HEADER_ALG = "EdDSA"


def _b64url_decode(segment: str) -> bytes:
	"""Pad back to a multiple of four, as AutoGrade's `_b64url_decode` does."""
	return urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


def decode_unverified(token: str) -> tuple[dict, dict]:
	header_b64, payload_b64, _ = token.split(".")
	return json.loads(_b64url_decode(header_b64)), json.loads(_b64url_decode(payload_b64))


def verify_like_autograde(token: str, public_pem: bytes) -> dict:
	"""Verify exactly the way the mill does, and raise the way the mill does."""
	from cryptography.hazmat.primitives.serialization import load_pem_public_key

	header_b64, payload_b64, sig_b64 = token.split(".")
	key = load_pem_public_key(public_pem)
	key.verify(_b64url_decode(sig_b64), f"{header_b64}.{payload_b64}".encode())

	header = json.loads(_b64url_decode(header_b64))
	payload = json.loads(_b64url_decode(payload_b64))
	if payload["kid"] != header.get("kid"):
		raise ValueError("kid mismatch")
	return payload


class IntegrationTestLicence(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		setup_palm_mill()

		# A throwaway key pair. The production private key exists only in
		# site_config.json on our own site and must never reach a test, a fixture or
		# this repo.
		cls.private_key = Ed25519PrivateKey.generate()
		cls.private_pem = cls.private_key.private_bytes(
			Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
		).decode()
		cls.public_pem = cls.private_key.public_key().public_bytes(
			Encoding.PEM, PublicFormat.SubjectPublicKeyInfo
		)

	def setUp(self):
		super().setUp()
		# Stored the way site_config.json really holds it: one line, literal \n.
		frappe.conf[CONF_PRIVATE_KEY] = self.private_pem.replace("\n", "\\n")
		frappe.conf[CONF_KEY_ID] = "v1"
		self.addCleanup(frappe.conf.pop, CONF_PRIVATE_KEY, None)
		self.addCleanup(frappe.conf.pop, CONF_KEY_ID, None)
		# Registered FIRST so it runs LAST: cleanups unwind in reverse, and the row
		# deletions queued after this one need Administrator to be back.
		self.addCleanup(frappe.set_user, "Administrator")

	def make_licence(self, **overrides):
		doc = frappe.get_doc(
			{
				"doctype": "AutoGrade Licence",
				"company": COMPANY,
				"license_expires_on": add_days(nowdate(), 180),
				"grace_days": 60,
				"warning_days": 30,
				"status": "ACTIVE",
				**overrides,
			}
		).insert(ignore_permissions=True)
		# `ignore_permissions`: a test that switched to a System Manager to prove they
		# cannot issue would otherwise fail in teardown rather than in the assertion.
		self.addCleanup(
			lambda: frappe.delete_doc("AutoGrade Licence", doc.name, force=True, ignore_permissions=True)
		)
		return doc

	# ---------------------------------------------------------------- contract

	def test_payload_matches_autograde_contract(self):
		"""Exactly the twelve fields the mill reads - no more, no fewer.

		An extra field is as bad as a missing one: AutoGrade builds its dataclass by
		naming each key, so a field we add here and forget there is dead weight that
		reads like it is doing something.
		"""
		payload = build_payload(
			company=COMPANY,
			license_expires_on=add_days(nowdate(), 30),
			grace_days=60,
			warning_days=30,
			status="ACTIVE",
			kid="v1",
			now=int(datetime.now().timestamp()),
		)
		self.assertEqual(set(payload), AUTOGRADE_PAYLOAD_FIELDS)

	def test_token_verifies_with_the_public_half(self):
		doc = self.make_licence()
		result = issue(doc.name)

		payload = verify_like_autograde(result["token"], self.public_pem)
		self.assertEqual(payload["company_id"], COMPANY)
		self.assertEqual(payload["company_name"], COMPANY)
		self.assertEqual(payload["status"], "ACTIVE")

	def test_header_is_the_shape_autograde_expects(self):
		doc = self.make_licence()
		header, payload = decode_unverified(issue(doc.name)["token"])

		self.assertEqual(header["alg"], AUTOGRADE_JWS_HEADER_ALG)
		self.assertEqual(header["typ"], "JWT")
		# The mill raises "kid mismatch" if these two disagree.
		self.assertEqual(header["kid"], payload["kid"])

	def test_tampered_payload_fails_verification(self):
		"""The whole point of signing. If this passes, anyone can mint a licence."""
		doc = self.make_licence()
		header_b64, payload_b64, sig_b64 = issue(doc.name)["token"].split(".")

		payload = json.loads(_b64url_decode(payload_b64))
		payload["exp"] += 10 * 365 * SECONDS_PER_DAY
		from base64 import urlsafe_b64encode

		forged = urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).rstrip(b"=").decode()

		with self.assertRaises(InvalidSignature):
			verify_like_autograde(f"{header_b64}.{forged}.{sig_b64}", self.public_pem)

	# ------------------------------------------------------------------ dates

	def test_expiry_is_end_of_day_in_mill_time(self):
		"""Not UTC. Computing this in UTC kills the mill seven hours early."""
		date = getdate(add_days(nowdate(), 10))
		epoch = end_of_day_epoch(date)

		local = datetime.fromtimestamp(epoch, ZoneInfo(get_system_timezone()))
		self.assertEqual(local.date(), date)
		self.assertEqual((local.hour, local.minute, local.second), (23, 59, 59))

	def test_grace_is_added_on_top_of_expiry(self):
		doc = self.make_licence(license_expires_on=add_days(nowdate(), 30), grace_days=60)
		result = issue(doc.name)

		self.assertEqual(result["exp"] - result["license_expires_at"], 60 * SECONDS_PER_DAY)

	def test_zero_grace_ends_at_expiry(self):
		doc = self.make_licence(grace_days=0)
		result = issue(doc.name)

		self.assertEqual(result["exp"], result["license_expires_at"])

	def test_backdated_licence_is_marked_expired(self):
		"""A token minted past its own grace says so, rather than being refused."""
		doc = self.make_licence(license_expires_on=add_days(nowdate(), -90), grace_days=0)
		_, payload = decode_unverified(issue(doc.name)["token"])

		self.assertEqual(payload["status"], "EXPIRED")

	def test_cancel_survives_into_the_token(self):
		"""CANCEL must not be rewritten to ACTIVE by the date arithmetic."""
		doc = self.make_licence(status="CANCEL")
		_, payload = decode_unverified(issue(doc.name)["token"])

		self.assertEqual(payload["status"], "CANCEL")

	def test_warning_and_grace_days_reach_the_token(self):
		"""The mill cannot be told later that these changed - they ride along."""
		doc = self.make_licence(grace_days=14, warning_days=7)
		_, payload = decode_unverified(issue(doc.name)["token"])

		self.assertEqual(payload["grace_days_after_expiry"], 14)
		self.assertEqual(payload["warning_days_before_expiry"], 7)

	# ------------------------------------------------------------------ guards

	def test_only_administrator_may_issue(self):
		"""Not a role. Roles are grantable inside Desk, so a customer's own System
		Manager could otherwise extend their subscription for free, forever."""
		doc = self.make_licence()
		user = self._make_system_manager()

		frappe.set_user(user)
		with self.assertRaises(frappe.PermissionError):
			issue(doc.name)

	def test_site_without_a_key_refuses_to_issue(self):
		"""The normal state of a customer site and of demo.smagri.id."""
		doc = self.make_licence()
		frappe.conf.pop(CONF_PRIVATE_KEY, None)

		with self.assertRaises(frappe.ValidationError):
			issue(doc.name)

	def test_unreadable_key_refuses_to_issue(self):
		doc = self.make_licence()
		frappe.conf[CONF_PRIVATE_KEY] = "-----BEGIN PRIVATE KEY-----\\nnonsense\\n-----END PRIVATE KEY-----"

		with self.assertRaises(frappe.ValidationError):
			issue(doc.name)

	def test_non_ed25519_key_refuses_to_issue(self):
		"""An RSA key would sign happily and produce a token no mill can read."""
		from cryptography.hazmat.primitives.asymmetric import rsa

		rsa_pem = (
			rsa.generate_private_key(public_exponent=65537, key_size=2048)
			.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
			.decode()
		)
		doc = self.make_licence()
		frappe.conf[CONF_PRIVATE_KEY] = rsa_pem.replace("\n", "\\n")

		with self.assertRaises(frappe.ValidationError):
			issue(doc.name)

	def test_reissue_on_the_same_row_is_refused(self):
		"""Keeps the ledger honest: one row, one token, one set of terms."""
		doc = self.make_licence()
		issue(doc.name)

		with self.assertRaises(frappe.ValidationError):
			issue(doc.name)

	def test_terms_freeze_once_issued(self):
		doc = self.make_licence()
		issue(doc.name)

		doc.reload()
		doc.license_expires_on = add_days(nowdate(), 3650)
		with self.assertRaises(frappe.ValidationError):
			doc.save(ignore_permissions=True)

	def test_terms_are_editable_before_issuing(self):
		doc = self.make_licence()
		doc.license_expires_on = add_days(nowdate(), 90)
		doc.save(ignore_permissions=True)

		self.assertEqual(getdate(doc.license_expires_on), getdate(add_days(nowdate(), 90)))

	def test_issued_row_records_who_and_when(self):
		doc = self.make_licence()
		issue(doc.name)
		doc.reload()

		self.assertEqual(doc.issued_by, "Administrator")
		self.assertTrue(doc.issued_at)
		self.assertEqual(doc.kid, "v1")
		self.assertTrue(doc.nonce)

	def test_each_token_gets_a_fresh_nonce(self):
		"""Two identical subscriptions must not produce the same bytes."""
		first = issue(self.make_licence().name)["token"]
		second = issue(self.make_licence().name)["token"]

		self.assertNotEqual(first, second)

	def test_baris_bisa_dibuat_lewat_desk(self):
		"""Tanpa izin `create` pada satu pun role, Frappe menyembunyikan tombol
		tambah — untuk SEMUA orang, Administrator sekalian, karena tombol itu
		digambar dari izin role dan bukan dari siapa yang sedang masuk.

		Akibatnya DocType-nya ada, menunya ada, dan tidak ada cara membuat baris
		dari layar sama sekali. Terjadi sungguhan di produksi 2026-09-22.
		"""
		user = self._make_system_manager()
		frappe.set_user(user)

		self.assertTrue(frappe.has_permission("AutoGrade Licence", "create"))
		self.assertTrue(frappe.has_permission("AutoGrade Licence", "read"))

	def test_membuat_baris_dan_menerbitkan_token_dipisah(self):
		"""Boleh membuat baris bukan berarti boleh mencetak token.

		Barisnya cuma niat: Company dan tanggal, belum ada tanda tangan. Yang
		bernilai uang adalah tandatangannya, dan itu tetap Administrator saja —
		role bisa diberikan dari dalam Desk, jadi memagari penerbitan dengan role
		berarti System Manager pelanggan bisa memperpanjang langganannya sendiri.
		"""
		doc = self.make_licence()
		user = self._make_system_manager()
		frappe.set_user(user)

		self.assertTrue(frappe.has_permission("AutoGrade Licence", "create"))
		with self.assertRaises(frappe.PermissionError):
			issue(doc.name)

	# ----------------------------------------------------------------- helpers

	def _make_system_manager(self) -> str:
		email = "licence-tester@example.com"
		if not frappe.db.exists("User", email):
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": "Licence",
					"send_welcome_email": 0,
				}
			).insert(ignore_permissions=True)
			user.add_roles("System Manager")
			self.addCleanup(frappe.delete_doc, "User", email, force=True)
		return email


class UnitTestLicenceSigning(IntegrationTestCase):
	"""Signing arithmetic that needs no database row."""

	def test_one_line_pem_is_restored_before_use(self):
		r"""site_config.json is JSON, so the key is stored with literal \n."""
		key = Ed25519PrivateKey.generate()
		one_line = (
			key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode().replace("\n", "\\n")
		)

		frappe.conf[CONF_PRIVATE_KEY] = one_line
		self.addCleanup(frappe.conf.pop, CONF_PRIVATE_KEY, None)

		self.assertIsInstance(licence_module.private_key(), Ed25519PrivateKey)

	def test_signature_covers_header_and_payload(self):
		"""Swapping in another token's header must break the signature."""
		key = Ed25519PrivateKey.generate()
		public_pem = key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)

		payload = build_payload(
			company="PT A",
			license_expires_on=add_days(nowdate(), 30),
			grace_days=60,
			warning_days=30,
			status="ACTIVE",
			kid="v1",
			now=int(datetime.now().timestamp()),
		)
		token = sign(payload, key, "v1")
		other = sign(payload, key, "v2")

		foreign_header = other.split(".")[0]
		_, body, signature = token.split(".")

		with self.assertRaises(InvalidSignature):
			verify_like_autograde(f"{foreign_header}.{body}.{signature}", public_pem)

	def test_nbf_and_iat_are_not_in_the_future(self):
		"""AutoGrade refuses a token whose nbf has not arrived - a clock skew of a
		few seconds between this server and the mill would lock the mill out."""
		now = int(datetime.now().timestamp())
		payload = build_payload(
			company="PT A",
			license_expires_on=add_days(nowdate(), 30),
			grace_days=60,
			warning_days=30,
			status="ACTIVE",
			kid="v1",
			now=now,
		)

		self.assertEqual(payload["nbf"], now)
		self.assertEqual(payload["iat"], now)
		self.assertEqual(payload["server_time"], now)

	def test_expiry_is_after_issue_for_a_future_date(self):
		now = int((datetime.now() - timedelta(seconds=5)).timestamp())
		payload = build_payload(
			company="PT A",
			license_expires_on=add_days(nowdate(), 1),
			grace_days=0,
			warning_days=30,
			status="ACTIVE",
			kid="v1",
			now=now,
		)

		self.assertGreater(payload["license_expires_at"], payload["iat"])
