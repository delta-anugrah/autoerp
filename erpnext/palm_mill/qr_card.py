# Copyright (c) 2026, AutoERP and contributors
# For license information, please see license.txt

"""QR cards for truck windscreens, printed here rather than in AutoGrade.

Backoffice registers the truck in ERP Desk, so the print button belongs where they
already are (decision 2026-09-17). AutoGrade keeps its own `qr.png` endpoint as the
fallback for when the mill's internet is down and a new truck turns up.

**What goes into the code is the plate and nothing else.** Not the ERP id: a
borrowed truck has no id until someone registers it, and the gate has to keep
working while the link to this server is down - a plate means something on its own,
`TRK-0042` does not. Not supplier or driver either: those change here after the card
is stuck to the glass, and the card would then be quietly lying.

The exact string printed is `plate_normalized`, the field the gate matches on - not
`plate_number`, which is the display spelling and may carry spaces or dashes.
"""

import io

import frappe
import pyqrcode
from frappe import _

from erpnext.palm_mill.utils import is_scannable_plate, normalize_plate

# 15% of the code may be damaged and still read. Not 'L' (7%): the card lives on a
# windscreen through rain, palm dust and wiper blades. Not 'H' (30%): a denser
# pattern is harder for a gate scanner to read off a phone screen.
ERROR_CORRECTION = "M"

# Pixels per QR module, and the white margin around it. The margin is part of the
# QR spec ("quiet zone") - without it scanners often fail to find the code's edge.
SCALE = 8
QUIET_ZONE = 2


def qr_png(plate: str) -> bytes:
	"""PNG of the QR card for one plate. Raises if the gate could not read it."""
	content = qr_content(plate)
	buffer = io.BytesIO()
	pyqrcode.create(content, error=ERROR_CORRECTION).png(buffer, scale=SCALE, quiet_zone=QUIET_ZONE)
	return buffer.getvalue()


def qr_png_data_uri(plate: str) -> str:
	"""The same image as a `data:` URI, for embedding in the print format.

	Inline rather than a file attachment: a card is printed once and thrown away,
	and attaching one image per truck would leave thousands of orphaned files behind.
	"""
	content = qr_content(plate)
	code = pyqrcode.create(content, error=ERROR_CORRECTION)
	return "data:image/png;base64," + code.png_as_base64_str(scale=SCALE, quiet_zone=QUIET_ZONE)


def qr_content(plate: str) -> str:
	"""What is encoded in the card, checked to be readable before it is printed.

	Validated here rather than trusted from the caller: the plate comes from a row
	someone typed, and a card whose content the gate rejects is a card nobody can use
	- discovered at the gate, after printing, with the driver waiting.
	"""
	normalised = normalize_plate(plate)
	if not normalised:
		frappe.throw(_("Plate number must contain letters or digits"))
	if not is_scannable_plate(normalised):
		frappe.throw(
			_(
				"Plate {0} is not shaped like a plate, so a QR card printed for it would "
				"not scan at the gate. Weigh this truck without scanning."
			).format(frappe.bold(plate))
		)
	return normalised


@frappe.whitelist()
def cards(trucks: str | list[str]) -> list[dict]:
	"""Card data for the print page: one row per truck, in the order asked for.

	Trucks whose plate cannot be scanned are returned with `qr` empty rather than
	dropped silently - backoffice ticked them, and a card missing from the printout
	with no explanation looks like a bug in the printer.
	"""
	names = frappe.parse_json(trucks) if isinstance(trucks, str) else trucks
	rows = []
	for name in names:
		truck = frappe.get_doc("Truck", name)
		truck.check_permission("read")
		plate = truck.plate_normalized or normalize_plate(truck.plate_number)
		rows.append(
			{
				"name": truck.name,
				"plate_number": truck.plate_number,
				"plate_normalized": plate,
				"supplier": truck.supplier,
				"vehicle_class": truck.vehicle_class,
				"qr": qr_png_data_uri(plate) if is_scannable_plate(plate) else "",
			}
		)
	return rows
