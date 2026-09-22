from erpnext.palm_mill.setup import set_administrator_timezone


def execute():
	"""Perbaiki zona waktu Administrator di site yang sudah jalan.

	Frappe memberinya `Asia/Kolkata` saat site dibuat. Site baru mendapat zona
	yang benar dari `after_install`; patch ini untuk yang lahir sebelumnya."""
	set_administrator_timezone()
