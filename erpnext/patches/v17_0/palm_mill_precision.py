import frappe


def execute():
	"""Six-decimal floats came with the demo dump; a mill reads kilograms and percentages to
	two places at most, and Frappe uses this one setting for every Float and Percent shown."""
	frappe.db.set_single_value("System Settings", "float_precision", "2")
	frappe.db.set_default("float_precision", "2")  # what bootinfo serves; only a UI save refreshes it
