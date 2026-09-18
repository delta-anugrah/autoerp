# Copyright (c) 2026, AutoERP and Contributors
# See license.txt

"""The job titles the New User dialog offers.

Frappe's quick-entry dialog cannot show the `roles` table -- it is a Table field, and
hidden -- so the only role control that fits there is `role_profiles`, the one field on
User marked `allow_in_quick_entry`. Without profiles, creating a user is two screens:
save first, then find the role checkboxes on the saved form.

Profiles also change what the person picking has to know. "Krani Timbang" is a job at
the mill; `Weighbridge Operator` + `Purchase User` + `Stock User` is a permission puzzle,
and getting it wrong is invisible until somebody cannot open a screen.
"""

import frappe
from frappe.tests import IntegrationTestCase

from erpnext.palm_mill import setup


class IntegrationTestRoleProfiles(IntegrationTestCase):
	def test_the_three_mill_profiles_exist(self):
		setup.setup_role_profiles()

		for nama in setup.ROLE_PROFILES:
			self.assertTrue(frappe.db.exists("Role Profile", nama), f"{nama} harus ada")

	def test_each_profile_carries_the_roles_it_promises(self):
		"""Through the patch, because `setup_role_profiles` only ever creates.

		A site that already has `Admin Pabrik` from before the module roles were added keeps
		it as it was -- deliberately, so an edited profile survives a migrate. The patch is
		what brings an existing profile up to date, so that is what this asserts.
		"""
		from erpnext.patches.v17_0 import palm_mill_dashboard_access

		palm_mill_dashboard_access.execute()

		for nama, peran in setup.ROLE_PROFILES.items():
			doc = frappe.get_doc("Role Profile", nama)
			self.assertEqual({r.role for r in doc.roles}, set(peran), f"isi {nama} tidak cocok")

	def test_every_role_used_is_one_the_picker_still_offers(self):
		"""A profile pointing at a hidden role would put it back on a user by the side door."""
		for nama, peran in setup.ROLE_PROFILES.items():
			for role in peran:
				self.assertIn(role, setup.MILL_ROLES, f"{nama} memakai {role} yang disembunyikan")

	def test_applying_a_profile_gives_the_user_those_roles(self):
		setup.setup_role_profiles()
		email = "uji.profil.krani@test.local"

		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Uji Profil",
				"user_type": "System User",
				"send_welcome_email": 0,
				"role_profiles": [{"role_profile": setup.PROFILE_KRANI}],
			}
		).insert(ignore_permissions=True)

		self.assertIn(setup.OPERATOR_ROLE, frappe.get_roles(email))

	def test_running_it_twice_changes_nothing_the_second_time(self):
		setup.setup_role_profiles()
		sebelum = {
			nama: sorted(r.role for r in frappe.get_doc("Role Profile", nama).roles)
			for nama in setup.ROLE_PROFILES
		}

		hasil = setup.setup_role_profiles()

		sesudah = {
			nama: sorted(r.role for r in frappe.get_doc("Role Profile", nama).roles)
			for nama in setup.ROLE_PROFILES
		}
		self.assertEqual(sebelum, sesudah)
		self.assertEqual(hasil["created"], [])

	def test_a_profile_someone_edited_is_left_alone(self):
		"""Once a site is live the profile is theirs, not ours to reset every migrate.

		Edits a copy rather than the real `Krani Timbang`: `IntegrationTestCase` does not
		roll back between methods, so an extra role added here would still be on it when
		the next test reads it.
		"""
		nama = setup.PROFILE_KRANI
		asli = dict(setup.ROLE_PROFILES)
		setup.ROLE_PROFILES = {nama: asli[nama]}
		self.addCleanup(setattr, setup, "ROLE_PROFILES", asli)

		setup.setup_role_profiles()
		doc = frappe.get_doc("Role Profile", nama)
		doc.append("roles", {"role": "Stock User"})
		doc.save(ignore_permissions=True)
		self.addCleanup(self._pulihkan_profil, nama, asli[nama])

		setup.setup_role_profiles()

		doc.reload()
		self.assertIn("Stock User", {r.role for r in doc.roles})

	@staticmethod
	def _pulihkan_profil(nama, peran):
		doc = frappe.get_doc("Role Profile", nama)
		doc.roles = []
		for r in peran:
			doc.append("roles", {"role": r})
		doc.save(ignore_permissions=True)

	def test_the_dialog_can_actually_show_this_field(self):
		"""`role_profiles` is the only role field allowed in quick entry -- if that ever
		changes, the profiles stop being reachable from the New User dialog."""
		meta = frappe.get_meta("User")
		self.assertTrue(meta.get_field("role_profiles").allow_in_quick_entry)


class IntegrationTestRoleProfilesWiring(IntegrationTestCase):
	def test_the_install_hook_creates_the_profiles(self):
		import inspect

		self.assertIn("setup_role_profiles()", inspect.getsource(setup.after_install))

	def test_the_patch_calls_the_same_code_as_the_hook(self):
		import inspect

		from erpnext.patches.v17_0 import palm_mill_role_profiles

		self.assertIn("setup_role_profiles", inspect.getsource(palm_mill_role_profiles.execute))
