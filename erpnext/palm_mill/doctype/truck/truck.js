// Copyright (c) 2026, AutoERP and contributors
// For license information, please see license.txt

// The QR card is printed here, not in AutoGrade: backoffice registers the truck in
// Desk, so the button belongs where they already are. The gate console keeps its own
// endpoint as the fallback for when the mill's internet is down.
//
// The cards open in a dialog (`qr_cards_dialog.js`), not a new tab: printing one is a
// two-second errand in the middle of registering a truck.

// The blank first option of Vehicle Class means "not recorded", and a blank line in a
// dropdown reads like a rendering fault. Relabel it in the browser ONLY: the stored
// value stays the empty string it has always been, so existing trucks, the AutoGrade
// contract and every report are untouched. Writing a literal "Lainnya" into the
// options would create a second way of saying "unknown" and split the data in two.
function label_blank_vehicle_class(frm) {
	const field = frm.get_field("vehicle_class");
	const select = field && field.$input && field.$input.get(0);
	if (!select) return;
	const blank = select.querySelector('option[value=""]');
	if (blank) blank.textContent = __("Lainnya / belum dicatat");
}

frappe.ui.form.on("Truck", {
	refresh(frm) {
		label_blank_vehicle_class(frm);
		if (frm.is_new()) return;
		frm.add_custom_button(__("Print QR Card"), () => erpnext.palm_mill.show_qr_cards([frm.doc.name]));
	},
});
