// Copyright (c) 2026, AutoERP and contributors
// For license information, please see license.txt

frappe.listview_settings["Weighbridge Ticket"] = {
	get_indicator(doc) {
		const colors = {
			"Waiting Weight": "orange",
			"Waiting Grading": "yellow",
			Ready: "blue",
			Finalised: "green",
			Cancelled: "red",
		};
		return [__(doc.status), colors[doc.status] || "gray", "status,=," + doc.status];
	},
};
