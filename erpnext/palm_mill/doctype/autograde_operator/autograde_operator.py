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
SUPPORT_ROLE = "support"


class AutoGradeOperator(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		active: DF.Check
		email: DF.Data
		full_name: DF.Data
		new_password: DF.Data | None
		password_hash: DF.Data | None
		role: DF.Literal["operator", "support"]
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
		self._guard_support_role()
		self._take_new_password()

	def _take_new_password(self):
		"""Hash whatever was typed into `new_password`, then wipe the field.

		Wiping is the point. `track_changes` is on, so every save writes a Version row —
		a raw password left on the document would sit in that history, readable by
		anyone who can open the document, including passwords long since replaced. The
		field is a form input, never stored: it exists only between the browser and this
		method.

		Empty means "leave the password alone", which is what lets backoffice fix a typo
		in a name without locking the operator out of the console.
		"""
		password = (self.new_password or "").strip()
		self.new_password = None
		if not password:
			return
		self._check_password_length(password)
		self.password_hash = passlibctx.hash(password)

	def _guard_support_role(self):
		"""Only Administrator hands out `support`.

		Checked on the server, not only in the form: the same DocType is reachable over
		REST with any System Manager's API key, and the form's own filtering is a
		convenience, not a control.

		Only a *change into* `support` is refused. An account that already holds it can
		still be saved by anyone who may write the doctype -- otherwise backoffice could
		not correct a name or switch the account off, and would be told they lack
		permission for an edit that has nothing to do with the role.
		"""
		if self.role != SUPPORT_ROLE:
			return
		if frappe.session.user == "Administrator":
			return
		sebelumnya = self.get_doc_before_save() if not self.is_new() else None
		if sebelumnya and sebelumnya.role == SUPPORT_ROLE:
			return
		frappe.throw(
			_("Only Administrator can give the {0} role.").format(frappe.bold(SUPPORT_ROLE)),
			frappe.PermissionError,
			title=_("Not permitted"),
		)

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
		self._check_password_length(password)
		self.db_set("password_hash", passlibctx.hash(password), update_modified=True)

	@staticmethod
	def _check_password_length(password: str) -> None:
		"""One rule for both ways in — the form field and `set_password` — so neither can
		quietly accept a password the other refuses."""
		if len(password) < PASSWORD_MIN_LENGTH:
			frappe.throw(
				_("Password must be at least {0} characters").format(PASSWORD_MIN_LENGTH),
				frappe.ValidationError,
			)
