# Copyright (c) 2026, AutoERP and contributors
# For license information, please see license.txt

"""The account an operator signs in to the AutoGrade console with.

AutoERP owns these accounts and hashes the passwords. AutoGrade pulls them down with the
master data (`docs/autograde-integration.md` §4.A) and verifies them **at the mill**,
because the console has to let someone in while the internet is down.

That is why the hash is a plain readable `Data` field rather than Frappe's own `User`
password: a `Password` field, like `User`, stores its value in `__Auth`, which is
deliberately never served over REST — so nothing could be pulled and offline sign-in
would be impossible. What leaves this site is a passlib hash, never a password.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import validate_email_address
from frappe.utils.password import passlibctx

PASSWORD_MIN_LENGTH = 8


class AutoGradeOperator(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		active: DF.Check
		email: DF.Data
		full_name: DF.Data
		password_hash: DF.Data | None
	# end: auto-generated types

	def before_naming(self):
		"""Normalise before `autoname: field:email` takes its snapshot.

		Doing this in `validate` is too late: naming has already copied the address as
		typed, so `Operator.DUA@pks.local` becomes a document named differently from one
		created as `operator.dua@pks.local` — and Frappe's duplicate check compares those
		names, so the same person typed two ways becomes two accounts with two passwords.
		AutoGrade derives its local operator id from this address, so the split would
		reach the mill as well.
		"""
		self._normalise_email()

	def validate(self):
		# Also here, not only in `before_naming`: an edit to an existing document does not
		# run naming again, and the field must not drift away from the name.
		self._normalise_email()

	def _normalise_email(self):
		self.email = (self.email or "").strip().lower()
		validate_email_address(self.email, throw=True)

	@frappe.whitelist()
	def set_password(self, password: str) -> None:
		"""Hash a new password with Frappe's own passlib context.

		Written straight to the column rather than through the document so the raw value
		never reaches a version row or an audit trail. The hash is what AutoGrade verifies
		offline; `pbkdf2_sha256` is in Python's standard library, so the mill needs no
		extra dependency to read it.
		"""
		self.check_permission("write")
		password = password or ""
		if len(password) < PASSWORD_MIN_LENGTH:
			frappe.throw(
				_("Password must be at least {0} characters").format(PASSWORD_MIN_LENGTH),
				frappe.ValidationError,
			)
		self.db_set("password_hash", passlibctx.hash(password), update_modified=True)
