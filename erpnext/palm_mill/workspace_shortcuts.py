# Copyright (c) 2026, AutoERP and contributors
# For license information, please see license.txt

"""Puts AutoGrade Licence into the Palm Mill workspace — sidebar and shortcut.

**Why this is not just the fixture.** `bench migrate` imports a workspace fixture
only when the site does not already have that workspace. Every site that ran an
earlier version has one, so editing
`workspace/pabrik_kelapa_sawit/pabrik_kelapa_sawit.json` alone reaches new sites
and nobody else — proven on `test_site`: after migrate the shortcut count was
still 0. The same trap bit the Desk menu cleanup (autoerp #32), which is why that
one shipped a patch too.

The fixture is still edited, and it is still the source of truth for a **new**
site. This only catches up the ones that already exist.

**Two separate places, and they are not the same thing.** The left-hand menu is a
`Workspace Sidebar` document, while `shortcuts` draws the cards in the body of the
page. Adding only the shortcut — which is what shipped in v1.0.5 — leaves the menu
without an entry, so the only way in is still to know the name and type it into
search. Both are written here.
"""

import json

import frappe

WORKSPACE = "Pabrik Kelapa Sawit"
# Nama dokumennya, bukan nama berkas fixture: `pabrik_kelapa_sawit.json` menyimpan
# `"name": "Pabrik Kelapa Sawit"`. Salah satu huruf di sini membuat semuanya
# pulang lebih awal tanpa mengubah apa pun, dan test yang menyaring dengan
# `skipTest` akan ikut diam.
SIDEBAR = "Pabrik Kelapa Sawit"
LABEL = "AutoGrade Licences"
LINK_TO = "AutoGrade Licence"
# Sits right after the operators shortcut, so the two AutoGrade errands are
# side by side rather than scattered through the Documents row.
AFTER = "AutoGrade Operator"


def ensure_licence_entries() -> bool:
	"""Both the menu entry and the shortcut. Returns True if anything changed."""
	sidebar = ensure_licence_sidebar_item()
	shortcut = ensure_licence_shortcut()
	return sidebar or shortcut


def ensure_licence_sidebar_item() -> bool:
	"""The entry in the left-hand menu, under Mill Settings.

	This is the one people actually use to find things; the shortcut is a card
	further down the page. They live in different doctypes, so neither implies
	the other.
	"""
	if not frappe.db.exists("Workspace Sidebar", SIDEBAR):
		return False

	if not frappe.db.exists("DocType", LINK_TO):
		return False

	doc = frappe.get_doc("Workspace Sidebar", SIDEBAR)

	if any(i.link_to == LINK_TO for i in doc.items):
		return False

	position = next((n for n, i in enumerate(doc.items) if i.link_to == AFTER), len(doc.items) - 1)
	doc.append(
		"items",
		{
			"type": "Link",
			"label": LABEL,
			"link_to": LINK_TO,
			"link_type": "DocType",
			"child": 1,
			"collapsible": 1,
			"indent": 0,
			"keep_closed": 0,
			"show_arrow": 0,
		},
	)
	# `append` puts it last, which would drop it under Accounting Dimensions —
	# a different section entirely. Move it next to the operators entry.
	doc.items.insert(position + 1, doc.items.pop())
	for n, row in enumerate(doc.items, start=1):
		row.idx = n

	doc.save(ignore_permissions=True)
	return True


def ensure_licence_shortcut() -> bool:
	"""Add the shortcut if it is missing. Returns True when something changed.

	Idempotent: safe to run on every migrate, and safe to run on a site that
	already has it (a new site gets it from the fixture).
	"""
	if not frappe.db.exists("Workspace", WORKSPACE):
		# A site whose workspace was never created, or one where it was deleted
		# on purpose. Creating it here would resurrect something somebody removed.
		return False

	if not frappe.db.exists("DocType", LINK_TO):
		# The DocType ships in the same release as this patch, so this only
		# happens on a half-applied install. Better silent than a broken link.
		return False

	doc = frappe.get_doc("Workspace", WORKSPACE)

	if any(s.link_to == LINK_TO for s in doc.shortcuts):
		return False

	position = next((n for n, s in enumerate(doc.shortcuts) if s.link_to == AFTER), len(doc.shortcuts) - 1)
	doc.append("shortcuts", {"type": "DocType", "label": LABEL, "link_to": LINK_TO, "color": "Grey"})
	# `append` puts it last; move it next to the operators shortcut.
	doc.shortcuts.insert(position + 1, doc.shortcuts.pop())
	for n, row in enumerate(doc.shortcuts, start=1):
		row.idx = n

	doc.content = _content_with_shortcut(doc.content)
	doc.save(ignore_permissions=True)
	return True


def _content_with_shortcut(raw: str) -> str:
	"""Insert the card into the rendered layout.

	The shortcuts table decides what exists; `content` decides what is drawn and
	in which order. A shortcut missing from `content` simply never appears — no
	error, no empty slot — so both have to be written together.
	"""
	try:
		blocks = json.loads(raw or "[]")
	except (ValueError, TypeError):
		return raw

	if any(b.get("data", {}).get("shortcut_name") == LABEL for b in blocks):
		return raw

	card = {"id": "licenceShortcut", "type": "shortcut", "data": {"shortcut_name": LABEL, "col": 3}}

	for n, block in enumerate(blocks):
		if (
			block.get("type") == "shortcut"
			and block.get("data", {}).get("shortcut_name") == "AutoGrade Operators"
		):
			blocks.insert(n + 1, card)
			break
	else:
		blocks.append(card)

	return json.dumps(blocks)
