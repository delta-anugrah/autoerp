from erpnext.palm_mill.setup import hide_seed_masters, set_site_language


def execute():
	"""Indonesian by default, switchable per user; ERPNext's unused seed masters out of the way.

	Both live in `palm_mill.setup` so that a new site, which never runs this patch, gets
	the same policy from the install hook.
	"""
	set_site_language()
	hide_seed_masters()
