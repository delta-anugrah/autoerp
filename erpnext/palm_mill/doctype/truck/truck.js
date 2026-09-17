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
		frm.add_custom_button(__("Print QR Card"), () => open_qr_cards([frm.doc.name]));
	},
});
