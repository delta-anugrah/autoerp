# Copyright (c) 2026, AutoERP and contributors
# For license information, please see license.txt

"""Settings links a palm mill cannot use, removed from the AutoERP Settings sidebar.

Two separate problems, both in `workspace_sidebar/*.json`:

1. `Repost Accounting Ledger Settings` points at a DocType that does not exist on this
   fork -- not renamed, not moved, simply absent. Clicking it is an error page. It sat
   in two sidebars, AutoERP Settings and Accounts Setup.

2. Eleven settings pages for modules the mill does not run: Selling, Buying,
   Manufacturing, Projects, CRM, Support, POS, Subscription, Delivery, Item Variant
   and Appointment Booking. We hid those modules' icons from the Desk; their settings
   pages stayed behind in the one sidebar an owner is most likely to open.

The JSON files are the source of truth and are edited alongside this module. This
function exists because editing them is not sufficient on its own: `sync.py` imports
app-level entities by upserting the parent and its rows, and `remove_orphan_entities`
only deletes a whole sidebar whose file has vanished. A child row dropped from the
file is left in the database, so an existing site keeps showing every link this
module was written to remove -- including the broken one.

Applied idempotently from `after_install` (harmless there, the fresh import already
matches the files) and from the `palm_mill_dead_settings` patch, which is the call
that actually matters.
"""

import frappe

# (sidebar, link_to) pairs to drop. Keyed by `link_to` rather than label because the
# label is translated and a site in Indonesian would not match an English string.
DEAD_LINKS = {
	"AutoERP Settings": (
		# Points at a DocType that does not exist on this fork; clicking it errors.
		"Repost Accounting Ledger Settings",
		# Modules the mill does not run. Kept: Global Defaults, System Settings,
		# Accounts Settings, Stock Settings, Currency Exchange, Stock Reposting.
		"POS Settings",
		"Selling Settings",
		"Buying Settings",
		"Manufacturing Settings",
		"Projects Settings",
		"CRM Settings",
		"Support Settings",
		"Subscription Settings",
		"Item Variant Settings",
		"Delivery Settings",
		"Appointment Booking Settings",
	),
	"Accounts Setup": ("Repost Accounting Ledger Settings",),
}


def remove_dead_settings() -> dict:
	"""Idempotent: deletes the listed child rows where they are still present.

	Returns what it removed, so the caller can print it -- the same reason
	`hide_unused_roles` reports.
	"""
	removed, absent = [], []

	for sidebar, links in DEAD_LINKS.items():
		if not frappe.db.exists("Workspace Sidebar", sidebar):
			absent.append(sidebar)
			continue

		doc = frappe.get_doc("Workspace Sidebar", sidebar)
		keep = [item for item in doc.items if (item.link_to or "") not in links]
		if len(keep) == len(doc.items):
			continue  # already clean

		doomed = [item for item in doc.items if (item.link_to or "") in links]
		doc.items = keep
		orphaned_sections = _drop_empty_sections(doc)

		# Deleted explicitly. `db_update_all` only rewrites the rows still attached --
		# it has no concept of a row that went away -- so dropping them from `doc.items`
		# alone would leave every one of them in `tabWorkspace Sidebar Item` and change
		# nothing on screen. That is exactly how editing the JSON files by itself failed.
		for item in doomed + orphaned_sections:
			frappe.db.delete("Workspace Sidebar Item", {"name": item.name})

		# The survivors keep their renumbered idx. Not `save`: these are `standard`
		# records, and saving one marks it customised, after which the next migrate stops
		# syncing it from the file -- the JSON has to stay the source of truth.
		doc.db_update_all()
		removed.extend(f"{sidebar}: {item.link_to}" for item in doomed)

	if removed:
		frappe.clear_cache()

	return {"removed": removed, "absent": absent}


def _drop_empty_sections(doc):
	"""A Section Break with no Link left under it draws as a heading over nothing.

	`Other Settings` in AutoERP Settings loses four of its six links here, so this is a
	real case rather than a defensive one.

	Returns the section rows it removed, so the caller can delete them too -- they are
	rows in the same child table and stay behind just like any other.
	"""
	items, out, dropped = doc.items, [], []
	for index, item in enumerate(items):
		if item.type == "Section Break" and not any(r.type == "Link" for r in items[index + 1 :]):
			dropped.append(item)
			continue
		out.append(item)
	for position, item in enumerate(out, start=1):
		item.idx = position
	doc.items = out
	return dropped
