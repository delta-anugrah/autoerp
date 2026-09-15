import frappe

from erpnext.palm_mill.setup import set_favicon


def execute():
	"""Sites installed before the favicon was branded still show Frappe's mark in the tab.

	`after_install` only runs on a fresh site, so existing ones need this to catch up.
	Reuses the setup function, which leaves an uploaded favicon alone.
	"""
	set_favicon()
