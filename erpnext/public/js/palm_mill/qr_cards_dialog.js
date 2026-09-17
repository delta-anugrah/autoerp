// Copyright (c) 2026, AutoERP and contributors
// For license information, please see license.txt

// The QR cards open in a dialog on the page you are already on, not a new tab.
// Printing a card is a two-second errand in the middle of registering a truck; a tab
// switch makes you lose your place and leaves a stray tab behind every time.
//
// Loaded for both the form and the list view, so the two entry points cannot drift.
frappe.provide("erpnext.palm_mill");

erpnext.palm_mill.show_qr_cards = function (names) {
	if (!names || !names.length) {
		frappe.msgprint(__("Select at least one truck to print"));
		return;
	}

	frappe.call({
		method: "erpnext.palm_mill.qr_card.cards",
		args: { trucks: names },
		freeze: true,
		freeze_message: __("Building the cards…"),
		callback(r) {
			const cards = r.message || [];
			if (!cards.length) return;
			erpnext.palm_mill._render_qr_dialog(cards);
		},
	});
};

erpnext.palm_mill._render_qr_dialog = function (cards) {
	const unscannable = cards.filter((c) => !c.qr);
	const dialog = new frappe.ui.Dialog({
		title: __("Truck QR Cards"),
		size: "large",
		primary_action_label: __("Print cards"),
		primary_action() {
			erpnext.palm_mill._print_cards(cards);
		},
	});

	// Cards are cut apart with scissors, so the sheet is sized in millimetres even
	// here — what you see in the dialog is what comes out of the printer.
	const sheet = cards
		.filter((c) => c.qr)
		.map(
			(c) => `
			<div class="qr-card">
				<img src="${c.qr}" alt="${frappe.utils.escape_html(c.plate_normalized)}">
				<div class="qr-plate">${frappe.utils.escape_html(c.plate_number)}</div>
				<div class="qr-meta">${frappe.utils.escape_html(c.supplier || __("Internal"))}${
				c.vehicle_class ? " &middot; " + frappe.utils.escape_html(c.vehicle_class) : ""
			}</div>
			</div>`
		)
		.join("");

	// Listed rather than dropped silently: backoffice ticked these trucks, and a card
	// missing from the sheet with no explanation looks like a broken printer.
	const warning = unscannable.length
		? `<div class="qr-warning">
				<b>${__("No card printed for {0} truck(s)", [unscannable.length])}</b><br>
				${__(
					"Their plates are not shaped like a plate, so the gate scanner could not read the card. Weigh these trucks without scanning."
				)}
				<ul>${unscannable.map((c) => `<li>${frappe.utils.escape_html(c.plate_number)}</li>`).join("")}</ul>
			</div>`
		: "";

	dialog.$body.html(`
		<style>
			.qr-sheet { display:flex; flex-wrap:wrap; gap:6mm; }
			.qr-card { width:62mm; padding:4mm; text-align:center;
			           border:1px dashed #999; border-radius:2mm;
			           break-inside:avoid; page-break-inside:avoid; }
			.qr-card img { width:42mm; height:42mm; image-rendering:pixelated; }
			.qr-plate { font-size:15pt; font-weight:700; letter-spacing:.5pt; margin-top:2mm; }
			.qr-meta { font-size:8pt; color:#555; margin-top:1mm; }
			.qr-warning { border:1px solid #c1841c; background:#fff7e6;
			              padding:3mm; margin-bottom:5mm; border-radius:4px; }
		</style>
		${warning}
		<div class="qr-sheet">${sheet}</div>
	`);

	dialog.show();
};

// Printed from a hidden iframe, not `window.print()`: printing the Desk page would
// carry the sidebar, the navbar and the dialog chrome onto the paper. The iframe
// contains the cards and nothing else, so what prints is the sheet.
erpnext.palm_mill._print_cards = function (cards) {
	const printable = cards.filter((c) => c.qr);
	if (!printable.length) {
		frappe.msgprint(__("There is nothing to print"));
		return;
	}

	const sheet = printable
		.map(
			(c) => `
			<div class="qr-card">
				<img src="${c.qr}" alt="${frappe.utils.escape_html(c.plate_normalized)}">
				<div class="qr-plate">${frappe.utils.escape_html(c.plate_number)}</div>
				<div class="qr-meta">${frappe.utils.escape_html(c.supplier || __("Internal"))}${
				c.vehicle_class ? " &middot; " + frappe.utils.escape_html(c.vehicle_class) : ""
			}</div>
			</div>`
		)
		.join("");

	const frame = document.createElement("iframe");
	frame.style.cssText = "position:fixed; right:0; bottom:0; width:0; height:0; border:0;";
	document.body.appendChild(frame);

	const doc = frame.contentWindow.document;
	doc.open();
	doc.write(`<!doctype html><html><head><meta charset="utf-8"><title>${__("Truck QR Cards")}</title><style>
		@page { margin:10mm; }
		body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
		.qr-sheet { display:flex; flex-wrap:wrap; gap:6mm; }
		.qr-card { width:62mm; padding:4mm; text-align:center;
		           border:1px dashed #ccc; border-radius:2mm;
		           break-inside:avoid; page-break-inside:avoid; }
		.qr-card img { width:42mm; height:42mm; image-rendering:pixelated; }
		.qr-plate { font-size:15pt; font-weight:700; letter-spacing:.5pt; margin-top:2mm; }
		.qr-meta { font-size:8pt; color:#555; margin-top:1mm; }
	</style></head><body><div class="qr-sheet">${sheet}</div></body></html>`);
	doc.close();

	// The QR images are `data:` URIs, so there is nothing to fetch — but the browser
	// still needs a turn to lay the page out before it can measure it for printing.
	const go = () => {
		frame.contentWindow.focus();
		frame.contentWindow.print();
		// Left in place for a moment: removing the iframe while the print dialog is
		// still open cancels the job in some browsers.
		setTimeout(() => frame.remove(), 60000);
	};
	if (frame.contentWindow.document.readyState === "complete") setTimeout(go, 50);
	else frame.onload = () => setTimeout(go, 50);
};
