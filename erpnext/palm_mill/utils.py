# Copyright (c) 2026, AutoERP and contributors
# For license information, please see license.txt

import re
from datetime import datetime
from zoneinfo import ZoneInfo

import frappe
from frappe.utils import get_datetime, get_system_timezone

PURCHASED_SOURCES = ("Plasma", "Pihak Ketiga")


def normalize_plate(plate: str | None) -> str:
	"""Cross-system truck key: letters and digits only, upper case.

	Must stay identical to AutoGrade's plateNormalizer.ts.
	"""
	return re.sub(r"[^A-Za-z0-9]", "", plate or "").upper()


def to_site_datetime(value) -> datetime:
	"""Parse an ISO-8601 timestamp (with or without offset) into a naive site-local datetime.

	Integrations send offsets; the ticket stores naive site-local date and time.
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
	return get_datetime(f"{date} {frappe.utils.format_time(time) if time is not None else '00:00:00'}")
