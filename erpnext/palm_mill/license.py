# Copyright (c) 2026, AutoERP and contributors
# For license information, please see license.txt

"""Issues the signed subscription tokens that AutoGrade checks at the mill.

This used to live in palmgrade-api, which was switched off on 2026-09-20. Nothing
about the *checking* side moved: AutoGrade still holds the same baked-in public key
and verifies entirely offline. Only the signing moved here.

**The key pair is asymmetric on purpose.** A mill PC is effectively readable by the
customer (the operator is in the `docker` group, which is root in all but name), so
a key that can *open* a token is a key that can *forge* one. The mill holds the
public half and can therefore check but never mint. The private half lives in
`site_config.json` on our own site and nowhere else - not in this repo, not in the
image, not in a fixture, and never on a customer or demo site.

**The payload is a cross-repo contract.** Every field here is read by
`autograde/src/palmgrade/license/types.py`; the two apps run on different machines
and neither can import the other, so `test_license.py` writes the field list out in
full and fails loudly if they drift.
"""

import json
import secrets
from base64 import urlsafe_b64encode
from datetime import datetime, time
from zoneinfo import ZoneInfo

import frappe
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from frappe import _
from frappe.utils import get_system_timezone, getdate

SECONDS_PER_DAY = 86_400

# Matches the `kid` AutoGrade expects in the JWS header. The verifier rejects a
# token whose header `kid` disagrees with the payload `kid`, so this is not
# decoration - it is checked.
DEFAULT_KEY_ID = "v1"

# Site config keys. Absent = this site is not an issuer, which is the normal state
# for a customer site and for demo.smagri.id.
CONF_PRIVATE_KEY = "autograde_license_private_key"
CONF_KEY_ID = "autograde_license_kid"


def _b64url(raw: bytes) -> str:
	"""Base64url with the padding stripped, as JWS requires."""
	return urlsafe_b64encode(raw).rstrip(b"=").decode()


def _pem(raw: str) -> str:
	r"""Turn the stored one-line PEM back into real lines.

	`site_config.json` is JSON, so the key is stored with literal `\n` two-character
	sequences rather than actual newlines. Without this step `load_pem_private_key`
	raises and the failure reads like a corrupt key rather than a formatting one.
	`utils/license.ts` in palmgrade-api did exactly the same for `.env`.
	"""
	return raw.replace("\\n", "\n")


def private_key() -> Ed25519PrivateKey:
	"""The signing key, or a hard stop if this site is not the issuer.

	Refusing loudly matters more than it looks: a silent empty key would let the
	button appear to work on a customer site and hand back an unusable token.
	"""
	raw = (frappe.conf.get(CONF_PRIVATE_KEY) or "").strip()
	if not raw:
		frappe.throw(
			_("This site does not issue AutoGrade licences. The signing key lives only on our own site."),
			title=_("Not a licence issuer"),
		)

	try:
		key = load_pem_private_key(_pem(raw).encode(), password=None)
	except Exception as exc:
		# `str(exc)` rather than the exception object: an exception's own __str__ can
		# carry markup that a translated format string would then render.
		frappe.throw(
			_("The licence signing key could not be read: {0}").format(str(exc)),
			title=_("Broken signing key"),
		)

	if not isinstance(key, Ed25519PrivateKey):
		frappe.throw(_("The licence signing key must be Ed25519."), title=_("Wrong key type"))

	return key


def end_of_day_epoch(date_value) -> int:
	"""Unix seconds for 23:59:59 on that date, in the *site's* timezone.

	Not UTC. Somebody types "30 June" meaning until that day is over at the mill;
	computing it in UTC kills the mill seven hours early. This repo has been bitten
	by exactly that seven-hour offset before.
	"""
	zone = ZoneInfo(get_system_timezone())
	local_end = datetime.combine(getdate(date_value), time(23, 59, 59), tzinfo=zone)
	return int(local_end.timestamp())


def build_payload(
	*,
	company: str,
	license_expires_on,
	grace_days: int,
	warning_days: int,
	status: str,
	kid: str,
	now: int,
) -> dict:
	"""The twelve fields AutoGrade reads. Field names are the contract."""
	license_expires_at = end_of_day_epoch(license_expires_on)
	exp = license_expires_at + grace_days * SECONDS_PER_DAY

	return {
		# Company name doubles as the id: it is what the mill's `.env` already
		# carries as ERP_COMPANY, so one name covers both jobs (decision 2026-09-22).
		"company_id": company,
		"company_name": company,
		# A token minted already past its own grace is marked EXPIRED rather than
		# refused, so that "cancel this mill" is a thing you can actually issue.
		"status": "EXPIRED" if status == "ACTIVE" and now > exp else status,
		"iat": now,
		"nbf": now,
		"license_expires_at": license_expires_at,
		"grace_days_after_expiry": grace_days,
		"warning_days_before_expiry": warning_days,
		"exp": exp,
		"server_time": now,
		"nonce": secrets.token_hex(16),
		"kid": kid,
	}


def sign(payload: dict, key: Ed25519PrivateKey, kid: str) -> str:
	"""Compact JWS, EdDSA. The header `kid` must equal the payload `kid`."""
	header = _b64url(json.dumps({"alg": "EdDSA", "typ": "JWT", "kid": kid}, separators=(",", ":")).encode())
	body = _b64url(json.dumps(payload, separators=(",", ":")).encode())
	signature = _b64url(key.sign(f"{header}.{body}".encode()))
	return f"{header}.{body}.{signature}"


@frappe.whitelist()
def issue(name: str) -> dict:
	"""Sign the token for one AutoGrade Licence row and store it on that row.

	Administrator only, deliberately not a role. Roles are grantable from inside
	Desk, so a customer's own System Manager could otherwise extend their own
	subscription for free, forever. The same reasoning killed the role check in
	palmgrade-api, where every company had its own `admin`.
	"""
	if frappe.session.user != "Administrator":
		frappe.throw(_("Only Administrator may issue licence tokens."), frappe.PermissionError)

	doc = frappe.get_doc("AutoGrade Licence", name)

	if doc.token:
		frappe.throw(
			_("This licence already has a token. Create a new licence row instead of reissuing."),
			title=_("Already issued"),
		)

	kid = (frappe.conf.get(CONF_KEY_ID) or DEFAULT_KEY_ID).strip()
	key = private_key()
	now = frappe.utils.now_datetime().replace(microsecond=0)
	now_epoch = int(now.replace(tzinfo=ZoneInfo(get_system_timezone())).timestamp())

	payload = build_payload(
		company=doc.company,
		license_expires_on=doc.license_expires_on,
		grace_days=int(doc.grace_days or 0),
		warning_days=int(doc.warning_days or 0),
		status=doc.status,
		kid=kid,
		now=now_epoch,
	)

	doc.token = sign(payload, key, kid)
	doc.kid = kid
	doc.nonce = payload["nonce"]
	doc.issued_at = now
	doc.issued_by = frappe.session.user
	doc.grace_ends_on = frappe.utils.get_datetime(
		datetime.fromtimestamp(payload["exp"], ZoneInfo(get_system_timezone())).replace(tzinfo=None)
	)
	doc.save(ignore_permissions=True)

	frappe.logger("palm_mill").info(
		f"licence issued company={doc.company} expires={doc.license_expires_on} grace_days={doc.grace_days}"
	)

	return {
		"token": doc.token,
		"license_expires_at": payload["license_expires_at"],
		"exp": payload["exp"],
	}
