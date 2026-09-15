// Copyright (c) 2026, AutoERP and contributors
// For license information, please see license.txt

frappe.ui.form.on("AutoGrade Operator", {
	refresh(frm) {
		// The password is typed into the form's own field and hashed on save, so there is
		// no "Set Password" button any more: two ways to do one thing means two code paths
		// to keep in step, and the one used less is the one that drifts.

		// Masked here rather than by using the `Password` fieldtype, deliberately. That
		// fieldtype stores its value in `__Auth`, which Frappe never serves over REST —
		// and the mill has to be able to pull what it verifies. So the field stays `Data`
		// (never stored at all; `validate` hashes it and wipes it) and only the input is
		// masked, so a shoulder at the office screen reads nothing.
		frm.fields_dict.new_password?.$input?.attr("type", "password");

		// The field is always blank on an existing document — a hash cannot be turned back
		// into a password. Say so, or it reads as "this account has no password".
		if (!frm.is_new() && frm.doc.password_hash) {
			frm.set_df_property(
				"new_password",
				"description",
				__("A password is already set. Type here only to replace it.")
			);
		}
	},
});
