// Copyright (c) 2026, AutoERP and contributors
// For license information, please see license.txt

// The token is a single long string that has to survive a trip through AnyDesk into
// a mill PC terminal. A broken copy is the failure this screen exists to prevent:
// `autograde licence` rejects a mangled token with "signature does not match",
// which reads like a bad token rather than a bad paste. So the whole command line is
// offered ready-made, and copying is one button rather than a drag-select.

frappe.ui.form.on("AutoGrade Licence", {
	refresh(frm) {
		if (frm.is_new()) return;

		if (!frm.doc.token) {
			frm.add_custom_button(__("Issue Token"), () => issue(frm)).addClass("btn-primary");
			return;
		}

		frm.add_custom_button(__("Copy Install Command"), () => copy_command(frm));
	},
});

function issue(frm) {
	frappe.confirm(
		__("Issue a token for {0}, active until {1}? The terms cannot be changed afterwards.", [
			frm.doc.company,
			frappe.datetime.str_to_user(frm.doc.license_expires_on),
		]),
		() => {
			frappe.call({
				method: "erpnext.palm_mill.license.issue",
				args: { name: frm.doc.name },
				freeze: true,
				freeze_message: __("Signing..."),
				callback: () => {
					frm.reload_doc();
					frappe.show_alert({ message: __("Token issued"), indicator: "green" });
				},
			});
		}
	);
}

function copy_command(frm) {
	// `autograde`, bukan `autograde.sh`: itu symlink di /usr/local/bin milik PC
	// pabrik, jadi perintahnya jalan dari folder mana pun. Bentuk `./autograde.sh`
	// tetap sah, tapi cuma kalau teknisi kebetulan sedang berada di /opt/palmgrade.
	const command = `autograde licence ${frm.doc.token}`;

	// `navigator.clipboard` is unavailable over plain HTTP, and Desk is reached over
	// HTTP on some internal setups - so fall back rather than fail silently.
	if (navigator.clipboard && window.isSecureContext) {
		navigator.clipboard.writeText(command).then(
			() => frappe.show_alert({ message: __("Command copied"), indicator: "green" }),
			() => show_command(command)
		);
		return;
	}
	show_command(command);
}

function show_command(command) {
	const dialog = new frappe.ui.Dialog({
		title: __("Run this on the mill PC"),
		fields: [
			{
				fieldtype: "Code",
				fieldname: "command",
				label: __("Command"),
				default: command,
				read_only: 1,
			},
		],
	});
	dialog.show();
}
