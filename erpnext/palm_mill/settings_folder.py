# Copyright (c) 2026, AutoERP and contributors
# For license information, please see license.txt

"""Organization and AutoERP Settings, gathered into one "Pengaturan" folder.

The Desk home showed four icons of equal weight: Palm Oil Mill, Accounting,
Organization and AutoERP Settings. They are not of equal weight. Palm Oil Mill is
opened every shift; Accounting monthly; the other two are set up once and then
essentially never touched again.

Putting the two setup icons behind one folder leaves the Desk saying three distinct
things -- daily work, money, setup -- instead of four flat choices the operator has to
read before picking the one that is always the same.

Nothing is hidden and nothing is removed: both screens stay one click further in, the
way Invoicing and Payments already live under Accounting. That folder is the pattern
this copies.

`desktop_icon/pengaturan.json` and the two reparented icons are the source of truth.
This function exists because the JSON alone does not reach a site that already exists:
`sync.py` upserts app-level entities but a site created before these files still has
both icons at the top level, and `create_desktop_icons` only inserts what is missing.

Applied idempotently from `after_install` and from the `palm_mill_settings_folder`
patch, which is the call that matters for the droplet.
"""

import frappe

FOLDER = "Pengaturan"
# The icons that move under it, in the order they should appear.
CHILDREN = ("Organization", "AutoERP Settings")


def group_settings_icons() -> dict:
	"""Idempotent: creates the folder if missing and reparents the two icons.

	Returns what it did, so the caller can print it -- the same reason
	`hide_unused_roles` reports.
	"""
	created, moved, absent = False, [], []

	if not frappe.db.exists("Desktop Icon", FOLDER):
		# Mirrors `desktop_icon/pengaturan.json`. A site that has the file already got
		# this from the sync; one that does not is mid-upgrade and needs it now, because
		# reparenting onto a folder that does not exist drops both icons off the Desk
		# entirely -- `build_folder_map` only keeps a child whose parent it can see.
		frappe.get_doc(
			{
				"doctype": "Desktop Icon",
				"name": FOLDER,
				"label": FOLDER,
				"icon": "setting",
				"icon_type": "Folder",
				"link_type": "Workspace Sidebar",
				"link_to": "",
				"app": "erpnext",
				"standard": 1,
				"hidden": 0,
				"idx": 3,
			}
		).insert(ignore_permissions=True)
		created = True

	for position, name in enumerate(CHILDREN, start=1):
		if not frappe.db.exists("Desktop Icon", name):
			absent.append(name)
			continue
		if frappe.db.get_value("Desktop Icon", name, "parent_icon") == FOLDER:
			continue
		frappe.db.set_value(
			"Desktop Icon",
			name,
			{"parent_icon": FOLDER, "idx": position},
			update_modified=False,
		)
		moved.append(name)

	if created or moved:
		# `get_desktop_icons` caches per user under the `desktop_icons` hash.
		frappe.cache.delete_key("desktop_icons")
		frappe.clear_cache()

	return {"created": created, "moved": moved, "absent": absent}
