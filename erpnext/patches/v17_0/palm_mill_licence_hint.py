import json
import pathlib

import frappe


def execute():
	"""Samakan keterangan kolom Token di database dengan berkas DocType.

	`bench migrate` TIDAK memperbarui `description` sebuah DocField yang sudah ada
	di site — hanya struktur kolom yang disinkronkan. Jadi mengubah teksnya di
	JSON cuma menjangkau site baru, dan site yang sudah jalan tetap menampilkan
	kalimat lama. Terbukti di produksi 2026-09-22: kolom Token masih menyuruh
	`autograde.sh licence` sesudah v1.1.1 naik, padahal berkasnya sudah
	`autograde licence`.

	Kenapa itu bukan hal sepele: teks ini duduk tepat di bawah token yang akan
	disalin teknisi. `autograde.sh` hanya jalan dari `/opt/palmgrade`, jadi yang
	mengikutinya dari folder lain dijawab "command not found" — di tengah shift,
	dengan pabrik menunggu.

	Nilainya dibaca dari berkas DocType, bukan ditulis ulang di sini: dua sumber
	yang sama-sama mengeja kalimat itu pasti menyimpang cepat atau lambat.
	"""
	berkas = (
		pathlib.Path(frappe.get_app_path("erpnext"))
		/ "palm_mill/doctype/autograde_licence/autograde_licence.json"
	)
	if not berkas.exists():
		return

	for field in json.loads(berkas.read_text())["fields"]:
		nama, teks = field.get("fieldname"), field.get("description")
		if not nama or teks is None:
			continue

		sekarang = frappe.db.get_value(
			"DocField", {"parent": "AutoGrade Licence", "fieldname": nama}, "description"
		)
		if sekarang != teks:
			frappe.db.set_value(
				"DocField",
				{"parent": "AutoGrade Licence", "fieldname": nama},
				"description",
				teks,
				update_modified=False,
			)

	frappe.clear_cache(doctype="AutoGrade Licence")
