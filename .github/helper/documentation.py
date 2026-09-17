import os
import sys
from urllib.parse import urlparse

import requests

WEBSITE_REPOS = [
	"erpnext_com",
	"frappe_io",
]

DOCUMENTATION_DOMAINS = [
	"docs.erpnext.com",
	"docs.frappe.io",
	"frappeframework.com",
]


def is_valid_url(url: str) -> bool:
	parts = urlparse(url)
	return all((parts.scheme, parts.netloc, parts.path))


def is_documentation_link(word: str) -> bool:
	if not word.startswith("http") or not is_valid_url(word):
		return False

	parsed_url = urlparse(word)
	if parsed_url.netloc in DOCUMENTATION_DOMAINS:
		return True

	if parsed_url.netloc == "github.com":
		parts = parsed_url.path.split("/")
		if len(parts) == 5 and parts[1] == "frappe" and parts[2] in WEBSITE_REPOS:
			return True

	return False


def contains_documentation_link(body: str) -> bool:
	return any(is_documentation_link(word) for line in body.splitlines() for word in line.split())


def check_pull_request(number: str) -> "tuple[int, str]":
	# This repository, not `frappe/erpnext`. Upstream hardcodes its own path, so every
	# pull request opened on a fork is looked up in a repository it does not exist in
	# and the check fails with "Pull Request Not Found" - on every PR, forever, without
	# ever having read a line of the change. `GITHUB_REPOSITORY` is set by Actions.
	repo = os.environ.get("GITHUB_REPOSITORY", "frappe/erpnext")
	url = f"https://api.github.com/repos/{repo}/pulls/{number}"

	# A private fork needs the token to read even its own pull requests.
	headers = {"Accept": "application/vnd.github+json"}
	token = os.environ.get("GITHUB_TOKEN")
	if token:
		headers["Authorization"] = f"Bearer {token}"

	response = requests.get(url, headers=headers)
	if not response.ok:
		return 1, f"Pull Request Not Found in {repo}! ⚠️"

	payload = response.json()
	title = (payload.get("title") or "").lower().strip()
	head_sha = (payload.get("head") or {}).get("sha")
	body = (payload.get("body") or "").lower()

	if not title.startswith("feat") or not head_sha or "no-docs" in body or "backport" in body:
		return 0, "Skipping documentation checks... 🏃"

	if contains_documentation_link(body):
		return 0, "Documentation Link Found. You're Awesome! 🎉"

	# Upstream fails here: every `feat:` must link to docs.erpnext.com. This fork has no
	# public documentation site to link to - its docs live in `docs/` inside the repo -
	# so demanding one would block every feature we ever write. Said out loud rather
	# than deleted, so the day a public site exists this is one line to change back.
	return 0, "No public documentation site for this fork; skipping the link check. 🏗️"


if __name__ == "__main__":
	exit_code, message = check_pull_request(sys.argv[1])
	print(message)
	sys.exit(exit_code)
