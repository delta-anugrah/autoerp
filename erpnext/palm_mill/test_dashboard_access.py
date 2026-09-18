# Copyright (c) 2026, AutoERP and Contributors
# See license.txt

"""What the mill workspace needs before it will draw for the customer's own admin.

`System Manager` administers the system -- users, settings, DocTypes. In ERPNext it does
not read transactions: Purchase Receipt, Stock Entry and the invoices are reached through
the module roles instead. An admin holding only `System Manager` therefore opens the mill
workspace and gets "You don't have permission to get a report on: Stock Entry", with four
of the seven cards stuck on "Loading...".

That is our gap, not ERPNext's: the `Admin Pabrik` profile promises the person who runs
the mill's ERP, and we pointed them at a dashboard built from documents that role was
never meant to see. These tests pin the roles that make the workspace whole, so a later
trim of the profile cannot quietly blank it again.
"""

import frappe
from frappe.tests import IntegrationTestCase

from erpnext.palm_mill import setup

# Every doctype the workspace's cards, charts and shortcuts read. `Oil Extraction Rate`
# declares `ref_doctype: Stock Entry`, and Frappe checks the report permission there --
# not against the roles listed on the report -- so Stock Entry is what gates the OER card.
WORKSPACE_READS = (
	"Weighbridge Ticket",
	"Stock Entry",
	"Purchase Receipt",
	"Purchase Invoice",
	"Sales Invoice",
	"Batch",
	"Item",
	"Supplier",
	"Warehouse",
)


class IntegrationTestDashboardAccess(IntegrationTestCase):
	EMAIL = "uji.admin.dashboard@test.local"

	def _admin_pabrik(self) -> str:
		"""Runs the patch, not just `setup_role_profiles`.

		A site that already has `Admin Pabrik` keeps it as it was -- the setup function only
		ever creates -- so the roles reach an existing profile through the patch. Testing the
		other path would pass on a fresh site and miss every site that matters.
		"""
		from erpnext.patches.v17_0 import palm_mill_dashboard_access

		palm_mill_dashboard_access.execute()
		if frappe.db.exists("User", self.EMAIL):
			frappe.delete_doc("User", self.EMAIL, force=True, ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "User",
				"email": self.EMAIL,
				"first_name": "Uji Dashboard",
				"user_type": "System User",
				"send_welcome_email": 0,
				"role_profiles": [{"role_profile": setup.PROFILE_ADMIN}],
			}
		).insert(ignore_permissions=True)
		return self.EMAIL

	def test_the_admin_profile_can_read_everything_the_workspace_draws(self):
		self._admin_pabrik()
		frappe.set_user(self.EMAIL)
		self.addCleanup(frappe.set_user, "Administrator")

		gagal = [
			dt
			for dt in WORKSPACE_READS
			if not (frappe.has_permission(dt, "read") and frappe.has_permission(dt, "report"))
		]

		self.assertEqual(gagal, [], f"kartu dashboard akan gagal untuk: {gagal}")

	def test_the_oer_report_is_reachable(self):
		"""The card that produced the error report on a live site."""
		self._admin_pabrik()
		frappe.set_user(self.EMAIL)
		self.addCleanup(frappe.set_user, "Administrator")

		ref = frappe.db.get_value("Report", "Oil Extraction Rate", "ref_doctype")

		self.assertEqual(ref, "Stock Entry")
		self.assertTrue(frappe.has_permission(ref, "report"))

	def test_the_batch_shortcut_is_not_a_dead_link(self):
		"""`CPO / PK Batches` sits on the workspace; a shortcut nobody may open is clutter."""
		setup.setup_batch_access()
		self._admin_pabrik()
		frappe.set_user(self.EMAIL)
		self.addCleanup(frappe.set_user, "Administrator")

		self.assertTrue(frappe.has_permission("Batch", "read"))

	def test_the_operator_may_read_batches_too(self):
		"""Finalising a ticket creates one, and the ticket links to it."""
		setup.setup_batch_access()

		peran = frappe.get_all("Custom DocPerm", filters={"parent": "Batch"}, pluck="role")

		self.assertIn(setup.OPERATOR_ROLE, peran)

	def test_granting_batch_access_twice_changes_nothing(self):
		setup.setup_batch_access()
		sebelum = frappe.db.count("Custom DocPerm", {"parent": "Batch"})

		setup.setup_batch_access()

		self.assertEqual(frappe.db.count("Custom DocPerm", {"parent": "Batch"}), sebelum)

	def test_the_admin_profile_still_carries_system_manager(self):
		"""The roles added here are for reading; administering the site is still the point."""
		self.assertIn("System Manager", setup.ROLE_PROFILES[setup.PROFILE_ADMIN])


class IntegrationTestDashboardAccessWiring(IntegrationTestCase):
	def test_the_install_hook_grants_batch_access(self):
		import inspect

		self.assertIn("setup_batch_access()", inspect.getsource(setup.after_install))

	def test_the_patch_calls_the_same_code_as_the_hook(self):
		import inspect

		from erpnext.patches.v17_0 import palm_mill_dashboard_access

		self.assertIn("setup_batch_access", inspect.getsource(palm_mill_dashboard_access.execute))
		self.assertIn("setup_role_profiles", inspect.getsource(palm_mill_dashboard_access.execute))
