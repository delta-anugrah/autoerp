from erpnext.palm_mill.hidden_fields import hide_unused_fields


def execute():
	"""Hide the native Stock Entry / Purchase Receipt fields a palm mill never fills in.

	Property Setters rather than DocType edits: these are core fields whose values
	ERPNext writes itself, so they stay functional and upstream pulls stay clean."""
	hide_unused_fields()
