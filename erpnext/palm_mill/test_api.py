# Copyright (c) 2026, AutoERP and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

from erpnext.palm_mill import api
from erpnext.palm_mill.setup import INTEGRATION_USER_ROLES
from erpnext.palm_mill.test_fixtures import (
	AGEN_SUPPLIER,
	COMPANY,
	EXPECTED_POTONGAN,
	PLASMA_SUPPLIER,
	make_truck,
	setup_palm_mill,
)

EXTRA_TEST_RECORD_DEPENDENCIES = ["Supplier", "Warehouse", "Price List", "Cost Center"]

INTEGRATION_USER = "palm-mill-integration@example.com"
PLAIN_USER = "palm-mill-nobody@example.com"


def make_user(email, roles):
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": email.split("@")[0],
				"send_welcome_email": 0,
				"roles": [{"role": r} for r in roles],
			}
		).insert(ignore_permissions=True)
	return email


def grading_payload(plate, assignment_id, day, supplier=None, **overrides):
	payload = {
		"assignment_id": assignment_id,
		"site": COMPANY,
		"truck": {"plate_number": plate, "autograde_id": f"ag-{assignment_id}"},
		"supplier_erp_name": supplier,
		"started_at": f"{day}T08:12:00",
		"ended_at": f"{day}T08:41:00",
		"counts": {"total": 412, "acc": 371, "rej": 41, "mentah": 41, "tangkai_panjang": 23},
		"pct": {"mentah": 9.95, "tangkai_panjang": 5.58},
		"detail_url": "https://autograde.example/gradings?assignment=" + assignment_id,
	}
	payload.update(overrides)
	return payload


class IntegrationTestPalmMillAPI(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		setup_palm_mill()
		make_truck("B 3001 PL", PLASMA_SUPPLIER)
		make_user(INTEGRATION_USER, INTEGRATION_USER_ROLES)
		make_user(PLAIN_USER, ["Employee"])

	def setUp(self):
		super().setUp()
		frappe.set_user(INTEGRATION_USER)

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def test_weighing_then_grading_is_one_ticket(self):
		day = frappe.utils.today()
		w = api.upsert_weighing(
			scale_ticket_no="T-1",
			plate_number="bg9911zz",
			gross_kg=14560,
			tare_kg=5400,
			time_in=f"{day}T08:03:00",
			time_out=f"{day}T08:52:00",
			site=COMPANY,
		)
		self.assertEqual(
			(w["status"], w["truck"], w["truck_pending"], w["finalised"]),
			("Waiting Grading", "BG 9911 ZZ", 1, False),
		)

		g = api.upsert_grading_session(**grading_payload("BG 9911 ZZ", "a-1", day, supplier=PLASMA_SUPPLIER))
		self.assertEqual((g["ticket"], g["status"], g["finalised"]), (w["ticket"], "Finalised", True))

		ticket = frappe.get_doc("Weighbridge Ticket", g["ticket"])
		self.assertEqual(
			(ticket.supplier, ticket.sumber_tbs, ticket.grading_total), (PLASMA_SUPPLIER, "Plasma", 412)
		)
		self.assertAlmostEqual(ticket.potongan_pct, EXPECTED_POTONGAN, places=2)
		self.assertTrue(ticket.purchase_receipt)
		self.assertEqual(frappe.db.get_value("Truck", "BG 9911 ZZ", "autograde_id"), "ag-a-1")
		self.assertEqual(frappe.db.count("Integration Request", {"reference_docname": ticket.name}), 2)

		# replays change nothing
		count = frappe.db.count("Weighbridge Ticket")
		again = api.upsert_grading_session(
			**grading_payload("BG 9911 ZZ", "a-1", day, supplier=PLASMA_SUPPLIER)
		)
		self.assertIn("unchanged", again["note"])
		self.assertEqual(frappe.db.count("Weighbridge Ticket"), count)

		# a real revision after finalisation is flagged, not applied
		revised = api.upsert_grading_session(
			**grading_payload(
				"BG 9911 ZZ",
				"a-1",
				day,
				supplier=PLASMA_SUPPLIER,
				pct={"mentah": 12, "tangkai_panjang": 5.58},
			)
		)
		self.assertTrue(revised["revised"])
		ticket.reload()
		self.assertEqual(ticket.grading_revised, 1)
		self.assertAlmostEqual(ticket.potongan_pct, EXPECTED_POTONGAN, places=2)
		self.assertTrue(
			frappe.db.exists("Comment", {"reference_name": ticket.name, "comment_type": "Comment"})
		)

	def test_grading_first_then_weighing(self):
		day = frappe.utils.today()
		g = api.upsert_grading_session(**grading_payload("BE 1234 QQ", "a-2", day, supplier=AGEN_SUPPLIER))
		self.assertEqual((g["status"], g["truck_pending"]), ("Waiting Weight", 1))

		w = api.upsert_weighing(
			scale_ticket_no="T-2",
			plate_number="BE1234QQ",
			gross_kg=12000,
			tare_kg=5400,
			time_in=f"{day}T07:58:00",
			time_out=f"{day}T09:10:00",
			site=COMPANY,
		)
		self.assertEqual((w["ticket"], w["finalised"]), (g["ticket"], True))
		ticket = frappe.get_doc("Weighbridge Ticket", w["ticket"])
		self.assertEqual(
			(ticket.sumber_tbs, ticket.scale_ticket_no, ticket.net_weight_kg), ("Pihak Ketiga", "T-2", 6600)
		)

	def test_weighing_in_two_calls(self):
		day = frappe.utils.today()
		gate = api.upsert_weighing(
			scale_ticket_no="T-5",
			plate_number="B 3001 PL",
			gross_kg=14560,
			time_in=f"{day}T08:03:00",
			site=COMPANY,
		)
		ticket = frappe.get_doc("Weighbridge Ticket", gate["ticket"])
		self.assertEqual(
			(gate["status"], ticket.gross_weight_kg, ticket.net_weight_kg, ticket.time_out),
			("Waiting Weight", 14560, 0, None),
		)

		leave = api.upsert_weighing(
			scale_ticket_no="T-5",
			plate_number="B 3001 PL",
			gross_kg=14560,
			tare_kg=5400,
			time_in=f"{day}T08:03:00",
			time_out=f"{day}T08:52:00",
			site=COMPANY,
		)
		ticket.reload()
		self.assertEqual(
			(leave["ticket"], leave["status"], ticket.net_weight_kg),
			(gate["ticket"], "Waiting Grading", 9160),
		)

	def test_visits_outside_the_window_are_separate_tickets(self):
		day = frappe.utils.today()
		first = api.upsert_weighing(
			scale_ticket_no="T-3",
			plate_number="B 3001 PL",
			gross_kg=10000,
			tare_kg=5400,
			time_in=f"{day}T06:00:00",
			time_out=f"{day}T06:20:00",
			site=COMPANY,
		)
		second = api.upsert_weighing(
			scale_ticket_no="T-4",
			plate_number="B 3001 PL",
			gross_kg=11000,
			tare_kg=5400,
			time_in=f"{day}T15:00:00",
			time_out=f"{day}T15:20:00",
			site=COMPANY,
		)
		self.assertNotEqual(first["ticket"], second["ticket"])

	def test_upsert_truck(self):
		existing = api.upsert_truck(plate_number="b3001pl", autograde_id="ag-x")
		self.assertEqual(
			(existing["name"], existing["pending"], existing["supplier"]), ("B 3001 PL", 0, PLASMA_SUPPLIER)
		)

		new = api.upsert_truck(plate_number="bd 777 xx", autograde_id="ag-y", capacity=8)
		self.assertEqual((new["name"], new["pending"], new["vehicle_class"]), ("BD 777 XX", 1, ""))

	def test_requires_integration_role(self):
		frappe.set_user(PLAIN_USER)
		self.assertRaises(frappe.PermissionError, api.upsert_truck, plate_number="X 1 Y")
