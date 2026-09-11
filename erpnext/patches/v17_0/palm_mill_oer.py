import frappe

from erpnext.palm_mill.setup import set_defaults


def execute():
	"""OER is now computed by the Oil Extraction Rate report; the never-written Batch field
	that used to carry a demo value would only contradict it."""
	frappe.delete_doc_if_exists("Custom Field", "Batch-custom_oer")
	set_defaults()  # points cpo_item / kernel_item at CPO / PK where those items exist
