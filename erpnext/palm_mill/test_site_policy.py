# Copyright (c) 2026, AutoERP and Contributors
# See license.txt

"""The policy a mill site has to be born with, and the wiring that gets it there.

A fresh site never runs patches: `install_app(set_as_patched=True)` marks all of them
completed without executing any. Until 2026-09-17 that meant every new site -- including
the production one, which is also born empty -- came up in English, at three decimals,
and unable to receive FFB at all (417 "Activate Serial and Batch No" on finalisation).
The cure was three commands typed by hand, in six different documents, which is the kind
of step that gets skipped exactly once and then debugged for an afternoon.

These tests pin the wiring, not just the effect. A regression here is silent by nature:
the site installs cleanly, looks fine on the login page, and only fails hours later at
the weighbridge -- so "did the hook actually get called" has to be asserted directly.
"""

import frappe
from frappe.tests import IntegrationTestCase

from erpnext.palm_mill import setup


class IntegrationTestSitePolicy(IntegrationTestCase):
	"""Effects of the policy functions, on the live test site."""

	def test_site_language_is_indonesian_and_the_language_is_enabled(self):
		setup.set_site_language()

		self.assertEqual(frappe.db.get_single_value("System Settings", "language"), "id")
		self.assertTrue(frappe.db.get_value("Language", "id", "enabled"))

	def test_users_pinned_to_the_old_default_follow_the_site_again(self):
		"""`en-US` on the user record outranks the site setting, so switching the site alone
		would leave every existing user in English with no visible reason why."""
		user = frappe.get_doc("User", "Administrator")
		before = user.language
		frappe.db.set_value("User", "Administrator", "language", "en-US")
		try:
			setup.set_site_language()
			self.assertIsNone(frappe.db.get_value("User", "Administrator", "language"))
		finally:
			frappe.db.set_value("User", "Administrator", "language", before)

	def test_floats_are_shown_to_two_decimals(self):
		setup.set_float_precision()

		self.assertEqual(frappe.db.get_single_value("System Settings", "float_precision"), "2")
		self.assertEqual(frappe.db.get_default("float_precision"), "2")

	def test_batched_items_can_be_submitted_at_all(self):
		"""Without this, finalising a ticket fails 417 and no amount of correct grading data
		gets FFB into the system."""
		setup.enable_serial_and_batch()

		self.assertTrue(frappe.db.get_single_value("Stock Settings", "enable_serial_and_batch_no_for_item"))

	def test_applying_the_policy_twice_changes_nothing_the_second_time(self):
		"""Both install hooks and the patches call these, so a site can see them more than
		once -- on install, then again on the next migrate."""
		setup.apply_site_policy()
		first = self._policy_state()

		setup.apply_site_policy()

		self.assertEqual(first, self._policy_state())

	def test_a_seed_warehouse_holding_stock_is_left_alone(self):
		"""An empty seed warehouse is clutter; one with ledger entries is somebody's data,
		and disabling it would break their stock transactions."""
		warehouse = frappe.get_all(
			"Warehouse", filters={"warehouse_name": ("in", setup.SEED_WAREHOUSES)}, pluck="name"
		)
		if not warehouse:
			self.skipTest("test site has no seed warehouses")
		name = warehouse[0]
		frappe.db.set_value("Warehouse", name, "disabled", 0)

		entry = frappe.get_doc(
			{
				"doctype": "Stock Ledger Entry",
				"item_code": "_Test Item",
				"warehouse": name,
				"posting_date": frappe.utils.today(),
				"actual_qty": 1,
				"voucher_type": "Stock Entry",
				"voucher_no": "_TEST-SLE-POLICY",
				"company": "_Test Company",
			}
		)
		entry.db_insert()
		try:
			setup.hide_seed_masters()
			self.assertFalse(
				frappe.db.get_value("Warehouse", name, "disabled"),
				f"{name} holds stock and must stay enabled",
			)
		finally:
			frappe.db.delete("Stock Ledger Entry", {"voucher_no": "_TEST-SLE-POLICY"})

	def test_a_seed_item_group_still_in_use_is_left_alone(self):
		"""Deleting an item group that items point at would orphan them."""
		in_use = [
			ig
			for ig in setup.SEED_ITEM_GROUPS
			if frappe.db.exists("Item Group", ig) and frappe.db.exists("Item", {"item_group": ig})
		]
		if not in_use:
			self.skipTest("no seed item group is in use on the test site")

		setup.hide_seed_masters()

		for ig in in_use:
			self.assertTrue(frappe.db.exists("Item Group", ig), f"{ig} is in use and must survive")

	def _policy_state(self):
		return (
			frappe.db.get_single_value("System Settings", "language"),
			frappe.db.get_single_value("System Settings", "float_precision"),
			frappe.db.get_single_value("Stock Settings", "enable_serial_and_batch_no_for_item"),
			frappe.db.get_value("Language", "id", "enabled"),
		)


class IntegrationTestSitePolicyWiring(IntegrationTestCase):
	"""That the policy is reached at install time at all.

	Asserting the effects above would still pass on a site that was fixed by hand, which is
	precisely how this went unnoticed for as long as it did.
	"""

	def test_install_hook_applies_the_policy(self):
		"""If `apply_site_policy` ever falls out of `after_install`, a new site is born in
		English again and nothing says so until the first truck."""
		import inspect

		self.assertIn("apply_site_policy()", inspect.getsource(setup.after_install))

	def test_the_app_registers_both_install_hooks(self):
		hooks = frappe.get_hooks()

		self.assertIn("erpnext.palm_mill.setup.after_install", hooks.get("after_install", []))
		self.assertIn("erpnext.palm_mill.setup.setup_wizard_complete", hooks.get("setup_wizard_complete", []))

	def test_seed_cleanup_waits_for_the_wizard(self):
		"""The seed warehouses are created by `Company.create_default_warehouses` and the seed
		item groups by the wizard's `install_fixtures` -- both of which run *after*
		`after_install`. Calling `hide_seed_masters` from the install hook would match nothing
		and quietly leave the clutter behind, so it belongs to the wizard hook instead.
		"""
		import inspect

		self.assertNotIn("hide_seed_masters()", inspect.getsource(setup.after_install))
		self.assertIn("hide_seed_masters()", inspect.getsource(setup.setup_wizard_complete))

	def test_the_wizard_hook_takes_the_arguments_frappe_passes_it(self):
		"""`get_setup_complete_hooks` calls every hook with the wizard's `args`; a function
		that does not accept them fails the last stage of the wizard, after the company has
		already been created."""
		import inspect

		signature = inspect.signature(setup.setup_wizard_complete)
		signature.bind({"country": "Indonesia"})

	def test_the_patches_call_the_same_code_as_the_hooks(self):
		"""Two copies of this policy would drift, and the patch copy is the one nobody looks
		at until a site is already wrong."""
		import inspect

		from erpnext.patches.v17_0 import palm_mill_language, palm_mill_precision

		language = inspect.getsource(palm_mill_language)
		self.assertIn("set_site_language()", language)
		self.assertIn("hide_seed_masters()", language)
		self.assertIn("from erpnext.palm_mill.setup import", language)

		precision = inspect.getsource(palm_mill_precision)
		self.assertIn("set_float_precision()", precision)
		self.assertIn("from erpnext.palm_mill.setup import", precision)
