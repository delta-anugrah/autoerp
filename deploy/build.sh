#!/usr/bin/env bash
# Build the AutoERP production image.
#
#   ./deploy/build.sh v1.0.0              # build ghcr.io/delta-anugrah/autoerp:v1.0.0
#   PUSH=1 ./deploy/build.sh v1.0.0       # and push it
#
# Dasarnya image resmi `frappe/erpnext`, yang sudah memuat frappe, seluruh
# dependensi Python/Node, wkhtmltopdf dan nginx. erpnext bawaannya ditukar
# dengan fork kita, yang diambil dari cermin lokal -- bukan dari GitHub.
#
# Tidak ada token yang dibutuhkan, dan tidak ada clone besar yang harus
# berhasil: keduanya adalah sebab kegagalan berulang pada pendekatan
# sebelumnya (`bench init` lewat frappe_docker images/custom).
set -euo pipefail

VERSION="${1:-}"
if [ -z "$VERSION" ]; then
	echo "usage: $0 <version>   (mis. v1.0.0, atau 'dev' untuk uji lokal)" >&2
	exit 1
fi

REGISTRY="${REGISTRY:-ghcr.io}"
IMAGE_NAME="${IMAGE_NAME:-delta-anugrah/autoerp}"
IMAGE="$REGISTRY/$IMAGE_NAME:$VERSION"

# Versi image dasar dipaku, bukan `v16`: tag bergerak itu berarti dua build
# dengan commit yang sama bisa menghasilkan isi yang berbeda. Naikkan sengaja.
BASE_IMAGE="${BASE_IMAGE:-frappe/erpnext:v16.35.0}"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTOERP_SRC="${AUTOERP_SRC:-$HERE/..}"
AUTOERP_BRANCH="${AUTOERP_BRANCH:-main}"
# `origin/<branch>`, BUKAN branch lokal: keduanya bisa berbeda (terbukti di
# mesin ini, `main` lokal tertinggal satu commit) dan membangun dari yang
# tertinggal akan mengirim kode lama tanpa ada yang memberi tahu.
AUTOERP_REF="${AUTOERP_REF:-origin/$AUTOERP_BRANCH}"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

if ! git -C "$AUTOERP_SRC" rev-parse --verify --quiet "$AUTOERP_REF" >/dev/null; then
	echo "ref tidak ada di checkout: $AUTOERP_REF (di $AUTOERP_SRC)" >&2
	echo "coba: git -C $AUTOERP_SRC fetch origin $AUTOERP_BRANCH" >&2
	exit 1
fi

WANT_SHA="$(git -C "$AUTOERP_SRC" rev-parse "$AUTOERP_REF")"
echo "==> cermin autoerp dari $AUTOERP_REF (${WANT_SHA:0:10})"

MIRROR="$WORK/autoerp-mirror.git"
SRC_URL="file://$(cd "$AUTOERP_SRC" && pwd)"
git clone -q --bare --depth 1 --branch "$AUTOERP_BRANCH" "$SRC_URL" "$MIRROR"
# `--branch` mengikuti branch LOKAL; timpa dengan ref yang benar-benar diminta.
git -C "$MIRROR" fetch -q --depth 1 --force "$SRC_URL" \
	"$WANT_SHA:refs/heads/$AUTOERP_BRANCH"

MIRROR_SHA="$(git -C "$MIRROR" rev-parse "$AUTOERP_BRANCH")"
if [ "$MIRROR_SHA" != "$WANT_SHA" ]; then
	echo "cermin memuat $MIRROR_SHA, seharusnya $WANT_SHA" >&2
	exit 1
fi

# Penjaga: image tanpa palm_mill akan terpasang mulus dan baru ketahuan salah
# saat truk pertama masuk.
if ! git -C "$MIRROR" cat-file -e "$AUTOERP_BRANCH:erpnext/palm_mill/api.py" 2>/dev/null; then
	echo "cermin tidak memuat erpnext/palm_mill — ref salah?" >&2
	exit 1
fi

cp "$HERE/Containerfile" "$WORK/Containerfile"

echo "==> build $IMAGE (dasar: $BASE_IMAGE)"
DOCKER_BUILDKIT=1 docker build \
	--file "$WORK/Containerfile" \
	--build-arg "BASE_IMAGE=$BASE_IMAGE" \
	--build-arg "AUTOERP_BRANCH=$AUTOERP_BRANCH" \
	--tag "$IMAGE" \
	"$WORK"

# Bukan basa-basi: keduanya pernah salah. palm_mill hilang berarti image
# terpasang mulus lalu menolak truk pertama; kredensial di dalam image berarti
# siapa pun yang menariknya bisa membacanya.
echo "==> periksa hasil"
docker run --rm --entrypoint bash "$IMAGE" -c '
	set -e
	test -f apps/erpnext/erpnext/palm_mill/api.py || { echo "palm_mill TIDAK ADA"; exit 1; }
	grep -q "^erpnext$" sites/apps.txt || { echo "erpnext tidak terdaftar di apps.txt"; exit 1; }
	test -d apps/erpnext/erpnext/public/dist || { echo "aset tidak terbangun"; exit 1; }
	if grep -rqE "x-access-token:[^@[:space:]]+@" /home/frappe/frappe-bench \
			--exclude-dir=deploy 2>/dev/null; then
		echo "kredensial terbaca di dalam image"; exit 1
	fi
	echo "    palm_mill ada, apps.txt benar, aset terbangun, tidak ada kredensial"
'

if [ "${PUSH:-0}" = "1" ]; then
	echo "==> push $IMAGE"
	docker push "$IMAGE"
fi

echo "selesai: $IMAGE (autoerp ${WANT_SHA:0:10})"
