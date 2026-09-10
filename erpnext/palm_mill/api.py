# Copyright (c) 2026, AutoERP and contributors
# For license information, please see license.txt

"""Inbound endpoints for the mill's systems (design: docs/autograde-integration.md, §4).

Callers authenticate with Frappe's `Authorization: token <api_key>:<api_secret>` header
as a user holding the Palm Mill Integration role. Every call is permission-checked
like a form would be, idempotent on its natural key, and recorded as an Integration
Request (successes) or an Error Log (failures) so an operator can see what arrived.

	POST /api/method/erpnext.palm_mill.api.upsert_truck
	POST /api/method/erpnext.palm_mill.api.upsert_weighing
	POST /api/method/erpnext.palm_mill.api.upsert_grading_session
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
WEIGHBRIDGE = "Weighbridge"
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
@logged(WEIGHBRIDGE)
def upsert_weighing(
	scale_ticket_no,
	plate_number,
	gross_kg,
	tare_kg,
	time_in,
	time_out=None,
	site=None,
	driver_name=None,
	vehicle_class=None,
):
	"""Interface D: one weighing from the scale program. Keyed by the scale's ticket number,
	then matched to an open ticket of the same truck within the matching window."""
	frappe.has_permission("Weighbridge Ticket", "write", throw=True)
	company = _company(site)
	truck = get_or_create_truck(plate_number, source="Scale", vehicle_class=vehicle_class)
	start = to_site_datetime(time_in)
	end = to_site_datetime(time_out) if time_out else None

	ticket = find_or_create_ticket(company, truck.name, start, end, "scale_ticket_no", scale_ticket_no)
	if ticket.docstatus != 0:
		return _result(ticket, truck, note="ticket already finalised; weighing ignored")

	ticket.update(
		{
			"scale_ticket_no": scale_ticket_no,
			"truck": truck.name,
			"ticket_date": start.date(),
			"time_in": start.time(),
			"time_out": end.time() if end else ticket.time_out,
			"gross_weight_kg": flt(gross_kg),
			"tare_weight_kg": flt(tare_kg),
			"net_weight_kg": flt(gross_kg) - flt(tare_kg),
			"driver_name": driver_name or ticket.driver_name,
			"weight_received_at": now_datetime(),
		}
	)
	ticket.flags.recompute = True
	ticket.save()
	finalised = ticket.try_finalize()
	return _result(ticket, truck, finalised=finalised)


@frappe.whitelist(methods=["POST"])
@logged(AUTOGRADE)
def upsert_grading_session(
	assignment_id,
	truck,
	counts,
	started_at,
	ended_at=None,
	site=None,
	supplier_erp_name=None,
	line_code=None,
	pct=None,
	detail_url=None,
	emitted_at=None,
):
	"""Interface C: the per-visit summary of an AutoGrade line assignment. Full replacement
	of the AI-graded criteria; operator-entered rows (Sampah, Lewat Matang) are kept.
	After the ticket is finalised a revision only leaves a flag and a comment."""
	frappe.has_permission("Weighbridge Ticket", "write", throw=True)
	company = _company(site)
	truck_info = frappe.parse_json(truck) or {}
	counts = frappe.parse_json(counts) or {}
	pct = frappe.parse_json(pct) or {}

	plate = truck_info.get("erp_name") or truck_info.get("plate_number")
	truck_doc = get_or_create_truck(
		plate, source=AUTOGRADE, supplier=supplier_erp_name, autograde_id=truck_info.get("autograde_id")
	)
	start = to_site_datetime(started_at)
	end = to_site_datetime(ended_at) if ended_at else None

	total = cint(counts.get("total"))
	mentah = (
		flt(pct.get("mentah"))
		if "mentah" in pct
		else (flt(counts.get("mentah")) / total * 100 if total else 0)
	)
	tangkai = (
		flt(pct.get("tangkai_panjang"))
		if "tangkai_panjang" in pct
		else (flt(counts.get("tangkai_panjang")) / total * 100 if total else 0)
	)

	ticket = find_or_create_ticket(
		company, truck_doc.name, start, end, "autograde_assignment_id", assignment_id
	)
	if ticket.docstatus == 2:
		return _result(ticket, truck_doc, note="ticket cancelled; grading ignored")
	if ticket.docstatus == 1:
		before = ticket.grading_percentages()
		if (round(before.get("Mentah", 0), 2), round(before.get("Tangkai Panjang", 0), 2)) == (
			round(mentah, 2),
			round(tangkai, 2),
		):
			return _result(ticket, truck_doc, note="ticket already finalised; grading unchanged")
		ticket.add_comment(
			"Comment",
			_(
				"AutoGrade revised grading after finalisation: Mentah {0}% -> {1}%, Tangkai Panjang {2}% -> {3}%"
			).format(
				before.get("Mentah", 0), round(mentah, 2), before.get("Tangkai Panjang", 0), round(tangkai, 2)
			),
		)
		ticket.db_set("grading_revised", 1)
		return _result(ticket, truck_doc, revised=True)

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
			"autograde_assignment_id": assignment_id,
			"autograde_url": detail_url,
			"supplier": ticket.supplier or truck_doc.supplier or supplier_erp_name,
			"grading_total": total,
			"grading_acc": cint(counts.get("acc")),
			"grading_rej": cint(counts.get("rej")),
			"grading_received_at": now_datetime(),
		}
	)
	ticket.flags.recompute = True
	ticket.save()
	finalised = ticket.try_finalize()
	return _result(ticket, truck_doc, finalised=finalised)
