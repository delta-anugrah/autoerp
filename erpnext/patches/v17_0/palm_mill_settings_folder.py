from erpnext.palm_mill.settings_folder import group_settings_icons


def execute():
	"""Gather Organization and AutoERP Settings under one "Pengaturan" folder.

	The JSON fixtures are edited alongside, but a site created before them still has
	both icons at the top level -- `create_desktop_icons` only inserts what is
	missing, so an existing site needs this to actually regroup them."""
	group_settings_icons()
