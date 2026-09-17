# Copyright (c) 2026, AutoERP and Contributors
# See license.txt

"""Who may hand out the `support` role.

`support` unlocks five diagnostic screens in the AutoGrade console -- log, ERP queue,
PLC test. Those are for whoever maintains the mill software, not for the customer, so
the choice is Administrator's alone. The check lives on the server because the form is
not the only way in: the same DocType is reachable over REST with any System Manager's
key.

Existing `support` accounts stay fully readable and editable, deliberately. Removing the
value from the Select would leave those documents showing an empty Role field, which
reads as corrupt data; and backoffice must still be able to fix a typo in a name or
switch an account off without being told they lack permission.
"""

import frappe
from frappe.tests import IntegrationTestCase


class IntegrationTestAutoGradeOperatorRole(IntegrationTestCase):
	def _buat(self, email: str, role: str):
		return frappe.get_doc(
			{
				"doctype": "AutoGrade Operator",
				"email": email,
				"full_name": "Uji Peran",
				"role": role,
				"active": 1,
				"new_password": "sawit2026",
			}
		).insert()

	def _jadi_system_manager(self) -> str:
		email = "uji.sysman.operator@test.local"
		if not frappe.db.exists("User", email):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": "Uji SysMan",
					"user_type": "System User",
					"send_welcome_email": 0,
					"roles": [{"role": "System Manager"}],
				}
			).insert(ignore_permissions=True)
		frappe.set_user(email)
		self.addCleanup(frappe.set_user, "Administrator")
		return email

	def test_administrator_may_create_a_support_account(self):
		frappe.set_user("Administrator")

		doc = self._buat("uji.support.admin@test.local", "support")

		self.assertEqual(doc.role, "support")

	def test_a_system_manager_may_not_create_a_support_account(self):
		self._jadi_system_manager()

		with self.assertRaises(frappe.PermissionError):
			self._buat("uji.support.ditolak@test.local", "support")

	def test_a_system_manager_may_still_create_an_operator_account(self):
		self._jadi_system_manager()

		doc = self._buat("uji.operator.boleh@test.local", "operator")

		self.assertEqual(doc.role, "operator")

	def test_a_system_manager_may_not_promote_an_operator_to_support(self):
		frappe.set_user("Administrator")
		doc = self._buat("uji.naik.pangkat@test.local", "operator")
		self._jadi_system_manager()

		doc.reload()
		doc.role = "support"
		with self.assertRaises(frappe.PermissionError):
			doc.save()

	def test_a_system_manager_may_still_edit_an_existing_support_account(self):
		"""Fixing a name or switching the account off must not be blocked."""
		frappe.set_user("Administrator")
		doc = self._buat("uji.support.diedit@test.local", "support")
		self._jadi_system_manager()

		doc.reload()
		doc.full_name = "Nama Diperbaiki"
		doc.active = 0
		doc.save()

		self.assertEqual(frappe.db.get_value("AutoGrade Operator", doc.name, "full_name"), "Nama Diperbaiki")

	def test_support_is_still_a_valid_stored_value(self):
		"""AutoGrade reads this column; the value must not be removed from the Select."""
		meta = frappe.get_meta("AutoGrade Operator")
		self.assertIn("support", meta.get_field("role").options.split("\n"))
