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

	def validate(self):
		# The email is the key on both sides: AutoGrade derives its local operator id from
		# it, so one address typed two ways must not become two accounts.
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
