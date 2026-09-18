import frappe

from erpnext.palm_mill.setup import (
	PROFILE_ADMIN,
	ROLE_PROFILES,
	setup_batch_access,
	setup_role_profiles,
)


def execute():
	"""Make the mill workspace draw for the customer's own admin.

	`System Manager` does not read transactions in ERPNext, so an admin created before
	this ran sees four cards stuck loading and a permission error on Stock Entry. Adds the
	module roles to the `Admin Pabrik` profile -- and to the users who already hold it,
	since a profile only applies its roles when it is attached.
	"""
	setup_role_profiles()
	setup_batch_access()

	if not frappe.db.exists("Role Profile", PROFILE_ADMIN):
		return

	profil = frappe.get_doc("Role Profile", PROFILE_ADMIN)
	punya = {r.role for r in profil.roles}
	kurang = [r for r in ROLE_PROFILES[PROFILE_ADMIN] if r not in punya and frappe.db.exists("Role", r)]
	if kurang:
		for role in kurang:
			profil.append("roles", {"role": role})
		profil.save(ignore_permissions=True)
		print(f"{PROFILE_ADMIN} ditambah: {', '.join(kurang)}")

	# A profile hands its roles over on attach, so users who already carry it keep the
	# roles they were given at the time -- re-saving is what pushes the new ones down.
	for nama in frappe.get_all(
		"User Role Profile", filters={"role_profile": PROFILE_ADMIN, "parenttype": "User"}, pluck="parent"
	):
		user = frappe.get_doc("User", nama)
		sudah = {r.role for r in user.roles}
		tambah = [r for r in ROLE_PROFILES[PROFILE_ADMIN] if r not in sudah and frappe.db.exists("Role", r)]
		if tambah:
			for role in tambah:
				user.append("roles", {"role": role})
			user.save(ignore_permissions=True)
			print(f"{nama} ditambah: {', '.join(tambah)}")
