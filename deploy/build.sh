#!/usr/bin/env bash
# Build the AutoERP production image from frappe_docker's `images/custom`.
#
#   GITHUB_TOKEN=ghp_... ./deploy/build.sh v1.0.0        # build
#   GITHUB_TOKEN=ghp_... PUSH=1 ./deploy/build.sh v1.0.0  # and push it
#
# GITHUB_TOKEN wajib: repo autoerp privat, dan `bench init` meng-clone-nya dari
# dalam container, yang tidak ikut membawa kredensial git di laptop. Di CI pakai
# secrets.GITHUB_TOKEN bawaan; lokal butuh PAT dengan akses baca repo saja.
#
# CI runs this same script on a `vX.Y.Z` tag, so a local build and a released one
# come from one recipe. Nothing here is specific to a droplet.
set -euo pipefail

VERSION="${1:-}"
if [ -z "$VERSION" ]; then
	echo "usage: $0 <version>   (mis. v1.0.0, atau 'dev' untuk uji lokal)" >&2
	exit 1
fi

REGISTRY="${REGISTRY:-ghcr.io}"
IMAGE_NAME="${IMAGE_NAME:-delta-anugrah/autoerp}"
IMAGE="$REGISTRY/$IMAGE_NAME:$VERSION"

# Pinned: `main` moves, and an image that silently rebuilds on a different
# frappe_docker is an image nobody can reproduce. Bump deliberately.
FRAPPE_DOCKER_REF="${FRAPPE_DOCKER_REF:-main}"
FRAPPE_BRANCH="${FRAPPE_BRANCH:-version-16}"

AUTOERP_REPO="${AUTOERP_REPO:-delta-anugrah/autoerp}"
AUTOERP_BRANCH="${AUTOERP_BRANCH:-main}"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPS_JSON_SRC="$HERE/apps.json"
WORK="$(mktemp -d)"
# 700: apps.json yang dibangkitkan memuat token. Umurnya sependek build, tapi
# tetap tidak perlu bisa dibaca akun lain di mesin yang sama.
chmod 700 "$WORK"
trap 'rm -rf "$WORK"' EXIT

if [ -z "${GITHUB_TOKEN:-}" ]; then
	cat >&2 <<'MSG'
GITHUB_TOKEN belum diisi.

Repo autoerp privat dan `bench init` meng-clone-nya DARI DALAM container, yang
tidak ikut membawa kredensial git laptop. Tanpa token, build berjalan ~1 jam
(frappe + erpnext + assets berhasil) lalu gagal di langkah terakhir dengan
"could not read Username for https://github.com".

  lokal : GITHUB_TOKEN=<PAT, cukup akses baca repo> ./deploy/build.sh dev
  CI    : sudah diisi otomatis dari secrets.GITHUB_TOKEN
MSG
	exit 1
fi

echo "==> frappe_docker ($FRAPPE_DOCKER_REF)"
git clone -q --depth 1 --branch "$FRAPPE_DOCKER_REF" \
	https://github.com/frappe/frappe_docker.git "$WORK/frappe_docker"

# The Containerfile reads apps.json as a BUILD SECRET, not as a base64 build arg:
#   RUN --mount=type=secret,id=apps_json,target=/opt/frappe/apps.json
# so it is passed with --secret. A missing or empty file is not an error there --
# bench init just builds a bench with no apps -- which would produce an image
# without palm_mill and fail only much later, at the first truck. Check it here.
if [ ! -s "$APPS_JSON_SRC" ]; then
	echo "apps.json kosong atau tidak ada: $APPS_JSON_SRC" >&2
	exit 1
fi

# autoerp TIDAK ditulis di apps.json: URL-nya harus membawa token, dan berkas
# yang di-commit bukan tempat kredensial. Disuntik di sini ke berkas sementara
# yang hanya hidup selama build.
APPS_JSON="$WORK/apps.json"
AUTOERP_REPO="$AUTOERP_REPO" AUTOERP_BRANCH="$AUTOERP_BRANCH" \
	python3 "$HERE/render_apps_json.py" "$APPS_JSON_SRC" "$APPS_JSON"
chmod 600 "$APPS_JSON"

echo "==> build $IMAGE"
# CACHE_BUST keeps `bench init` from reusing a cached layer when the branch has
# moved but the Containerfile has not -- without it a rebuild of the same tag can
# quietly ship yesterday's code.
DOCKER_BUILDKIT=1 docker build \
	--file "$WORK/frappe_docker/images/custom/Containerfile" \
	--secret "id=apps_json,src=$APPS_JSON" \
	--build-arg "FRAPPE_BRANCH=$FRAPPE_BRANCH" \
	--build-arg "CACHE_BUST=$(date +%s)" \
	--tag "$IMAGE-unscrubbed" \
	"$WORK/frappe_docker"

# `bench init` menulis perintah git yang dijalankannya -- lengkap dengan URL
# ber-token -- ke logs/bench.log, dan berkas itu ikut ke dalam image. Tanpa
# langkah ini siapa pun yang menarik image bisa membaca tokennya. Lapisan
# terpisah, karena menghapus berkas tidak menghapusnya dari lapisan sebelumnya.
echo "==> bersihkan jejak token"
DOCKER_BUILDKIT=1 docker build \
	--file "$HERE/Containerfile.scrub" \
	--build-arg "BASE_IMAGE=$IMAGE-unscrubbed" \
	--tag "$IMAGE" \
	"$WORK"

# Penjaga, bukan basa-basi: kalau suatu saat Frappe menulis log ke tempat lain,
# ini yang menahan image bocor supaya tidak sempat ter-push. Polanya menuntut
# token yang benar-benar menempel (`x-access-token:<sesuatu>@`), bukan kata
# "x-access-token" begitu saja -- kata itu muncul sah di .github/helper/install.sh
# dan mencocokkannya akan menggagalkan setiap build tanpa ada yang bocor.
if docker run --rm --entrypoint bash "$IMAGE" \
		-c "grep -rqE 'x-access-token:[^@[:space:]]+@' /home/frappe/frappe-bench 2>/dev/null"; then
	echo "GAGAL: token masih terbaca di dalam image; image tidak dipakai." >&2
	docker rmi -f "$IMAGE" "$IMAGE-unscrubbed" >/dev/null 2>&1 || true
	exit 1
fi

docker rmi -f "$IMAGE-unscrubbed" >/dev/null 2>&1 || true

if [ "${PUSH:-0}" = "1" ]; then
	echo "==> push $IMAGE"
	docker push "$IMAGE"
fi

echo "selesai: $IMAGE"
