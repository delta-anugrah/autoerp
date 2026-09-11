// Copyright (c) 2026, AutoERP and contributors
// For license information, please see license.txt

frappe.ui.form.on("Weighbridge Ticket", {
	refresh(frm) {
		if (frm.doc.docstatus === 1 && !frm.doc.purchase_receipt && !frm.doc.stock_entry) {
			frm.add_custom_button(
				__("Receive Stock"),
				() => {
					frappe.call({
						method: "erpnext.palm_mill.doctype.weighbridge_ticket.weighbridge_ticket.make_stock_documents",
						args: { name: frm.doc.name },
						freeze: true,
						freeze_message: __("Creating stock documents..."),
						callback: () => frm.reload_doc(),
					});
				},
				__("Create")
			);
		}
		if (frm.doc.autograde_url) {
			frm.add_custom_button(__("Open AutoGrade"), () => window.open(frm.doc.autograde_url, "_blank"));
		}
	},
});
