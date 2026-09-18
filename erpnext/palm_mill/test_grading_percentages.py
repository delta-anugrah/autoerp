# Copyright (c) 2026, AutoERP and Contributors
# See license.txt

"""What a weighbridge ticket must refuse before it can bill a supplier.

The grading rows carry a **Percent** column, but the number an operator has in mind at
the weighbridge is kilograms. Typing `500` for "500 kg of sampah" instead of `5` used to
sail through `validate()` and produce a payable of -40,000 kg and a value of
-Rp 114,000,000 on a 10,000 kg load, all from one keystroke on the screen a krani uses
every day.

Nothing downstream caught it either: the deduction cap only limits `potongan_pct`, and
`sampah_kg` is subtracted separately from it.
"""

import frappe
from frappe.tests import IntegrationTestCase

from erpnext.palm_mill.test_fixtures import make_truck, setup_palm_mill


class IntegrationTestGradingPercentages(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		setup_palm_mill()
		make_truck("B 9001 PC")

	def _ticket(self, rows, net=10000):
		ticket = frappe.new_doc("Weighbridge Ticket")
		ticket.update(
			{
				"company": "_Test Company",
				"ticket_date": frappe.utils.today(),
				"truck": "B 9001 PC",
				"time_in": "08:03:00",
				"net_weight_kg": net,
			}
		)
		for kriteria, persen in rows:
			ticket.append("grading", {"kriteria": kriteria, "persen": persen})
		return ticket

	def test_kilograms_typed_into_the_percent_column_are_refused(self):
		"""The original bug, kept as its own test: `500` where `5` was meant."""
		ticket = self._ticket([("Sampah", 500)])

		with self.assertRaises(frappe.ValidationError):
			ticket.run_method("validate")

	def test_a_negative_percentage_is_refused(self):
		ticket = self._ticket([("Sampah", -5)])

		with self.assertRaises(frappe.ValidationError):
			ticket.run_method("validate")

	def test_the_rows_together_cannot_exceed_the_whole_load(self):
		"""Each row can be under 100 and still be nonsense together: three rows at 60 %
		describe 180 % of a truck that only ever held 100 %."""
		ticket = self._ticket([("Mentah", 60), ("Matang", 60), ("Tangkai Panjang", 60)])

		with self.assertRaises(frappe.ValidationError):
			ticket.run_method("validate")

	def test_a_load_that_is_entirely_one_criterion_is_still_allowed(self):
		"""100 % is a real reading, not an error — the guard must not round it away.

		The deduction lands at the 18 % cap from Palm Mill Settings, not at Mentah's own
		60 % rule, so a fully unripe load still pays 8,200 of 10,000 kg."""
		ticket = self._ticket([("Mentah", 100)])

		ticket.run_method("validate")

		self.assertEqual(ticket.potongan_pct, 18.0)
		self.assertEqual(ticket.net_after_deduction_kg, 8200)

	def test_an_ordinary_ticket_still_computes_the_same_numbers(self):
		"""The guard must not change arithmetic that was already correct: 5 % sampah of
		10,000 kg is 500 kg off the top, leaving 9,500 payable."""
		ticket = self._ticket([("Sampah", 5)])

		ticket.run_method("validate")

		self.assertEqual(ticket.sampah_kg, 500)
		self.assertEqual(ticket.net_after_deduction_kg, 9500)

	def test_a_ticket_with_no_grading_rows_is_untouched(self):
		"""Tickets reach ERP before grading does; an empty table is the normal early state
		and must not be mistaken for a bad one."""
		ticket = self._ticket([])

		ticket.run_method("validate")

		self.assertEqual(ticket.net_after_deduction_kg, 10000)

	def test_the_payable_weight_can_never_come_out_negative(self):
		"""Last line of defence. Whatever combination gets past the per-row checks, a
		Purchase Receipt for a negative quantity must not be reachable."""
		ticket = self._ticket([("Sampah", 5)])
		ticket.run_method("validate")

		self.assertGreaterEqual(ticket.net_after_deduction_kg, 0)
		self.assertGreaterEqual(ticket.nilai, 0)
