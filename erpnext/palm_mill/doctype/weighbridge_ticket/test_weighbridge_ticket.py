# Copyright (c) 2026, AutoERP and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import change_settings

from erpnext.palm_mill.doctype.weighbridge_ticket.weighbridge_ticket import (
	finalize_due_tickets,
	make_stock_documents,
)
from erpnext.palm_mill.test_fixtures import (
	AGEN_SUPPLIER,
	BLOK,
	EXPECTED_PAYABLE,
	EXPECTED_POTONGAN,
	GRADING,
	PLASMA_SUPPLIER,
	PRICE,
	WAREHOUSE,
	make_ticket,
	make_truck,
	setup_palm_mill,
)

EXTRA_TEST_RECORD_DEPENDENCIES = ["Supplier", "Warehouse", "Price List", "Cost Center"]


class IntegrationTestWeighbridgeTicket(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		setup_palm_mill()
		make_truck("B 2001 PL", PLASMA_SUPPLIER)
		make_truck("B 2002 AG", AGEN_SUPPLIER)
		make_truck("B 2003 IN")

	def test_status_and_derivation(self):
		grading_only = make_ticket("B 2001 PL", gross=0, tare=0, grading=GRADING)
		self.assertEqual(grading_only.status, "Waiting Weight")
		self.assertFalse(grading_only.try_finalize())

		weight_only = make_ticket("B 2002 AG", time_in="09:00:00", time_out="09:30:00")
		self.assertEqual(weight_only.status, "Waiting Grading")
		self.assertEqual(
			(weight_only.net_weight_kg, weight_only.sumber_tbs, weight_only.supplier),
			(9160, "External", AGEN_SUPPLIER),
		)
		self.assertFalse(weight_only.try_finalize())  # grading not timed out yet

		internal = make_ticket(
			"B 2003 IN", time_in="10:00:00", time_out="10:30:00", grading=GRADING, blok=BLOK
		)
		self.assertEqual(
			(internal.status, internal.sumber_tbs, internal.supplier), ("Ready", "Internal", None)
		)

	def test_deductions_match_generator_formula(self):
		ticket = make_ticket("B 2001 PL", grading=GRADING)
		self.assertEqual(ticket.sumber_tbs, "External")
		self.assertAlmostEqual(ticket.potongan_pct, EXPECTED_POTONGAN, places=2)
		self.assertEqual(ticket.sampah_kg, 0)
		self.assertEqual(ticket.net_after_deduction_kg, EXPECTED_PAYABLE)
		self.assertEqual(ticket.harga_per_kg, PRICE)
		self.assertEqual(ticket.nilai, EXPECTED_PAYABLE * PRICE)
		self.assertEqual(ticket.grading[0].berat_kg, round(9160 * 9.95 / 100, 2))

	def test_cap_and_sampah(self):
		heavy = [
			{"kriteria": "Mentah", "persen": 40},
			{"kriteria": "Sampah", "persen": 1},
			{"kriteria": "Matang", "persen": 59},
		]
		ticket = make_ticket("B 2001 PL", gross=15400, tare=5400, grading=heavy)
		self.assertEqual(ticket.potongan_pct, 18)  # 40 x 0.6 = 24 %, capped
		self.assertEqual(ticket.sampah_kg, 100)
		self.assertEqual(ticket.net_after_deduction_kg, round(9900 * 0.82))

	def test_finalise_creates_purchase_receipt(self):
		ticket = make_ticket("B 2001 PL", grading=GRADING)
		self.assertTrue(ticket.try_finalize())
		ticket.reload()
		self.assertEqual((ticket.docstatus, ticket.status), (1, "Finalised"))

		pr = frappe.get_doc("Purchase Receipt", ticket.purchase_receipt)
		row = pr.items[0]
		self.assertEqual(pr.docstatus, 1)
		self.assertEqual(pr.custom_weighbridge_ticket, ticket.name)
		self.assertEqual((row.qty, row.warehouse, row.price_list_rate), (9160, WAREHOUSE, PRICE))
		self.assertAlmostEqual(row.discount_percentage, EXPECTED_POTONGAN, places=2)
		self.assertEqual(row.batch_no, f"TBS-{frappe.utils.today().replace('-', '')}")

		# idempotent
		self.assertEqual(ticket.create_stock_documents(), pr.name)

	def test_internal_creates_stock_entry(self):
		ticket = make_ticket("B 2003 IN", grading=GRADING, blok=BLOK)
		self.assertTrue(ticket.try_finalize())
		ticket.reload()
		se = frappe.get_doc("Stock Entry", ticket.stock_entry)
		row = se.items[0]
		self.assertEqual((se.docstatus, se.stock_entry_type), (1, "Material Receipt"))
		self.assertEqual((row.t_warehouse, row.qty, row.basic_rate), (WAREHOUSE, 9160, PRICE))
		self.assertEqual(row.expense_account, "Stock Adjustment - _TC")

	def test_timeout_finalises_without_grading(self):
		ticket = make_ticket("B 2001 PL", time_in="00:01:00", time_out="00:05:00")
		with change_settings("Palm Mill Settings", {"grading_timeout_hours": 0, "default_potongan_pct": 5}):
			finalize_due_tickets()
		ticket.reload()
		self.assertEqual((ticket.docstatus, ticket.grading_missing, ticket.potongan_pct), (1, 1, 5))
		self.assertTrue(ticket.purchase_receipt)

	def test_cancelling_receipt_clears_backlink(self):
		ticket = make_ticket("B 2001 PL", grading=GRADING)
		ticket.try_finalize()
		ticket.reload()
		pr = frappe.get_doc("Purchase Receipt", ticket.purchase_receipt)

		# the ticket cannot be cancelled while its receipt stands
		self.assertRaises(frappe.LinkExistsError, ticket.cancel)

		pr.cancel()
		ticket.reload()
		self.assertFalse(ticket.purchase_receipt)

		# and a replacement can be made from the form button
		new_pr = make_stock_documents(ticket.name)
		self.assertNotEqual(new_pr, pr.name)
		self.assertEqual(frappe.db.get_value("Purchase Receipt", new_pr, "docstatus"), 1)

	def test_submit_requires_weight(self):
		ticket = make_ticket("B 2001 PL", gross=0, tare=0, grading=GRADING)
		self.assertRaises(frappe.ValidationError, ticket.submit)
