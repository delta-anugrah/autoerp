# Copyright (c) 2026, AutoERP and Contributors
# See license.txt

"""The customer's own administrator account.

A site handed over with only `Administrator` is a site where every change is signed by
the same shared login, and the activity log cannot say who did what. The step that
prevents that used to exist nowhere -- not in `installation.md`, not in the install
skill -- so it was the step that got skipped.

`System Manager` is what the customer's admin needs and all they need: it creates users,
edits Palm Mill Settings, and reaches every mill DocType. No password is printed; the
account is opened through a reset link, so nothing quotable ends up in a terminal
scrollback or a chat message.
"""

import frappe
from frappe.tests import IntegrationTestCase

from erpnext.palm_mill import setup


class IntegrationTestAdminUser(IntegrationTestCase):
	"""Each test gets its own address.

	`IntegrationTestCase` does not roll the database back between methods, so a user made
	by one test is still there for the next -- and `create_admin_user` would then take the
	existing-user branch and leave the name from the earlier test in place.
	"""

	def setUp(self):
		self.EMAIL = f"uji.admin.{self._testMethodName}@test.local"

	def test_the_account_is_created_with_system_manager(self):
		hasil = setup.create_admin_user(self.EMAIL, "Admin Pelanggan")

		self.assertEqual(hasil["user"], self.EMAIL)
		self.assertIn("System Manager", frappe.get_roles(self.EMAIL))

	def test_it_is_a_desk_user_who_was_not_emailed(self):
		setup.create_admin_user(self.EMAIL, "Admin Pelanggan")

		user = frappe.get_doc("User", self.EMAIL)
		self.assertEqual(user.user_type, "System User")

	def test_running_it_again_does_not_duplicate_the_role(self):
		setup.create_admin_user(self.EMAIL, "Admin Pelanggan")

		hasil = setup.create_admin_user(self.EMAIL, "Admin Pelanggan")

		baris = frappe.get_all("Has Role", filters={"parent": self.EMAIL, "role": "System Manager"})
		self.assertEqual(len(baris), 1)
		self.assertEqual(hasil["roles_added"], [])

	def test_an_existing_user_keeps_the_roles_they_already_had(self):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": self.EMAIL,
				"first_name": "Sudah Ada",
				"user_type": "System User",
				"send_welcome_email": 0,
				"roles": [{"role": setup.OPERATOR_ROLE}],
			}
		).insert(ignore_permissions=True)

		setup.create_admin_user(self.EMAIL, "Sudah Ada")

		peran = frappe.get_roles(self.EMAIL)
		self.assertIn(setup.OPERATOR_ROLE, peran)
		self.assertIn("System Manager", peran)

	def test_the_reset_link_actually_works(self):
		"""The key in the link must be the raw one; Frappe stores only its sha256.

		Writing the raw key into `reset_password_key` produces a link that looks right and
		fails on use: `_get_user_for_update_password` hashes what the visitor brings and
		finds nothing, so the page says the link "has either been used before or is
		invalid" -- with no hint that the account was never openable to begin with.
		"""
		from frappe.core.doctype.user.user import _get_user_for_update_password

		hasil = setup.create_admin_user(self.EMAIL, "Admin Pelanggan")
		kunci = hasil["reset_link"].split("key=")[1]

		periksa = _get_user_for_update_password(kunci, None)

		self.assertEqual(periksa.get("user"), self.EMAIL)
		self.assertFalse(periksa.get("message"), periksa.get("message"))

	def test_it_hands_back_a_reset_link_instead_of_a_password(self):
		hasil = setup.create_admin_user(self.EMAIL, "Admin Pelanggan")

		self.assertIn("/update-password?key=", hasil["reset_link"])
		self.assertNotIn("password", {k.lower() for k in hasil})

	def test_the_full_name_is_split_into_first_and_last(self):
		setup.create_admin_user(self.EMAIL, "Admin Pelanggan")

		user = frappe.get_doc("User", self.EMAIL)
		self.assertEqual(user.first_name, "Admin")
		self.assertEqual(user.last_name, "Pelanggan")

	def test_a_single_word_name_is_accepted(self):
		setup.create_admin_user(self.EMAIL, "Budi")

		user = frappe.get_doc("User", self.EMAIL)
		self.assertEqual(user.first_name, "Budi")

	def test_the_makefile_exposes_it(self):
		"""The function is only reachable in practice through this target."""
		from pathlib import Path

		makefile = Path(frappe.get_app_path("erpnext")).parent / "Makefile"
		isi = makefile.read_text()
		self.assertIn("admin-new:", isi)
		self.assertIn("create_admin_user", isi)
