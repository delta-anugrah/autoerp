# Copyright (c) 2026, AutoERP and contributors
# For license information, please see license.txt

"""Inbound endpoints for AutoGrade, the one system that talks to AutoERP
(design: docs/autograde-integration.md, §4). The scale program feeds AutoGrade at the
mill; AutoGrade carries weights and grading up and sends each truck visit here.

Callers authenticate with Frappe's `Authorization: token <api_key>:<api_secret>` header
as a user holding the Palm Mill Integration role. Every call is permission-checked
like a form would be, idempotent on its natural key, and recorded as an Integration
Request (successes) or an Error Log (failures) so an operator can see what arrived.

	POST /api/method/erpnext.palm_mill.api.upsert_truck
	POST /api/method/erpnext.palm_mill.api.upsert_visit
"""

import functools

import frappe
from frappe import _
from frappe.integrations.utils import create_request_log
from frappe.utils import cint, flt, now_datetime

from erpnext.palm_mill.doctype.truck.truck import get_or_create_truck
from erpnext.palm_mill.doctype.weighbridge_ticket.weighbridge_ticket import find_or_create_ticket
from erpnext.palm_mill.utils import to_site_datetime

AUTOGRADE = "AutoGrade"
AI_CRITERIA = ("Mentah", "Tangkai Panjang", "Matang")


def logged(service):
	"""Record the call: Integration Request on success, Error Log (with payload) on failure."""

	def decorator(fn):
		@functools.wraps(fn)
		def wrapper(**kwargs):
			try:
				out = fn(**kwargs)
			except Exception:
				frappe.log_error(
					title=_("{0} request failed: {1}").format(service, fn.__name__),
					message=frappe.as_json(kwargs) + "\n\n" + frappe.get_traceback(),
				)
				raise
			create_request_log(
				kwargs,
				service_name=service,
				output=out,
				status="Completed",
				is_remote_request=1,
				reference_doctype="Weighbridge Ticket" if out.get("ticket") else None,
				reference_docname=out.get("ticket"),
			)
			return out

		return wrapper

	return decorator


def _company(site):
	company = site or frappe.defaults.get_global_default("company")
	if not company or not frappe.db.exists("Company", company):
		frappe.throw(_("Unknown company {0}").format(site))
	return company


def _result(ticket, truck, **extra):
	return {
		"ticket": ticket.name,
		"status": ticket.status,
		"truck": truck.name,
		"truck_pending": cint(truck.pending),
		**extra,
	}


@frappe.whitelist(methods=["POST"])
@logged(AUTOGRADE)
def upsert_truck(
	plate_number, autograde_id=None, supplier=None, vehicle_class=None, capacity=None, site=None
):
	"""Interface B: a plate first seen at the mill becomes a pending Truck. Existing trucks
	are never overwritten (AutoERP owns master data); `capacity` is accepted and ignored."""
	frappe.has_permission("Truck", "create", throw=True)
	truck = get_or_create_truck(
		plate_number,
		source=AUTOGRADE,
		supplier=supplier,
		vehicle_class=vehicle_class,
		autograde_id=autograde_id,
	)
	return {
		"name": truck.name,
		"pending": cint(truck.pending),
		"supplier": truck.supplier,
		"vehicle_class": truck.vehicle_class,
	}


@frappe.whitelist(methods=["POST"])
@logged(AUTOGRADE)
def upsert_visit(
	visit_id,
	truck,
	weighing,
	site=None,
	supplier_erp_name=None,
	scale_ticket_no=None,
	grading=None,
	stage=None,
	emitted_at=None,
):
	"""Interface C: one truck visit, sent by AutoGrade at each stage (gate, grading closed,
	weigh-out) and resent daily. Every send is a full replacement of the sections it carries.

	`weighing.time_in` is required (it dates the ticket); `tare_kg` / `time_out` arrive at
	departure, `grading` when the line assignment closes. The tare includes rejected bunches
	put back on the truck, so net is what stayed at the mill. After finalisation nothing is
	rewritten: identical numbers are acknowledged, changed ones leave a flag and a comment.
	"""
	frappe.has_permission("Weighbridge Ticket", "write", throw=True)
	company = _company(site)
	truck_info = frappe.parse_json(truck) or {}
	weighing = frappe.parse_json(weighing) or {}
	grading = frappe.parse_json(grading) or {}
	if not weighing.get("time_in"):
		frappe.throw(_("weighing.time_in is required: it dates the visit"))

	plate = truck_info.get("erp_name") or truck_info.get("plate_number")
	truck_doc = get_or_create_truck(
		plate, source=AUTOGRADE, supplier=supplier_erp_name, autograde_id=truck_info.get("autograde_id")
	)
	start = to_site_datetime(weighing["time_in"])
	end = to_site_datetime(weighing["time_out"]) if weighing.get("time_out") else None
	pct = _grading_percentages(grading) if grading else None

	ticket = _find_ticket(
		company, truck_doc.name, start, end, visit_id, scale_ticket_no, grading.get("assignment_id")
	)
	if ticket.docstatus == 2:
		return _result(ticket, truck_doc, note="ticket cancelled; visit ignored")
	if ticket.docstatus == 1:
		return _after_finalisation(ticket, truck_doc, weighing, pct)

	ticket.update(
		{
			"autograde_visit_id": visit_id,
			"scale_ticket_no": scale_ticket_no or ticket.scale_ticket_no,
			"truck": truck_doc.name,
			"supplier": ticket.supplier or truck_doc.supplier or supplier_erp_name,
		}
	)
	_apply_weighing(ticket, weighing, start, end)
	if grading:
		_apply_grading(ticket, grading, pct)
	ticket.flags.recompute = True
	ticket.save()
	finalised = ticket.try_finalize()
	return _result(ticket, truck_doc, finalised=finalised, stage=stage)


def _find_ticket(company, truck, start, end, visit_id, scale_ticket_no, assignment_id):
	"""By the visit id, then the secondary keys (a ticket typed by hand carries only the
	scale number), then the truck's open ticket in the matching window, else a new draft."""
	for field, value in (
		("autograde_visit_id", visit_id),
		("scale_ticket_no", scale_ticket_no),
		("autograde_assignment_id", assignment_id),
	):
		if value:
			name = frappe.db.get_value("Weighbridge Ticket", {field: value})
			if name:
				return frappe.get_doc("Weighbridge Ticket", name)
	return find_or_create_ticket(company, truck, start, end)


def _apply_weighing(ticket, weighing, start, end):
	has_tare = weighing.get("tare_kg") is not None
	gross = (
		flt(weighing.get("gross_kg")) if weighing.get("gross_kg") is not None else flt(ticket.gross_weight_kg)
	)
	ticket.update(
		{
			"ticket_date": start.date(),
			"time_in": start.time(),
			"time_out": end.time() if end else ticket.time_out,
			"gross_weight_kg": gross,
			"tare_weight_kg": flt(weighing["tare_kg"]) if has_tare else ticket.tare_weight_kg,
			"net_weight_kg": gross - flt(weighing["tare_kg"]) if has_tare else 0,
			"driver_name": weighing.get("driver_name") or ticket.driver_name,
			"weight_received_at": now_datetime(),
		}
	)


def _grading_percentages(grading) -> tuple[float, float]:
	"""Mentah (rejected share) and Tangkai Panjang, from `pct` when sent, else from counts."""
	counts = frappe.parse_json(grading.get("counts")) or {}
	pct = frappe.parse_json(grading.get("pct")) or {}
	total = cint(counts.get("total"))

	def share(key):
		if key in pct:
			return flt(pct[key])
		return flt(counts.get(key)) / total * 100 if total else 0

	return share("mentah"), share("tangkai_panjang")


def _apply_grading(ticket, grading, pct):
	"""Replace the AI-graded rows; rows an operator typed (Sampah, Lewat Matang) are kept."""
	mentah, tangkai = pct
	counts = frappe.parse_json(grading.get("counts")) or {}
	kept = [row for row in ticket.grading if row.kriteria not in AI_CRITERIA]
	other = sum(flt(row.persen) for row in kept)
	ticket.grading = []
	for row in kept:
		ticket.append("grading", row)
	for kriteria, persen in (
		("Mentah", mentah),
		("Tangkai Panjang", tangkai),
		("Matang", max(0.0, 100 - mentah - tangkai - other)),
	):
		ticket.append("grading", {"kriteria": kriteria, "persen": round(persen, 2)})
	ticket.update(
		{
			"autograde_assignment_id": grading.get("assignment_id") or ticket.autograde_assignment_id,
			"autograde_url": grading.get("detail_url") or ticket.autograde_url,
			"grading_total": cint(counts.get("total")),
			"grading_acc": cint(counts.get("acc")),
			"grading_rej": cint(counts.get("rej")),
			"grading_received_at": now_datetime(),
		}
	)


def _after_finalisation(ticket, truck, weighing, pct):
	"""A finalised ticket is never rewritten. Same numbers: acknowledge. Different numbers:
	flag and comment for the backoffice."""
	notes = []
	if pct:
		before = ticket.grading_percentages()
		old = (round(before.get("Mentah", 0), 2), round(before.get("Tangkai Panjang", 0), 2))
		new = (round(pct[0], 2), round(pct[1], 2))
		if old != new:
			ticket.add_comment(
				"Comment",
				_(
					"AutoGrade revised grading after finalisation: Mentah {0}% -> {1}%, Tangkai Panjang {2}% -> {3}%"
				).format(old[0], new[0], old[1], new[1]),
			)
			ticket.db_set("grading_revised", 1)
			notes.append("grading revised")
	if weighing.get("tare_kg") is not None:
		old = (flt(ticket.gross_weight_kg), flt(ticket.tare_weight_kg))
		new = (flt(weighing.get("gross_kg")), flt(weighing.get("tare_kg")))
		if old != new:
			ticket.add_comment(
				"Comment",
				_(
					"AutoGrade revised weights after finalisation: gross {0} -> {1} kg, tare {2} -> {3} kg"
				).format(old[0], new[0], old[1], new[1]),
			)
			notes.append("weights revised")
	if notes:
		return _result(ticket, truck, revised=True, note="ticket already finalised; " + ", ".join(notes))
	return _result(ticket, truck, note="ticket already finalised; visit unchanged")
