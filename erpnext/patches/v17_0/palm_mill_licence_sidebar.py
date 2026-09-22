from erpnext.palm_mill.workspace_shortcuts import ensure_licence_entries


def execute():
	"""Tambahkan AutoGrade Licence ke MENU KIRI di site yang sudah ada.

	Patch terpisah dari `palm_mill_licence_shortcut`, bukan menumpang di sana:
	patch itu sudah tercatat jalan di setiap site yang memasang v1.0.5, dan
	Frappe tidak pernah menjalankan ulang patch yang sudah ada di `Patch Log`.
	Memperluas isinya berarti perbaikan ini tidak akan pernah sampai ke site
	mana pun yang justru membutuhkannya.

	`ensure_licence_entries` mengurus menu dan shortcut sekaligus, dan keduanya
	idempotent — site yang shortcut-nya sudah ada cuma menerima entri menunya."""
	ensure_licence_entries()
