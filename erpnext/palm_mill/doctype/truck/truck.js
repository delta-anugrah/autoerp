// Copyright (c) 2026, AutoERP and contributors
// For license information, please see license.txt

// The QR card is printed here, not in AutoGrade: backoffice registers the truck in
// Desk, so the button belongs where they already are. The gate console keeps its own
// endpoint as the fallback for when the mill's internet is down.
function open_qr_cards(names) {
	if (!names.length) return;
	// A new tab, not a download: the sheet is cut apart with scissors and is often
	// reprinted for one truck, so it should stay open next to the list.
	window.open(`/truck_qr_cards?trucks=${encodeURIComponent(JSON.stringify(names))}`, "_blank");
}

frappe.ui.form.on("Truck", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Print QR Card"), () => open_qr_cards([frm.doc.name]));
	},
});
