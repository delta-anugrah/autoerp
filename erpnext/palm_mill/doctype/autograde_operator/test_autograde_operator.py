# Copyright (c) 2026, AutoERP and Contributors
# See license.txt

"""AutoGrade Operator: the account an operator signs in to the mill console with.

AutoERP owns these accounts and hashes the passwords; AutoGrade pulls them down and
verifies locally, because the mill console has to let someone in while the internet is
down. That is the whole reason `password_hash` is a readable field here instead of
Frappe's own `User` password, which lives in `__Auth` and is deliberately never served
over REST.

What these tests pin is therefore not "a DocType saves": it is that the hash AutoGrade
will verify offline is a real passlib hash, that the raw password never survives
anywhere, and that the integration role can read that field but cannot write the account.
"""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.password import passlibctx

from erpnext.palm_mill.setup import INTEGRATION_ROLE, INTEGRATION_USER_ROLES

EXTRA_TEST_RECORD_DEPENDENCIES = ["User"]

DOCTYPE = "AutoGrade Operator"
EMAIL = "operator.satu@pks.local"
PASSWORD = "sawit2026"
INTEGRATION_USER = "palm-mill-operator-integration@example.com"
PLAIN_USER = "palm-mill-operator-nobody@example.com"


def make_user(email, roles):
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": email.split("@")[0],
				"send_welcome_email": 0,
				"roles": [{"role": role} for role in roles],
			}
		).insert(ignore_permissions=True)
	return email


def make_operator(email=EMAIL, password=PASSWORD, full_name="Operator Satu", active=1):
	if frappe.db.exists("AutoGrade Operator", email):
		frappe.delete_doc("AutoGrade Operator", email, force=True, ignore_permissions=True)
	doc = frappe.get_doc(
		{
			"doctype": "AutoGrade Operator",
			"email": email,
			"full_name": full_name,
			"active": active,
		}
	).insert(ignore_permissions=True)
	if password:
		doc.set_password(password)
		doc.reload()
	return doc


class IntegrationTestAutoGradeOperator(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_user(INTEGRATION_USER, INTEGRATION_USER_ROLES)
		make_user(PLAIN_USER, ["Employee"])

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def test_the_stored_hash_verifies_the_password_and_is_not_the_password(self):
		"""AutoGrade verifies this string offline, so it has to be a real passlib hash —
		and the raw password must not be recoverable from anything we store."""
		operator = make_operator()

		self.assertTrue(passlibctx.verify(PASSWORD, operator.password_hash))
		self.assertNotIn(PASSWORD, operator.password_hash)
		self.assertTrue(operator.password_hash.startswith("$pbkdf2-sha256$"))

	def test_a_new_password_replaces_the_old_hash(self):
		operator = make_operator()
		before = operator.password_hash

		operator.set_password("gantisandi2026")
		operator.reload()

		self.assertNotEqual(operator.password_hash, before)
		self.assertTrue(passlibctx.verify("gantisandi2026", operator.password_hash))
		self.assertFalse(passlibctx.verify(PASSWORD, operator.password_hash))

	def test_a_password_shorter_than_the_rule_is_refused(self):
		"""Eight characters, the same floor palmgrade-api enforces. A weaker account here
		is a weaker account on every mill PC that pulls it."""
		operator = make_operator(password=None)

		self.assertRaises(frappe.ValidationError, operator.set_password, "sawit12")
		operator.reload()
		self.assertFalse(operator.password_hash)

	def test_the_email_is_the_key_and_is_stored_lower_case(self):
		"""AutoGrade derives the local operator id from the email, so one address typed
		two ways must not become two accounts."""
		operator = make_operator(email="Operator.DUA@PKS.local", password=PASSWORD)

		self.assertEqual(operator.name, "operator.dua@pks.local")
		self.assertEqual(operator.email, "operator.dua@pks.local")

	def test_two_accounts_cannot_share_one_email(self):
		"""Inserted directly rather than through `make_operator`: that helper deletes an
		existing document first, which is what makes it reusable and would also make this
		assertion unfalsifiable."""
		make_operator(email="operator.tiga@pks.local")

		duplicate = frappe.get_doc(
			{
				"doctype": "AutoGrade Operator",
				"email": "Operator.Tiga@pks.local",
				"full_name": "Operator Tiga Lagi",
				"active": 1,
			}
		)

		self.assertRaises(frappe.DuplicateEntryError, duplicate.insert, ignore_permissions=True)

	def test_an_address_that_is_not_an_email_is_refused(self):
		self.assertRaises(frappe.ValidationError, make_operator, email="operator-empat")

	def test_the_integration_user_can_read_the_hash_but_not_write_the_account(self):
		"""The read is what makes offline login possible: AutoGrade pulls the hash. The
		write must stay shut — accounts are owned here, and a mill must never edit them."""
		make_operator(email="operator.lima@pks.local")
		frappe.set_user(INTEGRATION_USER)

		rows = frappe.get_all(
			"AutoGrade Operator",
			filters={"email": "operator.lima@pks.local"},
			fields=["email", "full_name", "active", "password_hash", "modified"],
		)

		self.assertEqual(len(rows), 1)
		self.assertTrue(rows[0].password_hash)
		self.assertFalse(frappe.has_permission("AutoGrade Operator", "write"))
		self.assertFalse(frappe.has_permission("AutoGrade Operator", "create"))

	def test_a_user_without_the_integration_role_reads_nothing(self):
		make_operator(email="operator.enam@pks.local")
		frappe.set_user(PLAIN_USER)

		self.assertFalse(frappe.has_permission("AutoGrade Operator", "read"))

	def test_a_deactivated_operator_is_still_pulled_so_the_mill_can_act_on_it(self):
		"""Dropping the row from the pull would leave the mill with a stale account that
		still signs in. The console needs to see `active = 0` and end the sessions."""
		make_operator(email="operator.tujuh@pks.local", active=0)
		frappe.set_user(INTEGRATION_USER)

		rows = frappe.get_all(
			"AutoGrade Operator",
			filters={"email": "operator.tujuh@pks.local"},
			fields=["email", "active"],
		)

		self.assertEqual([row.active for row in rows], [0])

	def test_a_password_typed_on_the_form_is_hashed_on_save(self):
		"""One Save creates a usable account: email, name and password together.

		Before this, the password needed a second step after the document existed, which
		is a step people skip — leaving accounts that cannot sign in.
		"""
		operator = frappe.get_doc(
			{
				"doctype": DOCTYPE,
				"email": "operator.form@pks.local",
				"full_name": "Operator Form",
				"active": 1,
				"new_password": PASSWORD,
			}
		).insert(ignore_permissions=True)

		self.assertTrue(passlibctx.verify(PASSWORD, operator.password_hash))

	def test_the_typed_password_is_never_stored_anywhere(self):
		"""`track_changes` is on, so every Save writes a Version row. A raw password left
		on the document would sit in that history — readable by anyone who can open the
		document, including passwords already replaced.
		"""
		operator = frappe.get_doc(
			{
				"doctype": DOCTYPE,
				"email": "operator.delapan@pks.local",
				"full_name": "Operator Delapan",
				"active": 1,
				"new_password": PASSWORD,
			}
		).insert(ignore_permissions=True)
		operator.reload()

		self.assertFalse(operator.new_password, "the typed password survived on the document")
		stored = frappe.db.get_value(DOCTYPE, operator.name, ["password_hash", "new_password"], as_dict=True)
		self.assertFalse(stored.new_password, "the typed password reached the database")
		self.assertNotIn(PASSWORD, stored.password_hash)

		versions = frappe.get_all(
			"Version", filters={"ref_doctype": DOCTYPE, "docname": operator.name}, pluck="data"
		)
		for data in versions:
			self.assertNotIn(PASSWORD, data or "", "the typed password reached a Version row")

	def test_leaving_the_password_empty_keeps_the_one_already_set(self):
		"""Backoffice fixing a typo in a name must not lock the operator out of the
		console — which is what re-hashing an empty value would do."""
		operator = make_operator(email="operator.sembilan@pks.local")
		before = operator.password_hash

		operator.full_name = "Nama Dibetulkan"
		operator.save(ignore_permissions=True)
		operator.reload()

		self.assertEqual(operator.password_hash, before)
		self.assertTrue(passlibctx.verify(PASSWORD, operator.password_hash))

	def test_a_short_password_typed_on_the_form_is_refused(self):
		"""Same floor as everywhere else. Checked before the document is written, so a
		refused password cannot leave a half-made account behind."""
		operator = frappe.get_doc(
			{
				"doctype": DOCTYPE,
				"email": "operator.sepuluh@pks.local",
				"full_name": "Operator Sepuluh",
				"active": 1,
				"new_password": "sawit12",
			}
		)

		self.assertRaises(frappe.ValidationError, operator.insert, ignore_permissions=True)
		self.assertFalse(frappe.db.exists(DOCTYPE, "operator.sepuluh@pks.local"))

	def test_the_integration_role_is_the_one_autograde_already_uses(self):
		"""One key, one role: the pull rides the credentials `create_integration_user`
		already issues, so no second secret has to reach the mill."""
		self.assertIn(INTEGRATION_ROLE, INTEGRATION_USER_ROLES)

	def test_backoffice_can_reach_this_doctype_from_the_workspace(self):
		"""A DocType with no way in is a DocType nobody uses.

		Reported by the operator 2026-09-15: the accounts could only be found through
		search. Frappe needs the shortcut in **both** places — `shortcuts` defines it,
		`content` decides whether it is laid out on screen — so one without the other
		looks done in the JSON and changes nothing in the browser.
		"""
		workspace = frappe.get_doc("Workspace", "Pabrik Kelapa Sawit")

		self.assertTrue(
			any(row.link_to == DOCTYPE for row in workspace.shortcuts),
			f"{DOCTYPE} is missing from the workspace shortcuts",
		)
		self.assertIn(
			"AutoGrade Operators",
			workspace.content or "",
			f"{DOCTYPE} has a shortcut but is not laid out in `content`, so it stays invisible",
		)

	def test_backoffice_can_reach_this_doctype_from_the_sidebar(self):
		"""The shortcut above sits in the page body, below seven number cards and five
		charts — so it needs scrolling to find. The sidebar is the standing navigation,
		and it is a separate fixture (`workspace_sidebar/`), which is why adding the
		shortcut alone did not put it there.
		"""
		sidebar = frappe.get_doc("Workspace Sidebar", "Pabrik Kelapa Sawit")

		self.assertTrue(
			any(item.link_to == DOCTYPE for item in sidebar.items),
			f"{DOCTYPE} is missing from the workspace sidebar",
		)

	def test_peran_default_operator(self):
		"""A new account is an operator until someone says otherwise."""
		doc = frappe.get_doc(
			{
				"doctype": DOCTYPE,
				"email": "peran-default@example.com",
				"full_name": "Peran Default",
			}
		).insert(ignore_permissions=True)
		self.assertEqual(doc.peran, "operator")

	def test_peran_support_tersimpan(self):
		"""`support` is a value the field accepts, not just free text."""
		doc = frappe.get_doc(
			{
				"doctype": DOCTYPE,
				"email": "peran-support@example.com",
				"full_name": "Peran Support",
				"peran": "support",
			}
		).insert(ignore_permissions=True)
		self.assertEqual(frappe.db.get_value(DOCTYPE, doc.name, "peran"), "support")
