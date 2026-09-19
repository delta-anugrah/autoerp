# Copyright (c) 2026, AutoERP and Contributors
# See license.txt

"""The "Pengaturan" folder, and the wiring that puts the two setup icons in it.

The failure mode worth guarding here is not a crash. `build_folder_map` in
`sidebar_header.js` keeps a child icon only when its `parent_icon` is a folder it can
also see -- so pointing an icon at a folder that does not exist does not raise
anything, it just silently drops the icon off the Desk. Both of these icons are how an
owner reaches company setup and site settings, so losing them that quietly is the
expensive outcome.
"""

import frappe
from frappe.tests import IntegrationTestCase

from erpnext.palm_mill import settings_folder, setup
from erpnext.palm_mill.settings_folder import CHILDREN, FOLDER, group_settings_icons


class IntegrationTestSettingsFolder(IntegrationTestCase):
	def tearDown(self):
		group_settings_icons()
		super().tearDown()

	def test_the_folder_exists_and_is_a_folder(self):
		"""`icon_type` is what makes the Desk draw it as something that opens rather
		than something that navigates. A Link with no `link_to` would render as a dead
		icon instead."""
		group_settings_icons()

		self.assertTrue(frappe.db.exists("Desktop Icon", FOLDER))
		self.assertEqual(frappe.db.get_value("Desktop Icon", FOLDER, "icon_type"), "Folder")

	def test_both_icons_sit_under_it(self):
		group_settings_icons()

		for name in CHILDREN:
			self.assertEqual(
				frappe.db.get_value("Desktop Icon", name, "parent_icon"),
				FOLDER,
				f"{name} is not under {FOLDER}",
			)

	def test_neither_icon_is_hidden(self):
		"""Grouping is not hiding. Both screens must still be reachable -- one click
		further in, not gone."""
		group_settings_icons()

		for name in (FOLDER, *CHILDREN):
			self.assertFalse(
				frappe.db.get_value("Desktop Icon", name, "hidden"),
				f"{name} was hidden rather than grouped",
			)

	def test_the_folder_is_created_before_anything_is_reparented(self):
		"""The quiet failure, pinned.

		`build_folder_map` keeps a child only when it can see its parent, so if the
		folder is missing the two icons vanish from the Desk with no error anywhere.
		Deleting the folder and re-running has to put it back, not orphan them.
		"""
		group_settings_icons()
		frappe.delete_doc("Desktop Icon", FOLDER, force=True, ignore_permissions=True)

		result = group_settings_icons()

		self.assertTrue(result["created"], "the folder was not recreated")
		self.assertTrue(frappe.db.exists("Desktop Icon", FOLDER))
		for name in CHILDREN:
			self.assertEqual(frappe.db.get_value("Desktop Icon", name, "parent_icon"), FOLDER)

	def test_the_mill_icon_is_not_moved_into_this_folder(self):
		"""The one icon that must never end up in here: it is the screen the Desk exists
		to reach.

		It is not parentless -- it sits under the `AutoERP` app icon, which is the app
		grouping every erpnext icon hangs from and is not a folder the Desk draws. The
		assertion is therefore "not in Pengaturan", not "has no parent".
		"""
		group_settings_icons()

		self.assertNotEqual(
			frappe.db.get_value("Desktop Icon", "Pabrik Kelapa Sawit", "parent_icon"),
			FOLDER,
			"the mill icon was moved into the settings folder",
		)

	def test_the_desk_shows_three_things(self):
		"""What the customer actually sees.

		`build_folder_map` draws an icon when it is visible and its parent is either
		absent or an app grouping rather than a drawn folder -- so the top row is every
		visible erpnext icon whose parent is not one of the folders. Before this change
		that was four; the point of the change is that it is three.
		"""
		group_settings_icons()

		folders = {
			row.name
			for row in frappe.get_all(
				"Desktop Icon", filters={"icon_type": "Folder", "hidden": 0}, fields=["name"]
			)
		}
		visible = frappe.get_all(
			"Desktop Icon",
			filters={"hidden": 0, "app": "erpnext", "standard": 1},
			fields=["name", "parent_icon"],
		)
		top = sorted(row.name for row in visible if (row.parent_icon or "") not in folders)

		self.assertEqual(
			top,
			["Accounting", "Pabrik Kelapa Sawit", FOLDER],
			f"the Desk home is not the expected three icons: {top}",
		)

	def test_the_json_and_this_module_agree(self):
		"""Two sources for the same fact: the fixtures a fresh site reads, and the code
		an existing site runs. If they drift the two kinds of site end up different."""
		import json
		import os

		import erpnext

		folder = os.path.join(os.path.dirname(erpnext.__file__), "desktop_icon")
		files = {"Organization": "organization.json", "AutoERP Settings": "autoerp_settings.json"}

		with open(os.path.join(folder, "pengaturan.json")) as f:
			self.assertEqual(json.load(f)["icon_type"], "Folder")

		for name, filename in files.items():
			with open(os.path.join(folder, filename)) as f:
				self.assertEqual(
					json.load(f)["parent_icon"], FOLDER, f"{filename} still points elsewhere"
				)

	def test_applying_it_twice_reports_nothing_left_to_do(self):
		group_settings_icons()

		second = group_settings_icons()

		self.assertFalse(second["created"])
		self.assertEqual(second["moved"], [], "re-running moved something a second time")

	def test_an_icon_upstream_removed_is_skipped_rather_than_crashing(self):
		original = settings_folder.CHILDREN
		settings_folder.CHILDREN = (*original, "Icon That Does Not Exist")
		try:
			result = group_settings_icons()
			self.assertIn("Icon That Does Not Exist", result["absent"])
		finally:
			settings_folder.CHILDREN = original

	def test_the_install_hook_runs_it(self):
		import inspect

		self.assertIn("group_settings_icons()", inspect.getsource(setup.after_install))

	def test_the_patch_calls_the_same_code_as_the_hook(self):
		import inspect

		from erpnext.patches.v17_0 import palm_mill_settings_folder

		source = inspect.getsource(palm_mill_settings_folder)
		self.assertIn("group_settings_icons()", source)
		self.assertIn("from erpnext.palm_mill.settings_folder import", source)

	def test_the_patch_is_registered(self):
		import os

		import erpnext

		patches = os.path.join(os.path.dirname(erpnext.__file__), "patches.txt")
		with open(patches) as f:
			self.assertIn("erpnext.patches.v17_0.palm_mill_settings_folder", f.read())
