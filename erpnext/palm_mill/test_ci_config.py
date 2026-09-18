# Copyright (c) 2026, AutoERP and Contributors
# See license.txt

"""CI settings this fork has to keep straight, pinned so they cannot drift back.

Everything here was a check that failed on **every** pull request, for reasons that
had nothing to do with the change under review — the worst kind of red, because it
trains people to ignore the CI page. Each one is inherited from upstream ERPNext,
which assumes it is running in `frappe/erpnext` on ERPNext's own infrastructure.
"""

import pathlib
import re
import subprocess

import frappe
from frappe.tests import IntegrationTestCase

REPO_ROOT = pathlib.Path(frappe.get_app_path("erpnext")).parent
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
INSTALL_SH = REPO_ROOT / ".github" / "helper" / "install.sh"
DOCS_CHECKER = REPO_ROOT / ".github" / "helper" / "documentation.py"

# Branches of `frappe/frappe` that actually exist. Ours (`main`, `staging`) do not,
# which is the whole problem this maps around.
FRAPPE_HAS_NO = ("main", "staging")


def frappe_branch_for(base_branch: str, override: str = "") -> str:
	"""Run install.sh's own branch selection, so the test cannot drift from the script."""
	script = INSTALL_SH.read_text()
	start = script.index("githubbranch=")
	end = script.index("db_host=")
	snippet = script[start:end]

	out = subprocess.run(
		[
			"bash",
			"-c",
			f'GITHUB_BASE_REF="{base_branch}" FRAPPE_BRANCH="{override}"\n{snippet}\necho "$frappecommitish"',
		],
		capture_output=True,
		text=True,
		check=True,
	)
	return out.stdout.strip()


class IntegrationTestCIConfig(IntegrationTestCase):
	def test_our_branches_build_against_a_frappe_branch_that_exists(self):
		"""`fatal: couldn't find remote ref staging` killed every CI run before a single
		test ran. Upstream reuses the repository's own branch name, which works there
		because erpnext and frappe share branch names; this fork's do not exist upstream.
		"""
		for ours in FRAPPE_HAS_NO:
			self.assertEqual(frappe_branch_for(ours), "version-16", f"base branch {ours}")

	def test_an_upstream_shaped_branch_is_passed_through_untouched(self):
		"""The map must not swallow branch names that upstream really has, or a future
		version bump silently keeps building against version-16."""
		for upstream in ("version-16", "develop", "version-15"):
			self.assertEqual(frappe_branch_for(upstream), upstream)

	def test_frappe_branch_override_still_wins(self):
		"""Escape hatch for testing against an unreleased framework branch."""
		self.assertEqual(frappe_branch_for("staging", override="develop"), "develop")

	def test_payments_is_installed_from_the_same_version_as_the_rest(self):
		"""`bench get-app payments --branch develop` is inherited from upstream, where
		`develop` is the branch under test. This fork builds `version-16`, so that line
		installs a payments built against a different framework version than everything
		around it.

		It has not broken a run yet, which is exactly why it is worth pinning: a
		cross-version app fails at some later point that looks unrelated to CI config.
		"""
		line = next(
			(l for l in INSTALL_SH.read_text().splitlines() if "get-app payments" in l),
			None,
		)
		self.assertIsNotNone(line, "install.sh no longer installs payments")
		self.assertIn(
			"--branch version-16",
			line,
			"payments must be installed from version-16, like frappe and erpnext here",
		)
		self.assertNotIn("--branch develop", line)

	def test_docs_checker_looks_at_this_repository(self):
		"""Upstream hardcodes `frappe/erpnext`, so every PR here was looked up in a
		repository it does not exist in and failed with "Pull Request Not Found" -
		without ever reading the change."""
		source = DOCS_CHECKER.read_text()

		self.assertNotIn("repos/frappe/erpnext/pulls", source)
		self.assertIn("GITHUB_REPOSITORY", source)

	def test_no_job_can_queue_forever_on_a_runner_we_do_not_have(self):
		"""`erpnext-arc` is ERPNext's own self-hosted scale set. A job asking for a
		runner that does not exist does NOT fail - it sits queued indefinitely, which
		reads on the pull request page as "still running" and never resolves. Worse
		than absent: a check nobody can act on.

		Rewriting those jobs to run on hosted runners was tried and abandoned: the
		workflow is welded to that estate (a `ci` user, a MariaDB datadir at
		/home/ci/db-data that setup packages and each shard unpacks), and forcing it
		onto a hosted runner failed at `mv: cannot move '/home/ci/db-data'`. So each
		such job must instead be *gated* — skipped cleanly where the runner is absent.
		"""
		import yaml

		for workflow in WORKFLOWS.glob("*.yml"):
			spec = yaml.safe_load(workflow.read_text())
			for name, job in (spec.get("jobs") or {}).items():
				if "erpnext-arc" not in str(job.get("runs-on", "")):
					continue
				gated = job.get("if") or any(
					(spec["jobs"].get(dep) or {}).get("if")
					for dep in (
						[job["needs"]] if isinstance(job.get("needs"), str) else job.get("needs") or []
					)
				)
				self.assertTrue(
					gated,
					f"{workflow.name}:{name} asks for a runner we lack and would queue forever",
				)

	def test_every_failing_check_has_a_skipped_twin(self):
		"""GitHub cannot mark a path-filtered check as passed, so ERPNext pairs each
		heavy workflow with a "faux" one that fires for the excluded paths. Without the
		twin, a docs-only PR shows a check that never reports and can never go green.
		"""
		names = {
			re.search(r"^name:\s*['\"]?([^'\"\n]+)", w.read_text(), re.M).group(1).strip()
			for w in WORKFLOWS.glob("*.yml")
			if re.search(r"^name:", w.read_text(), re.M)
		}

		self.assertIn("Skipped Patch Test", names)
		self.assertIn("Skipped Tests", names)
