# Copyright (c) 2026, AutoERP and Contributors
# See license.txt

"""Desk icons a palm mill never opens, and the wiring that keeps them hidden.

These tests exist because an earlier attempt at this hid the wrong thing. It set
`Workspace.is_hidden`, measured `get_workspaces()`, got convincing numbers, and
changed nothing at all on the screen the customer was looking at -- the Desk home
grid is built from `Desktop Icon` rows, a different layer entirely.

So the first test here is the one that would have caught that: it asserts against the
same field `sidebar_header.js` reads when it draws the grid. The rest pin the
opposite failure, which is quieter and worse: hiding something the mill does need
looks to the customer like a feature that was never built.
"""

import frappe
from frappe.tests import IntegrationTestCase

from erpnext.palm_mill import hidden_icons, setup
from erpnext.palm_mill.hidden_icons import HIDDEN_ICONS, hide_unused_icons

# What the mill works from. Anything here must never appear in HIDDEN_ICONS.
#
# `Pabrik Kelapa Sawit` is the mill itself. The four accounting icons are what the
# workspace's own number cards read -- payables, receivables, sales -- and the two
# `AutoERP`/`Organization` entries are where the owner sets the site up.
KEPT_ICONS = (
	"Pabrik Kelapa Sawit",
	"Invoicing",
	"Payments",
	"Financial Reports",
	"Taxes",
	"Accounts Setup",
	"Accounting",
	"Organization",
	"AutoERP Settings",
	"My Workspaces",
)


class IntegrationTestHiddenIcons(IntegrationTestCase):
	def tearDown(self):
		# These tests un-hide icons to prove the result is reversible. Leaving one
		# visible would hand the next test on this site a Desk it did not expect.
		hide_unused_icons()
		super().tearDown()

	def test_every_listed_icon_is_hidden(self):
		hide_unused_icons()

		for name, reason in HIDDEN_ICONS:
			if not frappe.db.exists("Desktop Icon", name):
				continue  # upstream dropped it; nothing to hide
			self.assertTrue(
				frappe.db.get_value("Desktop Icon", name, "hidden"),
				f"{name} is still on the Desk ({reason})",
			)

	def test_it_hides_the_field_the_desk_actually_reads(self):
		"""The mistake this guards against, stated plainly.

		`sidebar_header.js` builds the icon grid from `Desktop Icon` and skips a row on
		`!icon.hidden`. An earlier version of this work set `Workspace.is_hidden`
		instead, which governs a different list and left the Desk unchanged. If someone
		"simplifies" this back onto Workspace, this fails.
		"""
		hide_unused_icons()

		meta = frappe.get_meta("Desktop Icon")
		self.assertIsNotNone(meta.get_field("hidden"), "Desktop Icon lost its `hidden` field")

		framework = frappe.get_value("Desktop Icon", "Framework", "hidden")
		self.assertTrue(framework, "Framework still draws on the Desk home")

	def test_the_icons_the_mill_works_from_are_not_hidden(self):
		"""The expensive mistake in the other direction."""
		listed = [name for name, _reason in HIDDEN_ICONS]

		for name in KEPT_ICONS:
			self.assertNotIn(name, listed, f"{name} is one the mill works from")

		hide_unused_icons()

		for name in KEPT_ICONS:
			if not frappe.db.exists("Desktop Icon", name):
				continue
			self.assertFalse(
				frappe.db.get_value("Desktop Icon", name, "hidden"),
				f"{name} vanished from the Desk",
			)

	def test_the_mill_icon_survives(self):
		"""Hiding everything else is only safe while the one screen that replaces them
		is still there. If this fails the site has no usable Desk at all."""
		hide_unused_icons()

		self.assertTrue(frappe.db.exists("Desktop Icon", "Pabrik Kelapa Sawit"))
		self.assertFalse(frappe.db.get_value("Desktop Icon", "Pabrik Kelapa Sawit", "hidden"))

	def test_the_framework_folder_and_its_children_are_hidden_together(self):
		"""A folder and the links inside it are separate rows. Hiding the folder alone
		leaves nine orphans that still match on `app` and still draw."""
		hide_unused_icons()

		children = frappe.get_all(
			"Desktop Icon", filters={"parent_icon": "Framework"}, fields=["name", "hidden"]
		)
		self.assertTrue(children, "Framework has no children; the fixture changed")
		for child in children:
			self.assertTrue(child.hidden, f"{child.name} still draws under a hidden folder")

	def test_hiding_an_icon_changes_no_permission(self):
		"""`hidden` is read by the Desk when it draws, and nowhere else. Anything the
		mill workspace links to stays reachable."""
		hide_unused_icons()

		for doctype in ("User", "Stock Entry", "Purchase Receipt", "Sales Invoice"):
			self.assertTrue(
				frappe.has_permission(doctype, "read", user="Administrator"),
				f"hiding an icon took away {doctype}",
			)

	def test_applying_it_twice_reports_nothing_left_to_do(self):
		"""`after_install` and the patch both call this, so a site sees it more than
		once -- on install, then again on the next migrate."""
		hide_unused_icons()

		second = hide_unused_icons()

		self.assertEqual(second["hidden"], [], "re-running hid something a second time")

	def test_it_reports_what_it_hid(self):
		"""A step that changes eleven rows and says nothing cannot be audited."""
		present = [n for n, _r in HIDDEN_ICONS if frappe.db.exists("Desktop Icon", n)]
		for name in present:
			frappe.db.set_value("Desktop Icon", name, "hidden", 0, update_modified=False)

		result = hide_unused_icons()

		self.assertEqual(sorted(result["hidden"]), sorted(present))

	def test_an_icon_upstream_removed_is_skipped_rather_than_crashing(self):
		"""These are upstream's records, and upstream renames things. A missing one must
		not take the whole install down with it."""
		original = hidden_icons.HIDDEN_ICONS
		hidden_icons.HIDDEN_ICONS = (*original, ("Icon That Does Not Exist", "gone upstream"))
		try:
			result = hide_unused_icons()
			self.assertIn("Icon That Does Not Exist", result["absent"])
		finally:
			hidden_icons.HIDDEN_ICONS = original

	def test_hiding_is_reversible(self):
		"""Hiding rather than deleting is the whole point: the owner can put one back
		without reinstalling anything."""
		hide_unused_icons()

		frappe.db.set_value("Desktop Icon", "Users", "hidden", 0, update_modified=False)

		self.assertFalse(frappe.db.get_value("Desktop Icon", "Users", "hidden"))

	def test_the_install_hook_hides_them(self):
		"""If this falls out of `after_install`, a new site -- production included --
		comes up with the full Desk and nothing says so."""
		import inspect

		self.assertIn("hide_unused_icons()", inspect.getsource(setup.after_install))

	def test_the_patch_calls_the_same_code_as_the_hook(self):
		"""Two copies of this list would drift, and the patch copy is the one nobody
		looks at until a site is already wrong."""
		import inspect

		from erpnext.patches.v17_0 import palm_mill_hidden_icons

		source = inspect.getsource(palm_mill_hidden_icons)
		self.assertIn("hide_unused_icons()", source)
		self.assertIn("from erpnext.palm_mill.hidden_icons import", source)

	def test_the_patch_is_registered(self):
		"""An unregistered patch never runs, so every existing site -- the droplet
		included -- keeps the old Desk while the code says otherwise."""
		import os

		import erpnext

		patches = os.path.join(os.path.dirname(erpnext.__file__), "patches.txt")
		with open(patches) as f:
			self.assertIn("erpnext.patches.v17_0.palm_mill_hidden_icons", f.read())
