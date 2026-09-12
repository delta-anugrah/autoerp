import frappe


def execute():
	"""Drop every saved Desktop Layout so the launcher renders from `tabDesktop Icon` again.

	The desktop page prefers a user's saved layout over the icon table, and nothing ever
	invalidates that snapshot — so once a user has pressed Save in the launcher's edit
	mode, no later change to the shipped icons reaches them. Users can rearrange again."""
	frappe.db.delete("Desktop Layout")
	frappe.cache.delete_key("desktop_icons")
	frappe.cache.delete_key("bootinfo")
