// Copyright (c) 2026, AutoERP and contributors
// For license information, please see license.txt

frappe.ui.form.on("AutoGrade Operator", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Set Password"), () => {
			// Typed into a Password prompt and sent straight to the hashing method: the raw
			// value is never put on the document, so it cannot land in a version row.
			frappe.prompt(
				[
					{
						fieldname: "password",
						fieldtype: "Password",
						label: __("New Password"),
						reqd: 1,
						description: __(
							"At least 8 characters. The operator signs in to the AutoGrade console with this."
						),
					},
				],
				({ password }) => {
					frm.call({
						doc: frm.doc,
						method: "set_password",
						args: { password },
						freeze: true,
						freeze_message: __("Saving password..."),
						callback: () => {
							frm.reload_doc();
							frappe.show_alert({
								message: __("Password saved. The mill picks it up on its next pull."),
								indicator: "green",
							});
						},
					});
				},
				__("Set Password"),
				__("Save")
			);
		});
	},
});
