import frappe


def execute():
	"""Harvester Premi was removed from the module. Frappe's orphan-DocType removal on migrate
	deletes the DocType record but deliberately leaves the table; nothing ever read these rows
	(the DocType posted no ledger entries), so drop it."""
	if frappe.db.table_exists("Harvester Premi"):
		frappe.db.sql_ddl("drop table `tabHarvester Premi`")
