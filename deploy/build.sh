#!/usr/bin/env bash
# Build the AutoERP production image from frappe_docker's `images/custom`.
#
#   ./deploy/build.sh v1.0.0              # build ghcr.io/delta-anugrah/autoerp:v1.0.0
#   PUSH=1 ./deploy/build.sh v1.0.0       # and push it
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

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPS_JSON="$HERE/apps.json"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo "==> frappe_docker ($FRAPPE_DOCKER_REF)"
git clone -q --depth 1 --branch "$FRAPPE_DOCKER_REF" \
	https://github.com/frappe/frappe_docker.git "$WORK/frappe_docker"

# The Containerfile reads apps.json as a BUILD SECRET, not as a base64 build arg:
#   RUN --mount=type=secret,id=apps_json,target=/opt/frappe/apps.json
# so it is passed with --secret. A missing or empty file is not an error there --
# bench init just builds a bench with no apps -- which would produce an image
# without palm_mill and fail only much later, at the first truck. Check it here.
if [ ! -s "$APPS_JSON" ]; then
	echo "apps.json kosong atau tidak ada: $APPS_JSON" >&2
	exit 1
fi
python3 -c "
import json,sys
apps = json.load(open('$APPS_JSON'))
names = [a['url'].rstrip('/').rsplit('/',1)[-1] for a in apps]
if 'autoerp' not in names:
    sys.exit('apps.json harus memuat repo autoerp; ada: %s' % names)
print('    apps:', ', '.join(names))
"

echo "==> build $IMAGE"
# CACHE_BUST keeps `bench init` from reusing a cached layer when the branch has
# moved but the Containerfile has not -- without it a rebuild of the same tag can
# quietly ship yesterday's code.
DOCKER_BUILDKIT=1 docker build \
	--file "$WORK/frappe_docker/images/custom/Containerfile" \
	--secret "id=apps_json,src=$APPS_JSON" \
	--build-arg "FRAPPE_BRANCH=$FRAPPE_BRANCH" \
	--build-arg "CACHE_BUST=$(date +%s)" \
	--tag "$IMAGE" \
	"$WORK/frappe_docker"

if [ "${PUSH:-0}" = "1" ]; then
	echo "==> push $IMAGE"
	docker push "$IMAGE"
fi

echo "selesai: $IMAGE"
