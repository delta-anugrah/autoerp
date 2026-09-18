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
	// Matched by the option's `value` PROPERTY, not by `option[value=""]`: Frappe
	// renders the blank choice as a bare `<option></option>` with no value attribute
	// at all, so the attribute selector never matches and the relabel silently does
	// nothing. Caught in a real browser; no Python test can see this.
	const blank = Array.from(select.options).find((o) => o.value === "");
	if (!blank) return;

	// The value attribute must be pinned BEFORE the text is changed. An `<option>`
	// with no value attribute takes its value from its own text, so relabelling alone
	// silently turns the stored value into "Lainnya / belum dicatat" - the exact thing
	// this relabel exists to avoid. Caught in a real browser.
	blank.setAttribute("value", "");
	blank.textContent = __("Lainnya / belum dicatat");
}

frappe.ui.form.on("Truck", {
	refresh(frm) {
		label_blank_vehicle_class(frm);
		if (frm.is_new()) return;
		frm.add_custom_button(__("Print QR Card"), () => erpnext.palm_mill.show_qr_cards([frm.doc.name]));
	},
});
