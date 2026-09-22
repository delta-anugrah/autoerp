from erpnext.palm_mill.workspace_shortcuts import ensure_licence_entries


def execute():
	"""Put AutoGrade Licence into the workspace of sites that already exist.

	Both places: the left-hand menu (`Workspace Sidebar`) and the shortcut card.
	The fixture alone only reaches a brand-new site — `bench migrate` skips a
	workspace the site already has. See `workspace_shortcuts.py`."""
	ensure_licence_entries()
