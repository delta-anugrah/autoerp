# Copyright (c) 2026, AutoERP and Contributors
# See license.txt

"""Which roles a mill site offers when somebody creates a user.

A stock ERPNext site offers every role it ships -- 49 on ours -- of which a palm mill
uses seven. The rest are not merely noise: whoever creates the customer's admin has to
find `System Manager` among Academics User, HR Manager and Projects User, and picking
wrong is not visible until someone cannot open a screen.

These tests pin the mechanism, not only the count. Frappe has two ways to keep a role
out of that dropdown and they are not interchangeable: `disabled` deletes the role from
every user who holds it (`Role.remove_roles`) and re-enabling does not bring them back,
while `restrict_to_domain` touches nothing but the dropdown query. A regression that
swaps one for the other passes any test that only counts the dropdown -- hence the
explicit assertions on `Has Role` and on `disabled` below.
"""

import frappe
from frappe.core.doctype.user.user import get_all_roles
from frappe.tests import IntegrationTestCase

from erpnext.palm_mill import setup


class IntegrationTestRoleVisibility(IntegrationTestCase):
	def test_the_dropdown_offers_only_the_roles_a_mill_uses(self):
		setup.hide_unused_roles()

		offered = set(get_all_roles())
		for role in setup.MILL_ROLES:
			if frappe.db.exists("Role", role):
				self.assertIn(role, offered, f"{role} harus tetap ditawarkan")
		self.assertNotIn("HR Manager", offered)
		self.assertNotIn("Projects User", offered)

	def test_hiding_a_role_does_not_take_it_away_from_anyone(self):
		"""The failure this whole approach exists to avoid."""
		victim = "Sales User"
		frappe.get_doc(
			{
				"doctype": "User",
				"email": "uji.role.visibility@test.local",
				"first_name": "Uji Role",
				"user_type": "System User",
				"send_welcome_email": 0,
				"roles": [{"role": victim}],
			}
		).insert(ignore_permissions=True)
		before = frappe.db.count("Has Role", {"role": victim, "parenttype": "User"})

		setup.hide_unused_roles()

		self.assertEqual(frappe.db.count("Has Role", {"role": victim, "parenttype": "User"}), before)
		self.assertIn(victim, frappe.get_roles("uji.role.visibility@test.local"))

	def test_no_role_is_ever_disabled(self):
		"""`disabled` is the one column this code must never write."""
		before = dict(frappe.get_all("Role", fields=["name", "disabled"], as_list=True))

		setup.hide_unused_roles()

		after = dict(frappe.get_all("Role", fields=["name", "disabled"], as_list=True))
		self.assertEqual(before, after)

	def test_script_manager_and_workspace_manager_stay_visible(self):
		"""Both are referenced by name in Frappe's own code.

		`Script Manager` is in `role.py`'s STANDARD_ROLES and gates `frappe.only_for` in
		Server Script and Report; `Workspace Manager` gates editing any public workspace,
		including the mill's own. Hiding either leaves no way back from the UI.
		"""
		setup.hide_unused_roles()

		offered = get_all_roles()
		self.assertIn("Script Manager", offered)
		self.assertIn("Workspace Manager", offered)

	def test_a_role_already_restricted_by_erpnext_is_left_alone(self):
		frappe.db.set_value("Role", "Sales User", "restrict_to_domain", "Manufacturing")

		hasil = setup.hide_unused_roles()

		self.assertEqual(frappe.db.get_value("Role", "Sales User", "restrict_to_domain"), "Manufacturing")
		self.assertEqual(hasil["skipped"].get("Sales User"), "domain:Manufacturing")

	def test_the_domain_is_created_but_not_switched_on(self):
		setup.hide_unused_roles()

		self.assertTrue(frappe.db.exists("Domain", setup.ADVANCED_DOMAIN))
		self.assertNotIn(setup.ADVANCED_DOMAIN, frappe.get_active_domains())

	def test_running_it_twice_changes_nothing_the_second_time(self):
		setup.hide_unused_roles()
		sesudah_sekali = dict(frappe.get_all("Role", fields=["name", "restrict_to_domain"], as_list=True))

		kedua = setup.hide_unused_roles()

		self.assertEqual(
			dict(frappe.get_all("Role", fields=["name", "restrict_to_domain"], as_list=True)),
			sesudah_sekali,
		)
		self.assertEqual(kedua["hidden"], [])

	def test_administrator_can_bring_a_role_back(self):
		"""The escape hatch the customer's admin is told about in the skill."""
		setup.hide_unused_roles()
		self.assertNotIn("HR Manager", get_all_roles())

		frappe.db.set_value("Role", "HR Manager", "restrict_to_domain", "")
		frappe.clear_cache()

		self.assertIn("HR Manager", get_all_roles())


class IntegrationTestRoleVisibilityWiring(IntegrationTestCase):
	def test_the_install_hook_hides_the_roles(self):
		import inspect

		self.assertIn("hide_unused_roles()", inspect.getsource(setup.after_install))

	def test_the_patch_calls_the_same_code_as_the_hook(self):
		import inspect

		from erpnext.patches.v17_0 import palm_mill_role_visibility

		self.assertIn("hide_unused_roles", inspect.getsource(palm_mill_role_visibility.execute))

	def test_the_patch_is_registered(self):
		from pathlib import Path

		daftar = Path(frappe.get_app_path("erpnext")).joinpath("patches.txt").read_text()
		self.assertIn("erpnext.patches.v17_0.palm_mill_role_visibility", daftar)
