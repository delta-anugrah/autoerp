# Copyright (c) 2026, AutoERP and Contributors
# See license.txt

"""What the Truck screen shows backoffice, pinned so a refactor cannot quietly undo it.

These are the parts of the screen that are decided in Python and JSON rather than in
the browser: which fields are hidden, which scripts Desk loads, and what the dialog's
endpoint returns. The browser behaviour itself (the dialog, the relabelled dropdown)
is covered by `tests/e2e` in AutoGrade's sense only as far as the data it renders.
"""

import pathlib
import re

import frappe
from frappe.tests import IntegrationTestCase

from erpnext.palm_mill.test_fixtures import PLASMA_SUPPLIER, make_truck, setup_palm_mill

EXTRA_TEST_RECORD_DEPENDENCIES = ["Supplier"]

APP_ROOT = pathlib.Path(frappe.get_app_path("erpnext"))
DIALOG_JS = APP_ROOT / "public" / "js" / "palm_mill" / "qr_cards_dialog.js"

# The three read-only fields the server writes, plus the section and column that hold
# them. Hidden because nobody types them; `plate_normalized` in particular is set in
# Truck.validate(), so hiding it must not stop it being filled.
INTEGRATION_FIELDS = {
	"integration_section",
	"plate_normalized",
	"autograde_id",
	"integration_column",
	"source",
}

# What backoffice does own, and must keep seeing.
OPERATIONAL_FIELDS = {"plate_number", "supplier", "vehicle_class", "driver_name"}


class IntegrationTestTruckScreen(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		setup_palm_mill()

	def test_integration_fields_are_hidden_and_the_rest_are_not(self):
		"""Backoffice sees the four fields they own, and none of the plumbing."""
		meta = frappe.get_meta("Truck")
		hidden = {f.fieldname for f in meta.fields if f.hidden}

		self.assertEqual(hidden & INTEGRATION_FIELDS, INTEGRATION_FIELDS)
		self.assertEqual(hidden & OPERATIONAL_FIELDS, set())

	def test_hiding_the_field_does_not_stop_the_plate_key_being_written(self):
		"""The reason this test exists: `plate_normalized` is the cross-system truck key.

		It is set in `validate()`, not by the form, so hiding it is safe - but if someone
		ever moves that assignment into a client script, every truck saved from Desk
		would silently lose its AutoGrade match.
		"""
		truck = make_truck("B 4242 HID", PLASMA_SUPPLIER)

		self.assertEqual(frappe.db.get_value("Truck", truck.name, "plate_normalized"), "B4242HID")

	def test_desk_loads_the_card_dialog_for_both_form_and_list(self):
		"""One file, two entry points. If either hook is dropped the button throws
		`erpnext.palm_mill.show_qr_cards is not a function` - and only in the browser,
		where no Python test would ever see it."""
		script = "public/js/palm_mill/qr_cards_dialog.js"

		self.assertIn(script, frappe.get_hooks("doctype_js").get("Truck", []))
		self.assertIn(script, frappe.get_hooks("doctype_list_js").get("Truck", []))
		self.assertTrue(DIALOG_JS.exists(), f"{DIALOG_JS} is registered but missing")

	def test_dialog_calls_a_whitelisted_method_that_exists(self):
		"""The dialog names its endpoint in a string; a rename would break it silently."""
		called = set(re.findall(r'method:\s*"([^"]+)"', DIALOG_JS.read_text()))
		self.assertTrue(called, "the dialog calls no method at all - did the call move?")

		for dotted in called:
			# Frappe records the decorator in a registry, not as an attribute on the
			# function, so membership of `frappe.whitelisted` is what actually decides
			# whether the browser is allowed to call it.
			method = frappe.get_attr(dotted)
			self.assertIn(
				method,
				frappe.whitelisted,
				f"{dotted} is called from the browser but is not @frappe.whitelist()",
			)

	def test_the_dialog_prints_from_an_iframe_not_the_desk_page(self):
		"""`window.print()` on Desk puts the sidebar and navbar on the paper. The cards
		are printed from an iframe that holds nothing else."""
		# Comments are stripped first: the file explains at length why `window.print()`
		# is the wrong call, and a plain substring search would trip over that
		# explanation and fail for the very reason the code is correct.
		source = DIALOG_JS.read_text()
		code = re.sub(r"//[^\n]*", "", source)

		self.assertIn('createElement("iframe")', code)
		self.assertIn("contentWindow.print()", code)
		self.assertNotIn("window.print()", code)

	def test_relabelling_the_blank_option_pins_its_value_first(self):
		"""Two real bugs found in a browser, neither visible to a Python assertion.

		1. Frappe renders the blank choice as a bare `<option></option>` with **no value
		   attribute**, so `option[value=""]` never matches and the relabel silently
		   does nothing at all.
		2. An `<option>` with no value attribute takes its value from its own text, so
		   relabelling without pinning the attribute first turns the submitted value
		   into "Lainnya / belum dicatat" - writing the label into the database, the
		   exact thing this relabel exists to prevent.

		Pinned by reading the source because the DOM is where the mistake lives; a
		screen test would catch it too, but this repo has no browser test runner.
		"""
		source = (APP_ROOT / "palm_mill" / "doctype" / "truck" / "truck.js").read_text()
		code = re.sub(r"//[^\n]*", "", source)

		self.assertNotIn(
			'option[value=""]', code, "an attribute selector never matches Frappe's blank option"
		)
		self.assertIn('setAttribute("value", "")', code, "the blank option's value must be pinned")

		# ...and pinned BEFORE the text is replaced, or the value is already wrong.
		self.assertLess(
			code.index('setAttribute("value", "")'),
			code.index("textContent ="),
			"the value must be pinned before the label is changed",
		)

	def test_printed_card_carries_no_document_title(self):
		"""Chrome prints the document title in the page header, and the card is cut out
		and stuck on a windscreen - a title across the top is rubbish on it."""
		code = re.sub(r"//[^\n]*", "", DIALOG_JS.read_text())

		self.assertIn("<title></title>", code)

	def test_the_blank_vehicle_class_is_relabelled_without_changing_stored_values(self):
		"""A blank first option reads like a rendering fault, so it is relabelled - but
		in the browser only. Writing a literal value into the options would give two
		ways of saying "not recorded" and split every report in two.
		"""
		options = frappe.get_meta("Truck").get_field("vehicle_class").options.split("\n")
		self.assertEqual(options[0], "", "the stored blank option must stay blank")

		# Inserted directly rather than through `make_truck`, which always fills in a
		# class - the point here is exactly what a truck saved WITHOUT one stores.
		truck = frappe.get_doc(
			{"doctype": "Truck", "plate_number": "B 4343 BLK", "supplier": PLASMA_SUPPLIER}
		).insert()
		self.assertEqual(frappe.db.get_value("Truck", truck.name, "vehicle_class"), "")
