import frappe

SEED_WAREHOUSES = ("Finished Goods", "Goods In Transit", "Stores", "Work In Progress")
SEED_ITEM_GROUPS = ("Services", "Sub Assemblies")


def execute():
	"""Indonesian by default, switchable per user; ERPNext's unused seed masters out of the way."""
	frappe.db.set_value("Language", "id", "enabled", 1, update_modified=False)
	frappe.db.set_single_value("System Settings", "language", "id")
	# Users pinned to the old site default now follow the new one; the menu switches them back.
	frappe.db.sql("update `tabUser` set language = NULL where language = 'en-US'")

	# Seed masters ERPNext creates for every company. Hidden only where they carry nothing.
	for wh in frappe.get_all("Warehouse", filters={"warehouse_name": ("in", SEED_WAREHOUSES)}, pluck="name"):
		if not frappe.db.exists("Stock Ledger Entry", {"warehouse": wh}):
			frappe.db.set_value("Warehouse", wh, "disabled", 1, update_modified=False)
	for ig in SEED_ITEM_GROUPS:
		if (
			frappe.db.exists("Item Group", ig)
			and not frappe.db.exists("Item", {"item_group": ig})
			and not frappe.db.exists("Item Group", {"parent_item_group": ig})
		):
			frappe.delete_doc("Item Group", ig, ignore_permissions=True, force=True)
