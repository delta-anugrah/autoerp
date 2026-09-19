from erpnext.palm_mill.hidden_icons import hide_unused_icons


def execute():
	"""Hide the Desk icons a palm mill never opens.

	`hidden` is a column on the site's own Desktop Icon rows, not something this app
	ships, so a site that already exists keeps the full grid until this runs."""
	hide_unused_icons()
