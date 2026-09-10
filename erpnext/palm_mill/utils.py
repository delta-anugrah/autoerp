# Copyright (c) 2026, AutoERP and contributors
# For license information, please see license.txt

import re
from datetime import datetime
from zoneinfo import ZoneInfo

from frappe.utils import get_system_timezone

from erpnext.stock.utils import get_combine_datetime

PURCHASED_SOURCES = ("Plasma", "Pihak Ketiga")


def normalize_plate(plate: str | None) -> str:
	"""Cross-system truck key: letters and digits only, upper case.

	Must stay identical to AutoGrade's plateNormalizer.ts.
	"""
	return re.sub(r"[^A-Za-z0-9]", "", plate or "").upper()


INDONESIAN_PLATE = re.compile(r"^([A-Z]{1,2})(\d{1,4})([A-Z]{0,3})$")


def canonical_plate(plate: str) -> str:
	"""Display form for a plate typed by a machine or a person.

	Indonesian plates (area letters, number, series letters) are spaced as on the fleet
	list, e.g. "bg9911zz" -> "BG 9911 ZZ"; anything else keeps its typing, upper-cased.
	"""
	match = INDONESIAN_PLATE.match(normalize_plate(plate))
	if match:
		return " ".join(part for part in match.groups() if part)
	return " ".join((plate or "").split()).upper()


def to_site_datetime(value) -> datetime:
	"""ISO-8601 timestamp (with or without offset) -> naive site-local datetime.

	Integrations send offsets; the ticket stores a naive local date and time.
	"""
	if isinstance(value, datetime):
		dt = value
	else:
		dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
	if dt.tzinfo is None:
		return dt
	return dt.astimezone(ZoneInfo(get_system_timezone())).replace(tzinfo=None)


def combine(date, time) -> datetime:
	"""Ticket date + Time field (a timedelta once loaded) -> datetime."""
	return get_combine_datetime(date, time if time is not None else "00:00:00")
