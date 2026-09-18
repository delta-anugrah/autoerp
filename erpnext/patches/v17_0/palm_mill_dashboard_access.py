import frappe

from erpnext.palm_mill.setup import (
	ADMIN_TAG,
	ADMIN_USER_ROLES,
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
		_beri_peran(nama, ROLE_PROFILES[PROFILE_ADMIN])

	# Admins made by `make admin-new` hold the roles directly and no profile at all, so the
	# pass above never sees them. They carry the tag this module sets instead.
	#
	# Not "everyone with System Manager": that also fits Administrator, the site's own
	# accounts and every test user, and handing those the module roles would widen access
	# nobody asked to widen.
	for nama in frappe.get_all(
		"Tag Link", filters={"tag": ADMIN_TAG, "document_type": "User"}, pluck="document_name"
	):
		if frappe.db.exists("User", nama):
			_beri_peran(nama, ADMIN_USER_ROLES)


def _beri_peran(nama: str, peran) -> None:
	user = frappe.get_doc("User", nama)
	sudah = {r.role for r in user.roles}
	tambah = [r for r in peran if r not in sudah and frappe.db.exists("Role", r)]
	if not tambah:
		return
	for role in tambah:
		user.append("roles", {"role": role})
	user.save(ignore_permissions=True)
	print(f"{nama} ditambah: {', '.join(tambah)}")
