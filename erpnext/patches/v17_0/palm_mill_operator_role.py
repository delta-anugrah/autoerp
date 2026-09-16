"""Fill `role` for accounts created before the field existed.

Everyone becomes `operator`. Raising someone to `support` is a per-person
decision, never a side effect of a migration.
"""

import frappe


def execute():
    frappe.reload_doc("palm_mill", "doctype", "autograde_operator")
    frappe.db.sql(
        """UPDATE `tabAutoGrade Operator`
           SET role = 'operator'
           WHERE role IS NULL OR role = ''"""
    )
