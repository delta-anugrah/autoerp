// Copyright (c) 2026, AutoERP and contributors
// For license information, please see license.txt

frappe.listview_settings["Truck"] = {
	onload(listview) {
		// Bulk action rather than one-at-a-time: a new supplier arrives with a whole
		// fleet, and printing twenty cards one tab at a time is how people give up.
		listview.page.add_actions_menu_item(__("Print QR Cards"), () => {
			const names = listview.get_checked_items(true);
			if (!names.length) {
				frappe.msgprint(__("Select at least one truck to print"));
				return;
			}
			window.open(`/truck_qr_cards?trucks=${encodeURIComponent(JSON.stringify(names))}`, "_blank");
		});
	},
};
