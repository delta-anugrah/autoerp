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
		// `support` unlocks the console's diagnostic screens, so only Administrator hands
		// it out. The server refuses it either way (`_guard_support_role`); dropping it
		// from the picker is what stops someone choosing an option that cannot be saved.
		// An account that already holds the role keeps showing it -- removing the value
		// from a Select it still stores renders the field blank, which reads as corrupt.
		if (frappe.session.user !== "Administrator" && frm.doc.role !== "support") {
			frm.set_df_property("role", "options", ["operator"]);
		}

		const input = frm.fields_dict.new_password?.$input;
		input?.attr("type", "password");

		// Typed blind, and a typo here is not found by whoever made it: the operator
		// discovers it at the mill, on a screen that only says the password is wrong.
		// Added once - `refresh` runs on every save, and a second button per save would
		// stack up down the form.
		if (input && !input.parent().find(".autograde-lihat-sandi").length) {
			// Inside the field on the right, where every login screen puts it, rather than
			// below it - a separate button under the input does not read as belonging to
			// it. The field reserves matching right padding, so the typed text never runs
			// underneath the button and a click at the end of it still reaches the input.
			const tombol = $(`<button type="button" class="autograde-lihat-sandi">${__("Show")}</button>`);
			tombol.css({
				position: "absolute",
				top: "1px",
				right: "1px",
				bottom: "1px",
				width: "4.5rem",
				padding: "0",
				border: "0",
				background: "none",
				"font-weight": "600",
				cursor: "pointer",
			});
			tombol.on("click", () => {
				// Only the field's own `type` is swapped. Rendering the value anywhere else
				// would copy the password into a second place that can be read or logged.
				const terbuka = input.attr("type") === "text";
				input.attr("type", terbuka ? "password" : "text");
				tombol.text(terbuka ? __("Show") : __("Hide"));
				tombol.attr("aria-label", terbuka ? __("Show password") : __("Hide password"));
			});
			tombol.attr("aria-label", __("Show password"));
			input.css("padding-right", "4.5rem");
			input.parent().css("position", "relative").append(tombol);
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
