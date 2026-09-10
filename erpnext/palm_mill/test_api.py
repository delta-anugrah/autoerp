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
	make_ticket,
	make_truck,
	setup_palm_mill,
)

EXTRA_TEST_RECORD_DEPENDENCIES = ["Supplier", "Warehouse", "Price List", "Cost Center"]

INTEGRATION_USER = "palm-mill-integration@example.com"
PLAIN_USER = "palm-mill-nobody@example.com"
COUNTS = {"total": 412, "acc": 371, "rej": 41, "mentah": 41, "tangkai_panjang": 23, "manual_reject": 3}
PCT = {"mentah": 9.95, "tangkai_panjang": 5.58}


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


def visit(visit_id, plate, day, stage, supplier=None, scale_ticket_no=None, pct=None, time_in="08:03"):
	"""The message AutoGrade sends at each stage of one visit."""
	weighing = {"gross_kg": 14560, "time_in": f"{day}T{time_in}:00", "driver_name": "Yusuf"}
	grading = None
	if stage in ("grading", "departed"):
		grading = {
			"assignment_id": f"as-{visit_id}",
			"line_code": "L1",
			"started_at": f"{day}T08:12:00",
			"ended_at": f"{day}T08:41:00",
			"counts": COUNTS,
			"pct": pct or PCT,
			"detail_url": f"https://autograde.example/gradings?assignment=as-{visit_id}",
		}
	if stage == "departed":
		weighing.update({"tare_kg": 5400, "time_out": f"{day}T08:52:00"})
	return api.upsert_visit(
		visit_id=visit_id,
		site=COMPANY,
		stage=stage,
		truck={"plate_number": plate, "autograde_id": f"ag-{plate}"},
		supplier_erp_name=supplier,
		scale_ticket_no=scale_ticket_no,
		weighing=weighing,
		grading=grading,
	)


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

	def test_visit_in_three_sends(self):
		day = frappe.utils.today()
		gate = visit("v-1", "bg9911zz", day, "gate", supplier=PLASMA_SUPPLIER, scale_ticket_no="SCL-1")
		self.assertEqual(
			(gate["status"], gate["truck"], gate["truck_pending"]), ("Waiting Weight", "BG 9911 ZZ", 1)
		)

		graded = visit("v-1", "BG 9911 ZZ", day, "grading", supplier=PLASMA_SUPPLIER, scale_ticket_no="SCL-1")
		self.assertEqual((graded["ticket"], graded["status"]), (gate["ticket"], "Waiting Weight"))

		left = visit("v-1", "BG 9911 ZZ", day, "departed", supplier=PLASMA_SUPPLIER, scale_ticket_no="SCL-1")
		self.assertEqual(
			(left["ticket"], left["status"], left["finalised"]), (gate["ticket"], "Finalised", True)
		)

		ticket = frappe.get_doc("Weighbridge Ticket", left["ticket"])
		self.assertEqual(
			(ticket.autograde_visit_id, ticket.scale_ticket_no, ticket.autograde_assignment_id),
			("v-1", "SCL-1", "as-v-1"),
		)
		self.assertEqual(
			(ticket.supplier, ticket.sumber_tbs, ticket.net_weight_kg), (PLASMA_SUPPLIER, "Plasma", 9160)
		)
		self.assertAlmostEqual(ticket.potongan_pct, EXPECTED_POTONGAN, places=2)
		self.assertTrue(ticket.purchase_receipt)
		self.assertEqual(frappe.db.get_value("Truck", "BG 9911 ZZ", "autograde_id"), "ag-bg9911zz")
		self.assertEqual(frappe.db.count("Integration Request", {"reference_docname": ticket.name}), 3)

	def test_replay_and_revision_after_finalisation(self):
		day = frappe.utils.today()
		left = visit("v-2", "B 3001 PL", day, "departed")
		self.assertTrue(left["finalised"])
		count = frappe.db.count("Weighbridge Ticket")

		again = visit("v-2", "B 3001 PL", day, "departed")
		self.assertIn("unchanged", again["note"])
		self.assertEqual(frappe.db.count("Weighbridge Ticket"), count)

		revised = visit("v-2", "B 3001 PL", day, "departed", pct={"mentah": 12, "tangkai_panjang": 5.58})
		self.assertTrue(revised["revised"])
		ticket = frappe.get_doc("Weighbridge Ticket", left["ticket"])
		self.assertEqual(ticket.grading_revised, 1)
		self.assertAlmostEqual(ticket.potongan_pct, EXPECTED_POTONGAN, places=2)
		self.assertTrue(
			frappe.db.exists("Comment", {"reference_name": ticket.name, "comment_type": "Comment"})
		)

	def test_hand_typed_ticket_is_adopted_by_the_visit(self):
		day = frappe.utils.today()
		frappe.set_user("Administrator")
		typed = make_ticket("B 3001 PL", scale_ticket_no="SCL-MAN-7")
		self.assertEqual(typed.status, "Waiting Grading")
		frappe.set_user(INTEGRATION_USER)

		left = visit("v-3", "B 3001 PL", day, "departed", scale_ticket_no="SCL-MAN-7")
		self.assertEqual((left["ticket"], left["finalised"]), (typed.name, True))
		self.assertEqual(frappe.db.get_value("Weighbridge Ticket", typed.name, "autograde_visit_id"), "v-3")

	def test_visits_outside_the_window_are_separate_tickets(self):
		day = frappe.utils.today()
		first = visit("v-4", "B 3001 PL", day, "gate", time_in="06:00")
		second = visit("v-5", "B 3001 PL", day, "gate", time_in="15:00")
		self.assertNotEqual(first["ticket"], second["ticket"])

	def test_unknown_plate_becomes_pending_truck_and_inti(self):
		day = frappe.utils.today()
		gate = visit("v-6", "BE 1234 QQ", day, "gate", supplier=AGEN_SUPPLIER)
		self.assertEqual(gate["truck_pending"], 1)
		self.assertEqual(
			frappe.db.get_value("Weighbridge Ticket", gate["ticket"], "sumber_tbs"), "Pihak Ketiga"
		)

	def test_time_in_is_required(self):
		self.assertRaises(
			frappe.ValidationError,
			api.upsert_visit,
			visit_id="v-7",
			truck={"plate_number": "B 3001 PL"},
			weighing={"gross_kg": 1},
			site=COMPANY,
		)

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
