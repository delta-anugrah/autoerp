import frappe


def execute():
	"""Harvester Premi was removed from the module. Frappe's orphan-DocType removal on migrate
	deletes the DocType record but deliberately leaves the table; nothing ever read these rows
	(the DocType posted no ledger entries), so drop it."""
	# A site restored from the demo dump still holds the DocType as a custom record, which
	# the orphan cleanup skips; drop the record before the table so neither lingers.
	if frappe.db.exists("DocType", "Harvester Premi"):
		frappe.delete_doc("DocType", "Harvester Premi", force=True, ignore_missing=True)
	if frappe.db.table_exists("Harvester Premi"):
		frappe.db.sql_ddl("drop table `tabHarvester Premi`")
