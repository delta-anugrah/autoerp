# Copyright (c) 2026, AutoERP and Contributors
# See license.txt

"""Native fields a palm mill never fills in, and the wiring that keeps them hidden.

The fields are ERPNext's own — `is_return`, `per_transferred`, the Stock Entry
warehouse defaults. They cannot be deleted: ERPNext writes them itself, and editing
core DocType JSON conflicts on every upstream pull. Hiding them is reversible and
touches only the form layout.

The failure this guards against is quiet. A Property Setter that does not get applied
leaves an operator staring at a "Is Return" checkbox on an FFB receipt, and nothing in
any log says the setup step was skipped.
"""

import frappe
from frappe.tests import IntegrationTestCase

from erpnext.palm_mill import hidden_fields, setup


class IntegrationTestHiddenFields(IntegrationTestCase):
	def tearDown(self):
		# Leaving these applied would hide the fields for every later test on this site.
		hidden_fields.hide_unused_fields()
		super().tearDown()

	def test_every_listed_field_is_hidden_on_the_form(self):
		hidden_fields.hide_unused_fields()

		for doctype, fieldname, _reason in hidden_fields.HIDDEN_FIELDS:
			meta_field = frappe.get_meta(doctype).get_field(fieldname)
			self.assertIsNotNone(meta_field, f"{doctype}.{fieldname} vanished upstream")
			self.assertTrue(meta_field.hidden, f"{doctype}.{fieldname} still shows on the form")

	def test_hidden_fields_also_leave_the_list_view_and_the_filter_row(self):
		"""`hidden` governs the form only. The list view builds its columns from
		`in_list_view` and its filter row from `in_standard_filter`, so a field hidden on
		the form alone comes back as an empty column and a filter nobody can use."""
		hidden_fields.hide_unused_fields()

		for doctype, fieldname, _reason in hidden_fields.HIDDEN_FIELDS:
			meta_field = frappe.get_meta(doctype).get_field(fieldname)
			self.assertFalse(meta_field.in_list_view, f"{doctype}.{fieldname} in list view")
			self.assertFalse(meta_field.in_standard_filter, f"{doctype}.{fieldname} in the filter row")

	def test_applying_it_twice_does_not_duplicate_property_setters(self):
		"""`after_install` and the patch both call this, so a site can see it more than
		once — on install, then again on the next migrate."""
		hidden_fields.hide_unused_fields()
		before = self._property_setter_names()

		hidden_fields.hide_unused_fields()

		self.assertEqual(before, self._property_setter_names())

	def test_a_field_upstream_removed_is_skipped_rather_than_crashing(self):
		"""These are upstream's fields, and upstream renames things. A missing one must
		not take the whole install down with it."""
		original = hidden_fields.HIDDEN_FIELDS
		hidden_fields.HIDDEN_FIELDS = (
			*original,
			("Stock Entry", "custom_field_that_does_not_exist", "gone upstream"),
		)
		try:
			hidden_fields.hide_unused_fields()
		finally:
			hidden_fields.HIDDEN_FIELDS = original

	def test_the_install_hook_hides_them(self):
		"""If this falls out of `after_install`, a new site — production included — comes
		up with every one of these fields visible and nothing says so."""
		import inspect

		self.assertIn("hide_unused_fields()", inspect.getsource(setup.after_install))

	def test_the_patch_calls_the_same_code_as_the_hook(self):
		"""Two copies of this list would drift, and the patch copy is the one nobody
		looks at until a site is already wrong."""
		import inspect

		from erpnext.patches.v17_0 import palm_mill_hidden_fields

		source = inspect.getsource(palm_mill_hidden_fields)
		self.assertIn("hide_unused_fields()", source)
		self.assertIn("from erpnext.palm_mill.hidden_fields import", source)

	def _property_setter_names(self):
		return sorted(
			frappe.get_all(
				"Property Setter",
				filters={"doc_type": ("in", [d for d, _f, _r in hidden_fields.HIDDEN_FIELDS])},
				pluck="name",
			)
		)
