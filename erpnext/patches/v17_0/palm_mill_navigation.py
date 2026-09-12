import frappe

from erpnext.palm_mill.setup import setup_roles

WORKSPACE = "Pabrik Kelapa Sawit"


def execute():
	"""Land users on the mill workspace instead of Home.

	The router falls back to the public `home` workspace when a user has no
	default_workspace, and Home is only hidden for users without Workspace Manager
	— so the flag alone is not enough for the people who administer the site."""
	# The mill sidebar links the estate masters, which are System Manager only in their
	# DocType JSONs; setup_roles grants the operator read so no section renders empty.
	setup_roles()

	if not frappe.db.exists("Workspace", WORKSPACE):
		return

	# Workspace.is_hidden is on import_file's ignore_values list, so shipping the flag in
	# home.json only reaches fresh installs — existing sites need it set here.
	frappe.db.set_value("Workspace", "Home", "is_hidden", 1, update_modified=False)

	frappe.db.sql(
		"""update `tabUser`
		set default_workspace = %s
		where enabled = 1 and user_type = 'System User'
			and ifnull(default_workspace, '') = ''
			and name not in ('Administrator', 'Guest')""",
		WORKSPACE,
	)
