# Copyright (c) 2026, AutoERP and contributors
# For license information, please see license.txt

"""One row per token ever issued. This is a ledger, not a setting.

Reissuing onto the same row is refused (`license.issue`), so the history of what a
mill was handed stays readable: which dates, which grace, when, by whom.

The signing itself lives in `erpnext/palm_mill/license.py` - this class only guards
the inputs. See that module for why the key is asymmetric and where it lives.
"""

import frappe
from frappe import _
from frappe.model.document import Document

# A token that is signed but never installed is harmless; one that is installed and
# then edited is not. Once issued, the terms are frozen - the mill is holding a
# signed copy of them and cannot be told they changed.
FROZEN_AFTER_ISSUE = ("company", "license_expires_on", "grace_days", "warning_days", "status")


class AutoGradeLicence(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		company: DF.Link
		grace_days: DF.Int
		grace_ends_on: DF.Datetime | None
		issued_at: DF.Datetime | None
		issued_by: DF.Data | None
		kid: DF.Data | None
		license_expires_on: DF.Date
		nonce: DF.Data | None
		status: DF.Literal["ACTIVE", "CANCEL"]
		token: DF.SmallText | None
		warning_days: DF.Int
	# end: auto-generated types

	def validate(self):
		self._freeze_issued_terms()
		self._check_warning_fits_subscription()

	def _freeze_issued_terms(self):
		if self.is_new() or not self.token:
			return

		before = self.get_doc_before_save()
		if not before:
			return

		for field in FROZEN_AFTER_ISSUE:
			if self.get(field) != before.get(field):
				frappe.throw(
					_("{0} cannot change once the token is issued. Create a new licence row instead.").format(
						_(self.meta.get_label(field))
					),
					title=_("Already issued"),
				)

	def _check_warning_fits_subscription(self):
		"""A warning window longer than the subscription warns from day one.

		Not fatal - a one-month trial with a 30-day warning is a legitimate thing to
		issue - so this is a message, not a throw.
		"""
		if not self.warning_days or not self.license_expires_on:
			return

		days_left = frappe.utils.date_diff(self.license_expires_on, frappe.utils.nowdate())
		if days_left >= 0 and self.warning_days > days_left:
			frappe.msgprint(
				_("The warning window ({0} days) is longer than the time left ({1} days), so the console will warn from the moment this is installed.").format(
					self.warning_days, days_left
				),
				indicator="orange",
				alert=True,
			)
