import frappe

from erpnext.palm_mill.setup import setup_roles

DOCTYPE = "AutoGrade Operator"


def execute():
	"""Let the integration key read the operator accounts AutoGrade signs people in with.

	The DocType JSON already carries the permission rows, but a site that synced this app
	before the rows existed keeps its old Custom DocPerms — so the grant is repeated here.
	Idempotent: `add_permission` is a no-op when the row is already there.
	"""
	setup_roles()

	if not frappe.db.exists("DocType", DOCTYPE):
		return

	for role in ("Palm Mill Integration", "Weighbridge Operator"):
		if not frappe.db.exists("Custom DocPerm", {"parent": DOCTYPE, "role": role, "permlevel": 0}):
			frappe.permissions.add_permission(DOCTYPE, role)

	frappe.db.commit()
