from erpnext.palm_mill.setup import enable_serial_and_batch


def execute():
	"""FFB is received in batches, so the setting has to be on before the first ticket.

	`v16_0.enable_serial_batch_setting` turns it on only for sites that already have a
	Serial No or a Batch. A mill site that has not taken a delivery yet has neither, so
	upstream leaves it off and finalisation fails 417 -- which is every site on its first
	day, production included.

	Lives in `palm_mill.setup` so that a new site, which never runs this patch, gets the
	same policy from the install hook.
	"""
	enable_serial_and_batch()
