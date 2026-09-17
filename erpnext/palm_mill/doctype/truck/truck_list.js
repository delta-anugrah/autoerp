// Copyright (c) 2026, AutoERP and contributors
// For license information, please see license.txt

frappe.listview_settings["Truck"] = {
	onload(listview) {
		// Bulk action rather than one-at-a-time: a new supplier arrives with a whole
		// fleet, and printing twenty cards one tab at a time is how people give up.
		listview.page.add_actions_menu_item(__("Print QR Cards"), () => {
			// The "select something first" message lives in show_qr_cards, so the two
			// entry points cannot say it differently.
			erpnext.palm_mill.show_qr_cards(listview.get_checked_items(true));
		});
	},
};
