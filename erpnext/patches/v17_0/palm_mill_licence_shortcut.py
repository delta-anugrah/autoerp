from erpnext.palm_mill.workspace_shortcuts import ensure_licence_shortcut


def execute():
	"""Put the AutoGrade Licence shortcut on the workspace of sites that already exist.

	The fixture alone only reaches a brand-new site: `bench migrate` skips a
	workspace the site already has. See `workspace_shortcuts.py`."""
	ensure_licence_shortcut()
