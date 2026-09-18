from erpnext.palm_mill.setup import setup_role_profiles


def execute():
	"""Give existing sites the job titles the New User dialog offers.

	Lives in `palm_mill.setup` so a new site, which never runs this patch, gets the same
	profiles from the install hook. Only creates what is missing -- a profile someone
	edited stays as they left it.
	"""
	hasil = setup_role_profiles()
	if hasil["created"]:
		print(f"Role Profile dibuat: {', '.join(hasil['created'])}")
