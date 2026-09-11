import frappe
from frappe import _
from frappe.utils import fmt_money, formatdate

# Repack rows are tagged by ERPNext itself: the input has a source warehouse and no target,
# every output has a target and no source (stock_entry.py mark_finished_and_scrap_items).
NEEDED = ("tbs_item", "cpo_item", "kernel_item")


def execute(filters=None):
	filters = frappe._dict(filters or {})
	s = frappe.get_single("Palm Mill Settings")
	missing = [f for f in NEEDED if not s.get(f)]
	if missing:
		labels = ", ".join(_(frappe.get_meta("Palm Mill Settings").get_label(f)) for f in missing)
		frappe.throw(_("Please set {0} in Palm Mill Settings").format(labels))

	data = get_data(filters, s)
	return get_columns(), data, None, get_chart(data), get_summary(data)


def get_data(filters, s):
	se = frappe.qb.DocType("Stock Entry")
	d = frappe.qb.DocType("Stock Entry Detail")
	rows = (
		frappe.qb.from_(se)
		.inner_join(d)
		.on(d.parent == se.name)
		.select(se.name, se.posting_date, d.item_code, d.transfer_qty, d.s_warehouse, d.t_warehouse)
		.where(
			(se.docstatus == 1)
			& (se.purpose == "Repack")
			& (se.company == filters.company)
			& (se.posting_date >= filters.from_date)
			& (se.posting_date <= filters.to_date)
		)
		.orderby(se.posting_date)
		.orderby(se.name)
	).run(as_dict=True)

	by_entry = {}
	for r in rows:
		e = by_entry.setdefault(
			r.name,
			{
				"posting_date": r.posting_date,
				"stock_entry": r.name,
				"tbs_kg": 0.0,
				"cpo_kg": 0.0,
				"kernel_kg": 0.0,
				"byproduct_kg": 0.0,
			},
		)
		is_input = bool(r.s_warehouse) and not r.t_warehouse
		if is_input:
			if r.item_code == s.tbs_item:
				e["tbs_kg"] += r.transfer_qty
		elif r.item_code == s.cpo_item:
			e["cpo_kg"] += r.transfer_qty
		elif r.item_code == s.kernel_item:
			e["kernel_kg"] += r.transfer_qty
		else:
			e["byproduct_kg"] += r.transfer_qty

	data = []
	for e in by_entry.values():
		if not e["tbs_kg"]:
			continue  # a repack that consumed no FFB has no extraction rate
		out = e["cpo_kg"] + e["kernel_kg"] + e["byproduct_kg"]
		e["oer"] = pct(e["cpo_kg"], e["tbs_kg"])
		e["ker"] = pct(e["kernel_kg"], e["tbs_kg"])
		e["total_out"] = pct(out, e["tbs_kg"])
		e["losses"] = round(100 - e["total_out"], 2) if e["tbs_kg"] else 0.0
		data.append(e)
	return data


def pct(part, whole):
	return round(part / whole * 100, 2) if whole else 0.0


def get_columns():
	return [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{
			"label": _("Stock Entry"),
			"fieldname": "stock_entry",
			"fieldtype": "Link",
			"options": "Stock Entry",
			"width": 160,
		},
		{
			"label": _("FFB Processed (kg)"),
			"fieldname": "tbs_kg",
			"fieldtype": "Int",
			"width": 140,
		},
		{"label": _("CPO (kg)"), "fieldname": "cpo_kg", "fieldtype": "Int", "width": 120},
		{"label": _("OER (%)"), "fieldname": "oer", "fieldtype": "Percent", "precision": 2, "width": 90},
		{
			"label": _("Kernel (kg)"),
			"fieldname": "kernel_kg",
			"fieldtype": "Int",
			"width": 120,
		},
		{"label": _("KER (%)"), "fieldname": "ker", "fieldtype": "Percent", "precision": 2, "width": 90},
		{
			"label": _("By-products (kg)"),
			"fieldname": "byproduct_kg",
			"fieldtype": "Int",
			"width": 130,
		},
		{
			"label": _("Total Out (%)"),
			"fieldname": "total_out",
			"fieldtype": "Percent",
			"precision": 2,
			"width": 110,
		},
		{
			"label": _("Losses (%)"),
			"fieldname": "losses",
			"fieldtype": "Percent",
			"precision": 2,
			"width": 100,
		},
	]


def get_chart(data):
	return {
		"data": {
			# day of month: with 70-odd daily points each label gets room for two characters
			"labels": [formatdate(e["posting_date"], "d") for e in data],
			"datasets": [
				{"name": _("OER (%)"), "values": [e["oer"] for e in data]},
				{"name": _("KER (%)"), "values": [e["ker"] for e in data]},
			],
		},
		"type": "line",
		"fieldtype": "Percent",
	}


def get_summary(data):
	if not data:
		return None
	tbs = sum(e["tbs_kg"] for e in data)
	cpo = sum(e["cpo_kg"] for e in data)
	kernel = sum(e["kernel_kg"] for e in data)
	oer = pct(cpo, tbs)
	return [
		{
			"value": oer,
			"indicator": "Green" if oer >= 20 else "Red",
			"label": _("Period OER"),
			"datatype": "Percent",
		},
		{"value": pct(kernel, tbs), "indicator": "Blue", "label": _("Period KER"), "datatype": "Percent"},
		{
			"value": fmt_money(tbs, precision=0),
			"indicator": "Grey",
			"label": _("FFB Processed (kg)"),
			"datatype": "Data",
		},
		{
			"value": fmt_money(cpo, precision=0),
			"indicator": "Grey",
			"label": _("CPO Produced (kg)"),
			"datatype": "Data",
		},
	]
