from erpnext.palm_mill.setup import set_administrator_email


def execute():
	"""Ganti `admin@example.com` bawaan Frappe di site yang sudah jalan.

	Site baru mendapatkannya dari `after_install`; patch ini untuk yang lahir
	sebelum kebijakan itu ada. Aman dijalankan berkali-kali, dan tidak menyentuh
	site yang alamatnya sudah sengaja diganti ke alamat lain."""
	set_administrator_email()
