# Copyright (c) 2026, AutoERP and Contributors
# See license.txt

import base64
import re

import frappe
from frappe.tests import IntegrationTestCase

from erpnext.palm_mill.qr_card import cards, qr_content, qr_png, qr_png_data_uri
from erpnext.palm_mill.test_fixtures import PLASMA_SUPPLIER, make_truck, setup_palm_mill
from erpnext.palm_mill.utils import SCANNABLE_PLATE, is_scannable_plate

EXTRA_TEST_RECORD_DEPENDENCIES = ["Supplier"]

# Copied from AutoGrade `src/palmgrade/domain/qr.py`. Written out in full rather than
# imported: the two apps run on different machines and neither can import the other,
# so the only thing that can keep them in step is a test that fails loudly.
AUTOGRADE_BENTUK_PLAT = r"^(?:[A-Z]{1,2}\d{1,5}[A-Z]{0,4}|\d{1,5}[A-Z]{1,4})$"


class IntegrationTestQRCard(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		setup_palm_mill()

	def test_scannable_plate_matches_autograde(self):
		"""The gate decides what is readable; this app only mirrors that rule.

		If the two drift apart, backoffice prints a stack of cards that the scanner
		refuses - and nobody finds out until the cards are stuck to windscreens.
		"""
		self.assertEqual(SCANNABLE_PLATE.pattern, AUTOGRADE_BENTUK_PLAT)

	def test_odd_plates_are_scannable_but_rubbish_is_not(self):
		"""Backoffice may register an odd plate after confirming the warning, so the
		gate must accept it. What must still be refused is anything that is not a
		plate at all - one bad scan otherwise adds a ghost truck to master data."""
		for plate in ("BE 4412 OFL", "B 1234", "BE 12345 OFL", "B 1 A", "1234 AB"):
			self.assertTrue(is_scannable_plate(plate), plate)

		# `1234` is rubbish, not an odd plate: a bare number could be a ticket number,
		# a weight or a price, and the gate scanner reads whatever is put in front of it.
		for rubbish in ("TRK-0042", "TRK0042", "INV-2026-0001", "https://example.id/x", "!!!", "", "1234"):
			self.assertFalse(is_scannable_plate(rubbish), rubbish)

	def test_card_encodes_the_normalised_plate_and_nothing_else(self):
		"""Supplier and driver change here after the card is on the glass; a card
		carrying them would be quietly lying. The ERP id is out for a different
		reason: a borrowed truck has none, and the gate works while offline."""
		self.assertEqual(qr_content("be-4412-ofl"), "BE4412OFL")
		self.assertEqual(qr_content("BE 4412 OFL"), qr_content("be-4412-ofl"))
		self.assertTrue(re.match(AUTOGRADE_BENTUK_PLAT, qr_content("BE 4412 OFL")))

	def test_unreadable_plate_is_refused_before_anything_is_printed(self):
		for bad in ("TRK-0042", "   ", "https://example.id/promo"):
			self.assertRaises(frappe.ValidationError, qr_content, bad)

	def test_png_is_a_png(self):
		image = qr_png("BE 4412 OFL")
		self.assertTrue(image.startswith(b"\x89PNG\r\n\x1a\n"))

		uri = qr_png_data_uri("BE 4412 OFL")
		self.assertTrue(uri.startswith("data:image/png;base64,"))
		self.assertTrue(base64.b64decode(uri.split(",", 1)[1]).startswith(b"\x89PNG"))

	def test_print_sheet_keeps_unscannable_trucks_with_an_empty_code(self):
		"""Dropping them silently makes the printout look like a broken printer."""
		good = make_truck("B 9001 QR", PLASMA_SUPPLIER)
		odd = frappe.get_doc(
			{"doctype": "Truck", "plate_number": "TRK-9002", "supplier": PLASMA_SUPPLIER}
		).insert()

		rows = cards([good.name, odd.name])
		self.assertEqual([row["name"] for row in rows], [good.name, odd.name])
		self.assertTrue(rows[0]["qr"].startswith("data:image/png;base64,"))
		self.assertEqual(rows[1]["qr"], "")
