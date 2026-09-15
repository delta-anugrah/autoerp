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
		const input = frm.fields_dict.new_password?.$input;
		input?.attr("type", "password");

		// Typed blind, and a typo here is not found by whoever made it: the operator
		// discovers it at the mill, on a screen that only says the password is wrong.
		// Added once - `refresh` runs on every save, and a second button per save would
		// stack up down the form.
		if (input && !input.parent().find(".autograde-lihat-sandi").length) {
			const tombol = $(
				`<button type="button" class="btn btn-xs btn-default autograde-lihat-sandi"
				         style="margin-top:4px">${__("Show password")}</button>`
			);
			tombol.on("click", () => {
				// Only the field's own `type` is swapped. Rendering the value anywhere else
				// would copy the password into a second place that can be read or logged.
				const terbuka = input.attr("type") === "text";
				input.attr("type", terbuka ? "password" : "text");
				tombol.text(terbuka ? __("Show password") : __("Hide password"));
			});
			input.parent().append(tombol);
		}

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
