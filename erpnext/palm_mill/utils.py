# Copyright (c) 2026, AutoERP and contributors
# For license information, please see license.txt

import re
from datetime import datetime
from zoneinfo import ZoneInfo

import frappe
from frappe.utils import get_system_timezone

from erpnext.stock.utils import get_combine_datetime

PURCHASED_SOURCES = ("External",)


def normalize_plate(plate: str | None) -> str:
	"""Cross-system truck key: letters and digits only, upper case.

	Must stay identical to AutoGrade's plateNormalizer.ts.
	"""
	return re.sub(r"[^A-Za-z0-9]", "", plate or "").upper()


INDONESIAN_PLATE = re.compile(r"^([A-Z]{1,2})(\d{1,4})([A-Z]{0,3})$")

# What AutoGrade's gate scanner will accept, mirrored here so a QR card is never
# printed for a plate the gate cannot read.
#
# Deliberately wider than INDONESIAN_PLATE above: government, old and out-of-area
# plates are shaped differently, and backoffice may register those after confirming
# a warning. It is NOT unlimited - the two-letter cap is what keeps an ERP id like
# `TRK0042` (letters then digits, the same shape as a plate) from being scannable.
#
# Must stay identical to `_BENTUK_PLAT` in AutoGrade's `domain/qr.py`. The test
# `test_scannable_plate_matches_autograde` pins the exact pattern; if you change it
# here, change it there in the same pull request.
SCANNABLE_PLATE = re.compile(r"^[A-Z]{0,2}\d{1,5}[A-Z]{0,4}$")


def is_scannable_plate(plate: str | None) -> bool:
	"""Can AutoGrade's gate scanner read a QR card printed for this plate?"""
	return bool(SCANNABLE_PLATE.match(normalize_plate(plate)))


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


def relax_snapshot_isolation(*args, **kwargs):
	"""MariaDB 11.6+ turns a concurrent same-row update into error 1020 instead of a lock
	wait, and Frappe reads a document then updates it later in the same transaction all over
	the place (dashboard charts, naming series). Frappe shows 1020 as "Deadlock Occurred".
	Restore the pre-11.6 behaviour for this connection; older servers don't know the variable."""
	if frappe.db.db_type != "mariadb":
		return
	try:
		frappe.db.sql("set session innodb_snapshot_isolation = OFF")
	except Exception:
		pass
