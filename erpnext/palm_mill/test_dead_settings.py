# Copyright (c) 2026, AutoERP and Contributors
# See license.txt

"""Settings links a palm mill cannot use, and the wiring that removes them.

Two of these tests exist because of mistakes made while writing this module, and both
mistakes looked like success at the time:

- Editing `workspace_sidebar/*.json` and running `bench migrate` left every link in
  place. The sync upserts rows; it has no concept of a row a file stopped listing.
- Dropping the rows from `doc.items` and calling `db_update_all` also left them:
  that method rewrites the rows still attached and never deletes.

So the tests assert against the database after the call, not against the JSON and not
against what the code appears to do.
"""

import frappe
from frappe.tests import IntegrationTestCase

from erpnext.palm_mill import dead_settings, setup
from erpnext.palm_mill.dead_settings import DEAD_LINKS, remove_dead_settings

# Settings the mill does use. None of these may be removed.
KEPT_SETTINGS = (
	"Global Defaults",
	"System Settings",
	"Accounts Settings",
	"Stock Settings",
	"Currency Exchange Settings",
	"Stock Reposting Settings",
)


class IntegrationTestDeadSettings(IntegrationTestCase):
	def tearDown(self):
		remove_dead_settings()
		super().tearDown()

	def test_the_broken_link_is_gone(self):
		"""`Repost Accounting Ledger Settings` points at a DocType that does not exist
		on this fork. Clicking it is an error page, in two different sidebars."""
		remove_dead_settings()

		rows = frappe.get_all(
			"Workspace Sidebar Item",
			filters={"link_to": "Repost Accounting Ledger Settings"},
			fields=["parent"],
		)
		self.assertEqual(rows, [], "the broken link is still on a sidebar")

	def test_the_link_it_removes_really_is_broken(self):
		"""Guards the premise. If a later ERPNext ships this DocType, removing its link
		stops being a fix and starts being a feature we deleted."""
		self.assertFalse(
			frappe.db.exists("DocType", "Repost Accounting Ledger Settings"),
			"the DocType exists now; this link is no longer broken",
		)

	def test_every_listed_link_is_removed(self):
		remove_dead_settings()

		for sidebar, links in DEAD_LINKS.items():
			if not frappe.db.exists("Workspace Sidebar", sidebar):
				continue
			present = {item.link_to for item in frappe.get_doc("Workspace Sidebar", sidebar).items}
			for link in links:
				self.assertNotIn(link, present, f"{link} still on {sidebar}")

	def test_the_settings_the_mill_uses_are_kept(self):
		"""The expensive mistake in the other direction: removing a settings page the
		owner needs leaves them no way in from the Desk."""
		listed = {link for links in DEAD_LINKS.values() for link in links}
		for name in KEPT_SETTINGS:
			self.assertNotIn(name, listed, f"{name} is one the mill uses")

		remove_dead_settings()

		present = {item.link_to for item in frappe.get_doc("Workspace Sidebar", "AutoERP Settings").items}
		for name in KEPT_SETTINGS:
			self.assertIn(name, present, f"{name} vanished from AutoERP Settings")

	def test_the_rows_are_deleted_not_just_detached(self):
		"""The second mistake, pinned.

		`db_update_all` rewrites the rows still on the document and never deletes, so
		detaching a row from `doc.items` leaves it in the child table and on the screen.
		A count against the table is the only assertion that catches that.
		"""
		remove_dead_settings()

		for sidebar, links in DEAD_LINKS.items():
			if not frappe.db.exists("Workspace Sidebar", sidebar):
				continue
			stale = frappe.db.count(
				"Workspace Sidebar Item",
				{"parent": sidebar, "parenttype": "Workspace Sidebar", "link_to": ("in", links)},
			)
			self.assertEqual(stale, 0, f"{sidebar} keeps orphaned rows in the child table")

	def test_a_section_left_without_links_is_removed(self):
		"""`Other Settings` loses four of its six links. A Section Break with nothing
		under it draws as a heading over empty space."""
		remove_dead_settings()

		items = frappe.get_doc("Workspace Sidebar", "AutoERP Settings").items
		for index, item in enumerate(items):
			if item.type == "Section Break":
				self.assertTrue(
					any(r.type == "Link" for r in items[index + 1 :]),
					f"section {item.label!r} heads nothing",
				)

	def test_the_sidebar_stays_standard(self):
		"""These are `standard` records synced from the app's JSON. If this marks one
		customised, the next migrate silently stops syncing it from the file and the
		JSON quietly stops being the source of truth."""
		remove_dead_settings()

		for sidebar in DEAD_LINKS:
			if frappe.db.exists("Workspace Sidebar", sidebar):
				self.assertTrue(
					frappe.db.get_value("Workspace Sidebar", sidebar, "standard"),
					f"{sidebar} is no longer standard",
				)

	def test_the_json_and_this_module_agree(self):
		"""Two lists that must match: the file the sync reads, and the code an existing
		site runs. If they drift, a fresh site and a migrated site end up different."""
		import json
		import os

		import erpnext

		folder = os.path.join(os.path.dirname(erpnext.__file__), "workspace_sidebar")
		files = {"AutoERP Settings": "autoerp_settings.json", "Accounts Setup": "accounts_setup.json"}

		for sidebar, links in DEAD_LINKS.items():
			with open(os.path.join(folder, files[sidebar])) as f:
				in_file = {item.get("link_to") for item in json.load(f)["items"]}
			for link in links:
				self.assertNotIn(link, in_file, f"{link} still in {files[sidebar]}")

	def test_applying_it_twice_reports_nothing_left_to_do(self):
		remove_dead_settings()

		second = remove_dead_settings()

		self.assertEqual(second["removed"], [], "re-running removed something a second time")

	def test_a_sidebar_upstream_removed_is_skipped_rather_than_crashing(self):
		original = dead_settings.DEAD_LINKS
		dead_settings.DEAD_LINKS = {**original, "Sidebar That Does Not Exist": ("Whatever",)}
		try:
			result = remove_dead_settings()
			self.assertIn("Sidebar That Does Not Exist", result["absent"])
		finally:
			dead_settings.DEAD_LINKS = original

	def test_the_install_hook_runs_it(self):
		import inspect

		self.assertIn("remove_dead_settings()", inspect.getsource(setup.after_install))

	def test_the_patch_calls_the_same_code_as_the_hook(self):
		import inspect

		from erpnext.patches.v17_0 import palm_mill_dead_settings

		source = inspect.getsource(palm_mill_dead_settings)
		self.assertIn("remove_dead_settings()", source)
		self.assertIn("from erpnext.palm_mill.dead_settings import", source)

	def test_the_patch_is_registered(self):
		"""An unregistered patch never runs, so every existing site -- the droplet
		included -- keeps the broken link while the code says otherwise."""
		import os

		import erpnext

		patches = os.path.join(os.path.dirname(erpnext.__file__), "patches.txt")
		with open(patches) as f:
			self.assertIn("erpnext.patches.v17_0.palm_mill_dead_settings", f.read())
