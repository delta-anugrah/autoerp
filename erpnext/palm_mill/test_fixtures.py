# Copyright (c) 2026, AutoERP and contributors
# For license information, please see license.txt

"""Shared fixtures for Palm Mill tests, on top of ERPNext's standard test records
(_Test Company, _Test Supplier, _Test Warehouse - _TC, _Test Buying Price List)."""

import frappe

from erpnext.stock.doctype.item.test_item import make_item

COMPANY = "_Test Company"
WAREHOUSE = "_Test Warehouse - _TC"
COST_CENTER = "_Test Cost Center - _TC"
PRICE_LIST = "_Test Palm Mill Buying"  # INR, like _Test Company; the standard buying test list is USD
TBS_ITEM = "_Test TBS"
PLASMA_SUPPLIER = "_Test Supplier"  # group "_Test Supplier Group"
PLASMA_GROUP = "_Test Supplier Group"
AGEN_GROUP = "_Test Agen TBS"
AGEN_SUPPLIER = "_Test Agen Sawit"
BLOK = "_Test Blok"
PRICE = 2850.0

GRADING = [
	{"kriteria": "Mentah", "persen": 9.95},
	{"kriteria": "Tangkai Panjang", "persen": 5.58},
	{"kriteria": "Matang", "persen": 84.47},
]
# 9.95 % x 0.60 + 5.58 % x 1.00 = 11.55 % potongan on net 9160 kg -> 8102 kg payable
EXPECTED_POTONGAN = 11.55
EXPECTED_PAYABLE = 8102


def setup_palm_mill():
	"""Idempotent: item, suppliers, price, blok, and Palm Mill Settings pointed at test records."""
	make_item(
		TBS_ITEM,
		{
			"is_stock_item": 1,
			"stock_uom": "Kg",
			"has_batch_no": 1,
			"create_new_batch": 0,
			"is_purchase_item": 1,
		},
	)
	if not frappe.db.exists("Supplier Group", AGEN_GROUP):
		frappe.get_doc({"doctype": "Supplier Group", "supplier_group_name": AGEN_GROUP}).insert()
	if not frappe.db.exists("Supplier", AGEN_SUPPLIER):
		frappe.get_doc(
			{"doctype": "Supplier", "supplier_name": AGEN_SUPPLIER, "supplier_group": AGEN_GROUP}
		).insert()
	if not frappe.db.exists("Price List", PRICE_LIST):
		frappe.get_doc(
			{
				"doctype": "Price List",
				"price_list_name": PRICE_LIST,
				"currency": "INR",
				"buying": 1,
				"enabled": 1,
			}
		).insert()
	if not frappe.db.exists("Item Price", {"item_code": TBS_ITEM, "price_list": PRICE_LIST}):
		frappe.get_doc(
			{
				"doctype": "Item Price",
				"item_code": TBS_ITEM,
				"price_list": PRICE_LIST,
				"price_list_rate": PRICE,
			}
		).insert()
	# The FFB sources every ticket links to, and the estate and division of the block; the demo
	# dump had them, a clean site has not.
	for doctype, title in (
		("Sumber TBS", "Internal"),
		("Sumber TBS", "External"),
		("Kebun", "Sungai Rambang"),
		("Divisi", "I"),
	):
		if not frappe.db.exists(doctype, title):
			frappe.get_doc({"doctype": doctype, "title": title}).insert()
	if not frappe.db.exists("Blok", BLOK):
		frappe.get_doc(
			{"doctype": "Blok", "blok_code": BLOK, "kebun": "Sungai Rambang", "divisi": "I"}
		).insert()

	settings = frappe.get_doc("Palm Mill Settings")
	settings.update(
		{
			"tbs_item": TBS_ITEM,
			"tbs_warehouse": WAREHOUSE,
			"purchase_cost_center": COST_CENTER,
			"buying_price_list": PRICE_LIST,
			"inti_expense_account": "Stock Adjustment - _TC",
			"max_potongan_pct": 18,
			"default_potongan_pct": 0,
			"grading_timeout_hours": 6,
			"match_window_hours": 2,
			"create_stock_documents_on_submit": 0,
		}
	)
	if not settings.grading_rules:
		for kriteria, pct in (("Mentah", 60), ("Lewat Matang", 15), ("Tangkai Panjang", 100)):
			settings.append("grading_rules", {"kriteria": kriteria, "deduction_pct": pct})
	settings.save()


def make_truck(plate, supplier=None, **kwargs):
	if frappe.db.exists("Truck", plate):
		return frappe.get_doc("Truck", plate)
	return frappe.get_doc(
		{
			"doctype": "Truck",
			"plate_number": plate,
			"supplier": supplier,
			"vehicle_class": "Dump Truck",
			**kwargs,
		}
	).insert()


def make_ticket(truck, gross=14560, tare=5400, grading=None, **kwargs):
	values = {
		"doctype": "Weighbridge Ticket",
		"company": COMPANY,
		"ticket_date": frappe.utils.today(),
		"truck": truck,
		"time_in": "08:03:00",
		"time_out": "08:52:00",
		"gross_weight_kg": gross,
		"tare_weight_kg": tare,
		**kwargs,
	}
	if grading:
		values["grading"] = grading
	return frappe.get_doc({k: v for k, v in values.items() if v is not None}).insert()
