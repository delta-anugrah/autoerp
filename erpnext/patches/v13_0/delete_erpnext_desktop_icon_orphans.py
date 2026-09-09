import frappe


def execute():
	for dt, name in [
		("Desktop Icon", "ERPNext"),
		("Desktop Icon", "ERPNext Settings"),
		("Workspace Sidebar", "ERPNext Settings"),
	]:
		if frappe.db.exists(dt, name):
			frappe.delete_doc(dt, name, force=True)

	# Unhide CRM and Support desktop icons (fixture sync doesn't update existing records)
	for name in ("CRM", "Support"):
		if frappe.db.exists("Desktop Icon", name):
			frappe.db.set_value("Desktop Icon", name, "hidden", 0)
