import frappe

from erpnext.palm_mill.setup import after_install
from erpnext.palm_mill.utils import normalize_plate


def execute():
	"""Bring existing sites up to the Palm Mill module: custom fields, roles, settings
	defaults, and backfills for records created before the module had controllers."""
	after_install()

	for name, plate in frappe.get_all("Truck", fields=["name", "plate_number"], as_list=True):
		frappe.db.set_value("Truck", name, "plate_normalized", normalize_plate(plate), update_modified=False)

	frappe.db.sql(
		"""update `tabWeighbridge Ticket`
		set status = case docstatus when 1 then 'Finalised' when 2 then 'Cancelled' end
		where docstatus in (1, 2) and ifnull(status, '') = ''"""
	)

	# Back-links the demo seeder never wrote: receipt per purchased ticket ...
	if frappe.db.has_column("Purchase Receipt", "custom_weighbridge_ticket"):
		frappe.db.sql(
			"""update `tabWeighbridge Ticket` t
			join `tabPurchase Receipt` pr on pr.custom_weighbridge_ticket = t.name and pr.docstatus = 1
			set t.purchase_receipt = pr.name
			where ifnull(t.purchase_receipt, '') = ''"""
		)

	# ... and the day's single aggregated Material Receipt for own-estate (Inti) tickets.
	frappe.db.sql(
		"""update `tabWeighbridge Ticket` t
		join (
			select posting_date, min(name) as name
			from `tabStock Entry`
			where docstatus = 1 and stock_entry_type = 'Material Receipt'
				and remarks like 'Penerimaan TBS Inti%%'
			group by posting_date
			having count(*) = 1
		) se on se.posting_date = t.ticket_date
		set t.stock_entry = se.name
		where t.sumber_tbs = 'Inti' and t.docstatus = 1 and ifnull(t.stock_entry, '') = ''"""
	)
