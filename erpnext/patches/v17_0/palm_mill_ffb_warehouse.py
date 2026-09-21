from erpnext.palm_mill.setup import ensure_ffb_warehouse


def execute():
	"""An existing site can have zero warehouses that are able to receive FFB.

	`hide_seed_masters()` disables all four of ERPNext's starter warehouses and nothing
	ever created a replacement, so what stays enabled is `All Warehouses - <ABBR>` -- a
	group node, which ERPNext refuses for transactions. The refusal only surfaces when
	somebody presses Receive Stock, so the site looks healthy until the first real truck.

	Measured on `app.smagri.id` on 2026-09-21: four non-group warehouses all
	`disabled: 1`, and FFB receipt impossible until a warehouse was made by hand.

	Lives in `palm_mill.setup` so that a new site, which never runs this patch, gets the
	same warehouse from the wizard hook.
	"""
	ensure_ffb_warehouse()
