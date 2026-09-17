from erpnext.palm_mill.setup import set_float_precision


def execute():
	"""Six-decimal floats came with the demo dump; a mill reads kilograms and percentages to
	two places at most.

	Lives in `palm_mill.setup` so that a new site, which never runs this patch, gets the
	same policy from the install hook.
	"""
	set_float_precision()
