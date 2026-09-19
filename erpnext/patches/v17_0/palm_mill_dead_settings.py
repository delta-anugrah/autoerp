from erpnext.palm_mill.dead_settings import remove_dead_settings


def execute():
	"""Drop the AutoERP Settings links a palm mill cannot use.

	The JSON files are edited alongside, but `sync.py` upserts rows and never deletes
	the ones a file stopped listing -- so an existing site needs this to actually lose
	them, the broken `Repost Accounting Ledger Settings` included."""
	remove_dead_settings()
