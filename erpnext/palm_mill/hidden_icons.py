# Copyright (c) 2026, AutoERP and contributors
# For license information, please see license.txt

"""Desk icons a palm mill never opens, hidden instead of deleted.

This is the layer the operator actually sees. Frappe v16 draws the Desk home as a
grid of `Desktop Icon` records -- folders like `Framework` and `Accounting` with
links underneath -- and that grid is built client-side in `sidebar_header.js`
(`build_folder_map`), which skips any icon whose `hidden` is set.

Not to be confused with `Workspace.is_hidden`. That one governs the older left-hand
workspace list and has no effect on this grid, and the two do not even carry the same
records: `Workspace Sidebar`, which the icons link to, has no `is_hidden` field at
all. Hiding a workspace and hiding its icon are separate jobs; this module does the
one the customer complained about.

ERPNext already ships most of what a mill does not need as `hidden: 1` -- Selling,
Stock, CRM, Manufacturing and a dozen more arrive hidden. What is left visible and
still useless to a mill is Frappe's own `Framework` folder and its nine links.

Hiding rather than deleting, for the same reason as `hidden_fields`: these are
upstream's records, recreated by `create_desktop_icons` on install and migrate.
Deleting them means they come back on the next migrate, and `hidden` survives
because that function only inserts what is missing.

Applied idempotently from `after_install` and from the `palm_mill_hidden_icons`
patch. `hidden` is a column on the site's own rows, not a file this app ships, so an
existing site -- the droplet included -- changes only when the patch runs.
"""

import frappe

# (icon, why a palm mill never opens it)
#
# Named rather than derived. A rule like "hide everything from the frappe app" would
# swallow whatever the next Frappe version adds, including something a mill turns out
# to need. A list is auditable and its failures are visible.
HIDDEN_ICONS = (
	# Frappe's own developer and administration tooling. `Framework` is the folder; the
	# nine below are the links inside it. The folder alone is not enough -- its children
	# are separate rows, and an icon whose parent is hidden is still its own record.
	("Framework", "Frappe's developer tooling folder, not a mill screen"),
	("Build", "the app builder: DocTypes, scripts, workflows"),
	("Data", "import/export tooling for developers"),
	("System", "server settings, logs, background jobs"),
	("Users", "user administration belongs to the owner, not the Desk home"),
	("Website", "the site serves the Desk only; there is no public web presence"),
	("Printing", "print formats are set up once, not visited"),
	("Email", "the mill does not send mail from the ERP"),
	("Automation", "assignment rules and auto-repeat a mill never configures"),
	("Integrations", "Google/Dropbox/S3 connectors a mill never wires up"),
	# ERPNext accounting the mill does not run. What it does run -- Invoicing,
	# Payments, Financial Reports, Taxes, Accounts Setup -- stays.
	("Subcontracting", "nothing is subcontracted out"),
)


def hide_unused_icons() -> dict:
	"""Idempotent: sets `hidden` on each listed Desktop Icon that exists.

	Writes with `update_modified=False` and only when the value actually changes, so a
	re-run is a no-op rather than a fresh modification timestamp on eleven rows.

	Returns what it did, so the caller can print it. A step that changes eleven rows
	and says nothing is one nobody can audit afterwards -- the same reason
	`hide_unused_roles` reports.
	"""
	hidden, already, absent = [], [], []

	for name, _reason in HIDDEN_ICONS:
		if not frappe.db.exists("Desktop Icon", name):
			# Upstream renamed or dropped it, or the app that owned it is not installed.
			# Not an error: the icon is off the Desk either way.
			absent.append(name)
			continue
		if frappe.db.get_value("Desktop Icon", name, "hidden"):
			already.append(name)
			continue
		frappe.db.set_value("Desktop Icon", name, "hidden", 1, update_modified=False)
		hidden.append(name)

	if hidden:
		# `get_desktop_icons` caches per user under the `desktop_icons` hash. Without
		# this the mill keeps seeing the old grid until something else clears it.
		frappe.cache.delete_key("desktop_icons")
		frappe.clear_cache()

	return {"hidden": hidden, "already": already, "absent": absent}
