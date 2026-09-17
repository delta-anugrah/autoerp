from erpnext.palm_mill.setup import hide_unused_roles


def execute():
	"""Trim the role picker on sites that already exist.

	Lives in `palm_mill.setup` so a new site, which never runs this patch, gets the same
	treatment from the install hook. Safe on a site with users: nothing is disabled, so
	no `Has Role` row is removed.
	"""
	hasil = hide_unused_roles()
	print(f"Disembunyikan {len(hasil['hidden'])} role.")
	dilewati = {k: v for k, v in hasil["skipped"].items() if v != "whitelist"}
	if dilewati:
		print(f"Dilewati (sudah punya domain): {', '.join(sorted(dilewati))}")
