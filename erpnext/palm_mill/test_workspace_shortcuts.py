# Copyright (c) 2026, AutoERP and Contributors
# See license.txt

"""The licence shortcut has to reach sites that already exist.

`bench migrate` imports a workspace fixture only when the site has no workspace by
that name, so editing the JSON alone reaches new sites and nobody else. Measured on
`test_site`: after a full migrate the shortcut count was still 0. That is what the
patch is for, and what these tests pin.
"""

import json

import frappe
from frappe.tests import IntegrationTestCase

from erpnext.palm_mill.workspace_shortcuts import (
	AFTER,
	LABEL,
	LINK_TO,
	WORKSPACE,
	ensure_licence_shortcut,
)


class IntegrationTestWorkspaceShortcut(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		if not frappe.db.exists("Workspace", WORKSPACE):
			self.skipTest(f"{WORKSPACE} workspace not installed on this site")
		self.addCleanup(frappe.db.rollback)

	def _remove_shortcut(self):
		"""Put the workspace back to how a pre-licence site looks."""
		doc = frappe.get_doc("Workspace", WORKSPACE)
		doc.shortcuts = [s for s in doc.shortcuts if s.link_to != LINK_TO]
		blocks = [
			b for b in json.loads(doc.content or "[]") if b.get("data", {}).get("shortcut_name") != LABEL
		]
		doc.content = json.dumps(blocks)
		doc.save(ignore_permissions=True)
		return doc

	def test_adds_the_shortcut_to_an_existing_workspace(self):
		self._remove_shortcut()

		self.assertTrue(ensure_licence_shortcut())

		doc = frappe.get_doc("Workspace", WORKSPACE)
		self.assertIn(LINK_TO, [s.link_to for s in doc.shortcuts])

	def test_shortcut_also_lands_in_the_drawn_layout(self):
		"""The shortcuts table says what exists; `content` says what is drawn.

		A shortcut missing from `content` never appears — no error, no gap — so
		writing only one of the two looks like the patch did nothing.
		"""
		self._remove_shortcut()
		ensure_licence_shortcut()

		blocks = json.loads(frappe.db.get_value("Workspace", WORKSPACE, "content") or "[]")
		names = [b.get("data", {}).get("shortcut_name") for b in blocks if b.get("type") == "shortcut"]
		self.assertIn(LABEL, names)

	def test_sits_next_to_the_operators_shortcut(self):
		"""Both AutoGrade errands together, rather than scattered."""
		self._remove_shortcut()
		ensure_licence_shortcut()

		doc = frappe.get_doc("Workspace", WORKSPACE)
		links = [s.link_to for s in doc.shortcuts]
		if AFTER in links:
			self.assertEqual(links.index(LINK_TO), links.index(AFTER) + 1)

	def test_running_twice_changes_nothing(self):
		"""Patches re-run on every migrate; a second copy would be a visible bug."""
		self._remove_shortcut()
		ensure_licence_shortcut()

		self.assertFalse(ensure_licence_shortcut())

		doc = frappe.get_doc("Workspace", WORKSPACE)
		self.assertEqual([s.link_to for s in doc.shortcuts].count(LINK_TO), 1)

		blocks = json.loads(doc.content or "[]")
		names = [b.get("data", {}).get("shortcut_name") for b in blocks]
		self.assertEqual(names.count(LABEL), 1)

	def test_does_nothing_when_the_workspace_is_absent(self):
		"""Somebody deleted it on purpose. Recreating it here would undo that."""
		original = frappe.db.exists("Workspace", "Tidak Ada Workspace Ini")
		self.assertFalse(original)

		import erpnext.palm_mill.workspace_shortcuts as mod

		saved = mod.WORKSPACE
		mod.WORKSPACE = "Tidak Ada Workspace Ini"
		try:
			self.assertFalse(ensure_licence_shortcut())
		finally:
			mod.WORKSPACE = saved

	def test_fixture_and_code_agree_on_the_label(self):
		"""If the JSON and this module drift, a new site and an upgraded site get
		different workspaces — and nothing fails to say so."""
		import pathlib

		import erpnext

		fixture = (
			pathlib.Path(erpnext.__file__).parent
			/ "palm_mill/workspace/pabrik_kelapa_sawit/pabrik_kelapa_sawit.json"
		)
		data = json.loads(fixture.read_text())

		labels = {s["label"] for s in data["shortcuts"] if s.get("link_to") == LINK_TO}
		self.assertEqual(labels, {LABEL})

		drawn = [
			b.get("data", {}).get("shortcut_name")
			for b in json.loads(data["content"])
			if b.get("type") == "shortcut"
		]
		self.assertIn(LABEL, drawn)
