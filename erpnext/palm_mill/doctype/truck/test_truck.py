# Copyright (c) 2026, AutoERP and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from erpnext.palm_mill.doctype.truck.truck import get_or_create_truck, get_truck_by_plate
from erpnext.palm_mill.test_fixtures import PLASMA_SUPPLIER, make_truck, setup_palm_mill
from erpnext.palm_mill.utils import canonical_plate, normalize_plate

EXTRA_TEST_RECORD_DEPENDENCIES = ["Supplier"]


class IntegrationTestTruck(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		setup_palm_mill()

	def test_plate_helpers(self):
		self.assertEqual(normalize_plate(" b-5455 dk "), "B5455DK")
		self.assertEqual(canonical_plate("bg9911zz"), "BG 9911 ZZ")
		self.assertEqual(canonical_plate("BE 4075 PP"), "BE 4075 PP")
		self.assertEqual(canonical_plate("unknown-1a2b"), "UNKNOWN-1A2B")

	def test_normalised_plate_is_unique(self):
		make_truck("B 1111 TT", PLASMA_SUPPLIER)
		self.assertEqual(get_truck_by_plate("b1111tt"), "B 1111 TT")
		self.assertRaises(frappe.DuplicateEntryError, make_truck, "B1111TT")

	def test_odd_plate_warns_but_still_saves(self):
		"""Backoffice has the last word: government and out-of-area plates are real.

		The warning exists to catch a typo while the record is still open - not to
		refuse the truck. Blocking here would leave a real truck unweighable.
		"""
		frappe.message_log = []
		truck = frappe.get_doc({"doctype": "Truck", "plate_number": "TRK-9100"}).insert()

		self.assertEqual(truck.name, "TRK-9100")
		self.assertTrue(
			any("not shaped like an Indonesian plate" in str(m) for m in frappe.message_log),
			f"no warning was shown: {frappe.message_log}",
		)

	def test_ordinary_plate_is_saved_without_a_warning(self):
		"""A warning on every truck is a warning nobody reads."""
		frappe.message_log = []
		make_truck("B 9200 OK", PLASMA_SUPPLIER)

		self.assertFalse(
			any("not shaped like an Indonesian plate" in str(m) for m in frappe.message_log),
			f"unexpected warning: {frappe.message_log}",
		)

	def test_completing_a_truck_stores_the_owner(self):
		truck = get_or_create_truck("bd 777 xx", source="AutoGrade", autograde_id="ag-1")
		self.assertEqual((truck.name, truck.source, truck.vehicle_class), ("BD 777 XX", "AutoGrade", ""))

		again = get_or_create_truck("BD777XX", source="Scale")
		self.assertEqual(again.name, truck.name)

		truck.update({"supplier": PLASMA_SUPPLIER, "vehicle_class": "Dump Truck"})
		truck.save()
		self.assertEqual(frappe.db.get_value("Truck", truck.name, "supplier"), PLASMA_SUPPLIER)
