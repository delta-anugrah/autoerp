# Copyright (c) 2026, AutoERP and contributors
# For license information, please see license.txt

"""One truck visit = one Weighbridge Ticket.

Weight (from the scale) and grading (from AutoGrade or the operator) attach to the
ticket independently. `try_finalize` submits it once both are present, or once the
grading timeout has passed, and then creates the stock document: a Purchase Receipt
for bought fruit (Plasma / Pihak Ketiga) or a Stock Entry for the mill's own estate
(Inti). Quantity is net minus sampah; potongan is the receipt item's discount, the
same way the existing receipts were built.
"""

from datetime import datetime, timedelta

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate, now_datetime

from erpnext.palm_mill.utils import PURCHASED_SOURCES, combine
from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry

SAMPAH = "Sampah"
DIMENSION_FIELDS = ("sumber_tbs", "sertifikasi", "blok", "kebun", "divisi")


class WeighbridgeTicket(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from erpnext.palm_mill.doctype.weighbridge_grading.weighbridge_grading import WeighbridgeGrading

		amended_from: DF.Link | None
		autograde_assignment_id: DF.Data | None
		autograde_url: DF.Data | None
		blok: DF.Link | None
		catatan: DF.SmallText | None
		company: DF.Link
		driver_name: DF.Data | None
		grading: DF.Table[WeighbridgeGrading]
		grading_acc: DF.Int
		grading_missing: DF.Check
		grading_received_at: DF.Datetime | None
		grading_rej: DF.Int
		grading_revised: DF.Check
		grading_total: DF.Int
		gross_weight_kg: DF.Float
		harga_per_kg: DF.Currency
		net_after_deduction_kg: DF.Float
		net_weight_kg: DF.Float
		nilai: DF.Currency
		potongan_pct: DF.Percent
		purchase_receipt: DF.Link | None
		sampah_kg: DF.Float
		scale_ticket_no: DF.Data | None
		sertifikasi: DF.Literal["", "ISPO", "RSPO", "Non-sertifikasi"]
		status: DF.Literal["", "Waiting Weight", "Waiting Grading", "Ready", "Finalised", "Cancelled"]
		stock_entry: DF.Link | None
		sumber_tbs: DF.Literal["Inti", "Plasma", "Pihak Ketiga"]
		supplier: DF.Link | None
		tare_weight_kg: DF.Float
		ticket_date: DF.Date
		time_in: DF.Time | None
		time_out: DF.Time | None
		truck: DF.Link | None
		vehicle_class: DF.Data | None
		vehicle_no: DF.Data | None
		weight_received_at: DF.Datetime | None
	# end: auto-generated types

	# ----------------------------------------------------------------- lifecycle
	def validate(self):
		self.set_weights()
		self.set_supplier_and_source()
		# Seeded tickets arrive with their numbers; only recompute when asked or when empty.
		if self.flags.recompute or not self.nilai:
			self.compute_deductions()
		self.set_status()

	def before_submit(self):
		if flt(self.net_weight_kg) <= 0:
			frappe.throw(_("Net weight is required to finalise a Weighbridge Ticket"))

	def on_submit(self):
		if cint(settings().create_stock_documents_on_submit):
			self.create_stock_documents()

	def on_cancel(self):
		# Frappe already refuses to cancel while a submitted receipt / stock entry links here.
		self.db_set("status", "Cancelled")

	# ---------------------------------------------------------------- derivation
	def set_weights(self):
		if self.gross_weight_kg and self.tare_weight_kg and not self.net_weight_kg:
			self.net_weight_kg = flt(self.gross_weight_kg) - flt(self.tare_weight_kg)
		if flt(self.net_weight_kg) < 0:
			frappe.throw(_("Net weight cannot be negative"))

	def set_supplier_and_source(self):
		if not self.supplier and self.truck:
			self.supplier = frappe.db.get_value("Truck", self.truck, "supplier")
		# New documents get the Select's first option ("Inti") before validate runs, so derive
		# from the supplier whenever the value is missing or contradicts having a supplier.
		derived = sumber_for_supplier(self.supplier)
		if not self.sumber_tbs or (self.sumber_tbs == "Inti") != (derived == "Inti"):
			self.sumber_tbs = derived

	def grading_percentages(self) -> dict[str, float]:
		return {row.kriteria: flt(row.persen) for row in self.grading}

	def compute_deductions(self):
		"""Same arithmetic as the demo generator, so recomputed tickets match seeded ones."""
		s = settings()
		net = flt(self.net_weight_kg)
		pct = self.grading_percentages()
		rules = {row.kriteria: flt(row.deduction_pct) for row in s.grading_rules}

		if pct:
			pot = sum(pct.get(k, 0) / 100 * rules[k] / 100 for k in rules)
		elif self.grading_missing:
			pot = flt(s.default_potongan_pct) / 100
		else:
			pot = 0
		pot = min(pot, flt(s.max_potongan_pct) / 100)

		for row in self.grading:
			row.berat_kg = round(net * flt(row.persen) / 100, 2) if net else row.berat_kg

		self.sampah_kg = round(net * pct.get(SAMPAH, 0) / 100)
		self.potongan_pct = round(pot * 100, 2)
		payable = round((net - flt(self.sampah_kg)) * (1 - pot))
		self.net_after_deduction_kg = payable
		if not self.harga_per_kg:
			self.harga_per_kg = self.get_price()
		self.nilai = round(payable * flt(self.harga_per_kg), 2)

	def get_price(self) -> float:
		"""Buying price of TBS on the ticket date: supplier-specific Item Price first, then general."""
		from erpnext.stock.get_item_details import ItemPriceCtx, get_item_price

		s = settings()
		price_list = s.buying_price_list or frappe.db.get_single_value("Buying Settings", "buying_price_list")
		if not (s.tbs_item and price_list):
			return 0
		pctx = ItemPriceCtx(
			item_code=s.tbs_item,
			price_list=price_list,
			supplier=self.supplier,
			uom=frappe.db.get_value("Item", s.tbs_item, "stock_uom"),
			transaction_date=self.ticket_date,
		)
		rows = get_item_price(pctx, s.tbs_item)
		if not rows and self.supplier:
			del pctx["supplier"]
			rows = get_item_price(pctx, s.tbs_item)
		return flt(rows[0].price_list_rate) if rows else 0

	def set_status(self):
		if self.docstatus == 2:
			self.status = "Cancelled"
		elif self.docstatus == 1:
			self.status = "Finalised"
		elif flt(self.net_weight_kg) <= 0:
			self.status = "Waiting Weight"
		elif not self.grading and not self.grading_missing:
			self.status = "Waiting Grading"
		else:
			self.status = "Ready"

	# -------------------------------------------------------------- finalisation
	def grading_timed_out(self) -> bool:
		end = combine(self.ticket_date, self.time_out or self.time_in)
		return now_datetime() >= end + timedelta(hours=cint(settings().grading_timeout_hours))

	def try_finalize(self) -> bool:
		"""Submit and create the stock document when weight and grading are both in,
		or when grading has timed out. Returns True when the ticket was finalised."""
		if self.docstatus != 0 or flt(self.net_weight_kg) <= 0:
			return False
		if not self.grading:
			if not self.grading_timed_out():
				return False
			self.grading_missing = 1

		self.flags.recompute = True
		self.save()
		if flt(self.harga_per_kg) <= 0:
			frappe.log_error(
				title=_("Weighbridge Ticket without TBS price"),
				message=f"{self.name}: no buying Item Price for {settings().tbs_item} on {self.ticket_date}",
			)
			return False

		self.submit()
		self.create_stock_documents()
		return True

	def create_stock_documents(self) -> str:
		"""Purchase Receipt for bought fruit, Stock Entry for Inti. Idempotent per ticket.

		Runs with the caller's permissions: whoever finalises a ticket needs the roles of
		someone who receives stock (Purchase User + Stock User), as ERPNext expects.
		"""
		if self.docstatus != 1:
			frappe.throw(_("Submit the Weighbridge Ticket before creating stock documents"))

		if self.sumber_tbs in PURCHASED_SOURCES:
			if not self.purchase_receipt:
				self.db_set("purchase_receipt", self.make_purchase_receipt().name)
			return self.purchase_receipt

		if not self.stock_entry:
			self.db_set("stock_entry", self.make_stock_entry().name)
		return self.stock_entry

	def make_purchase_receipt(self):
		s = require_settings("tbs_item", "tbs_warehouse")
		if not self.supplier:
			frappe.throw(_("Supplier is required for a {0} ticket").format(self.sumber_tbs))
		stock_uom = frappe.db.get_value("Item", s.tbs_item, "stock_uom")

		item = {
			"item_code": s.tbs_item,
			"qty": flt(self.net_weight_kg) - flt(self.sampah_kg),
			"uom": stock_uom,
			"stock_uom": stock_uom,
			"conversion_factor": 1,
			"warehouse": s.tbs_warehouse,
			"price_list_rate": flt(self.harga_per_kg),
			"discount_percentage": flt(self.potongan_pct),
			"cost_center": s.purchase_cost_center,
			"use_serial_batch_fields": 1,
			"batch_no": get_or_create_daily_batch(s.tbs_item, self.ticket_date),
			"custom_grading_note": self.grading_note(),
			**self.dimension_values(),
		}
		pr = frappe.get_doc(
			{
				"doctype": "Purchase Receipt",
				"company": self.company,
				"supplier": self.supplier,
				"set_posting_time": 1,
				"posting_date": self.ticket_date,
				"posting_time": self.time_in,
				"buying_price_list": s.buying_price_list,
				"custom_weighbridge_ticket": self.name,
				"items": [only_known_fields("Purchase Receipt Item", item)],
			}
		)
		pr.insert()
		pr.submit()
		return pr

	def make_stock_entry(self):
		s = require_settings("tbs_item", "tbs_warehouse", "inti_expense_account")
		dims = self.dimension_values()
		cost_center = None
		if dims.get("kebun") and dims.get("divisi"):
			cost_center = frappe.db.get_value(
				"Cost Center",
				{"company": self.company, "cost_center_name": f"{dims['kebun']} Divisi {dims['divisi']}"},
			)

		se = make_stock_entry(
			item_code=s.tbs_item,
			qty=flt(self.net_weight_kg) - flt(self.sampah_kg),
			to_warehouse=s.tbs_warehouse,
			company=self.company,
			basic_rate=flt(self.harga_per_kg),
			posting_date=self.ticket_date,
			posting_time=self.time_in,
			purpose="Material Receipt",
			batch_no=get_or_create_daily_batch(s.tbs_item, self.ticket_date),
			use_serial_batch_fields=1,
			cost_center=cost_center,
			expense_account=s.inti_expense_account,
			do_not_save=True,
		)
		row = se.items[0]
		row.set_basic_rate_manually = 1
		row.update(only_known_fields("Stock Entry Detail", dims))
		se.remarks = f"Penerimaan TBS Inti {self.name} @ Rp {flt(self.harga_per_kg):,.0f}/kg"
		se.insert()
		se.submit()
		return se

	# ------------------------------------------------------------------ helpers
	def dimension_values(self) -> dict:
		"""Accounting-dimension values carried onto the stock document's item row."""
		values = {"sumber_tbs": self.sumber_tbs, "sertifikasi": self.sertifikasi}
		if self.blok:
			kebun, divisi = frappe.db.get_value("Blok", self.blok, ["kebun", "divisi"])
			values.update({"blok": self.blok, "kebun": kebun, "divisi": divisi})
		return {k: v for k, v in values.items() if v}

	def grading_note(self) -> str:
		pct = self.grading_percentages()
		return (
			f"Mentah {pct.get('Mentah', 0):.1f}%, lewat matang {pct.get('Lewat Matang', 0):.1f}%, "
			f"tangkai panjang {pct.get('Tangkai Panjang', 0):.1f}% -> potongan {flt(self.potongan_pct):.1f}%"
		)


# ------------------------------------------------------------------ module level
def settings():
	return frappe.get_cached_doc("Palm Mill Settings")


def require_settings(*fieldnames):
	s = settings()
	missing = [f for f in fieldnames if not s.get(f)]
	if missing:
		labels = ", ".join(frappe.get_meta("Palm Mill Settings").get_label(f) for f in missing)
		frappe.throw(_("Please set {0} in Palm Mill Settings").format(labels))
	return s


def sumber_for_supplier(supplier: str | None) -> str:
	if not supplier:
		return "Inti"
	group = frappe.db.get_value("Supplier", supplier, "supplier_group")
	return "Plasma" if group and group == settings().plasma_supplier_group else "Pihak Ketiga"


def get_or_create_daily_batch(item_code: str, date) -> str:
	"""The demo convention: one TBS batch per receiving day, named TBS-YYYYMMDD."""
	batch_id = f"TBS-{getdate(date):%Y%m%d}"
	if not frappe.db.exists("Batch", batch_id):
		# A derived record, created the way ERPNext creates its own automatic batches
		# (erpnext.stock.serial_batch_bundle.make_batch): without a Batch permission check.
		frappe.get_doc(
			{"doctype": "Batch", "batch_id": batch_id, "item": item_code, "manufacturing_date": date}
		).insert(ignore_permissions=True)
	return batch_id


def only_known_fields(doctype: str, values: dict) -> dict:
	"""Dimension and custom fields exist only on sites that created them; drop the rest."""
	meta = frappe.get_meta(doctype)
	return {k: v for k, v in values.items() if meta.has_field(k)}


def find_or_create_ticket(
	company: str,
	truck: str,
	start: datetime,
	end: datetime | None,
	key_field: str | None = None,
	key_value: str | None = None,
) -> WeighbridgeTicket:
	"""The ticket for a truck visit: by natural key, else an open ticket of the same truck
	whose weighing window (widened by the matching tolerance) overlaps [start, end],
	else a new draft. The caller sets its fields and saves."""
	if key_field and key_value:
		name = frappe.db.get_value("Weighbridge Ticket", {key_field: key_value})
		if name:
			return frappe.get_doc("Weighbridge Ticket", name)

	end = end or start
	window = timedelta(hours=cint(settings().match_window_hours))
	rows = frappe.db.sql(
		"""select name from `tabWeighbridge Ticket`
		where company = %s and truck = %s and docstatus = 0 and ticket_date = %s
			and timestamp(ticket_date, ifnull(time_in, '00:00:00')) <= %s
			and timestamp(ticket_date, ifnull(time_out, ifnull(time_in, '00:00:00'))) >= %s
		order by creation desc limit 1""",
		(company, truck, start.date(), end + window, start - window),
	)
	if rows:
		return frappe.get_doc("Weighbridge Ticket", rows[0][0])

	doc = frappe.new_doc("Weighbridge Ticket")
	doc.update(
		{
			"company": company,
			"truck": truck,
			"ticket_date": start.date(),
			"time_in": start.time(),
			"time_out": end.time(),
		}
	)
	return doc


def on_stock_document_cancel(doc, method=None):
	"""doc_events hook on Purchase Receipt / Stock Entry cancel.

	The ticket links to its stock document and the stock document links back, which
	would block cancelling either. Cancelling the stock document is the legitimate
	first step (the ticket stays finalised), so let it through and clear the ticket's
	back-link so "Penerimaan Stok" can create a replacement.
	"""
	doc.ignore_linked_doctypes = (*(doc.get("ignore_linked_doctypes") or ()), "Weighbridge Ticket")
	field = "purchase_receipt" if doc.doctype == "Purchase Receipt" else "stock_entry"
	for name in frappe.get_all("Weighbridge Ticket", {field: doc.name}, pluck="name"):
		frappe.db.set_value("Weighbridge Ticket", name, field, None)


@frappe.whitelist()
def make_stock_documents(name: str) -> str:
	"""Form button for tickets submitted by hand."""
	doc = frappe.get_doc("Weighbridge Ticket", name)
	doc.check_permission("submit")
	return doc.create_stock_documents()


def finalize_due_tickets():
	"""Scheduler (every 15 min): finalise drafts whose grading arrived or timed out."""
	for name in frappe.get_all(
		"Weighbridge Ticket", {"docstatus": 0, "net_weight_kg": [">", 0]}, pluck="name"
	):
		try:
			if frappe.get_doc("Weighbridge Ticket", name).try_finalize():
				frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title=_("Weighbridge Ticket auto-finalise failed: {0}").format(name))
