#!/usr/bin/env python3
"""Tulis apps.json yang dipakai build, dengan repo autoerp yang ber-token.

Dipisah dari build.sh karena tokennya tidak boleh lewat argumen proses: `ps`
bisa dibaca proses lain di mesin yang sama, dan `set -x` akan meng-echo-nya.
Di sini token hanya dibaca dari environment dan hanya ditulis ke berkas yang
berumur sependek build.

    AUTOERP_REPO=... AUTOERP_BRANCH=... GITHUB_TOKEN=... \
        render_apps_json.py <sumber> <tujuan>
"""

import json
import os
import sys


def main() -> None:
	src, dst = sys.argv[1], sys.argv[2]
	repo = os.environ["AUTOERP_REPO"]
	branch = os.environ["AUTOERP_BRANCH"]
	token = os.environ["GITHUB_TOKEN"]

	apps = json.load(open(src))

	# `x-access-token` adalah bentuk yang diterima GitHub untuk PAT maupun
	# GITHUB_TOKEN bawaan Actions.
	apps.insert(0, {"url": f"https://x-access-token:{token}@github.com/{repo}", "branch": branch})

	names = [a["url"].rstrip("/").rsplit("/", 1)[-1] for a in apps]
	if "autoerp" not in names:
		sys.exit(f"apps.json harus memuat repo autoerp; ada: {names}")

	with open(dst, "w") as fh:
		json.dump(apps, fh, indent=2)

	# Jangan cetak URL-nya: yang pertama membawa token.
	print("    apps:", ", ".join(names))


if __name__ == "__main__":
	main()
