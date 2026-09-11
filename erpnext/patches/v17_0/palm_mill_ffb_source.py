import frappe

# Inti / Plasma / Pihak Ketiga -> Internal / External. Plasma and third-party fruit were
# always handled identically (both bought); the plasma-vs-agent distinction stays on the
# Supplier Group. rename_doc re-points every Link field on every table — tickets, receipts,
# stock entries and the GL dimension rows — and merge folds the two bought sources into one.
RENAMES = (("Inti", "Internal", False), ("Plasma", "External", False), ("Pihak Ketiga", "External", True))


def execute():
	for old, new, merge in RENAMES:
		if not frappe.db.exists("Sumber TBS", old):
			continue
		if frappe.db.exists("Sumber TBS", new) and not merge:
			merge = True  # a partial earlier run already created the target
		frappe.rename_doc("Sumber TBS", old, new, merge=merge, force=True)
	frappe.db.commit()
