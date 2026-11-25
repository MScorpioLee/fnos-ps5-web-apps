#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p logs
[ -f source/CMakeLists.txt ] && [ -f deps/opus/CMakeLists.txt ] || python3 fetch-sources.py
python3 apply-patches.py
# BUILD_PROXY is optional. Default is ordinary direct networking, suitable for CI.
proxy_args=()
if [ -n "${BUILD_PROXY:-}" ]; then
 for key in http_proxy https_proxy HTTP_PROXY HTTPS_PROXY; do proxy_args+=(-e "$key=$BUILD_PROXY"); done
fi
# Docker is strictly a build-time tool; no container or Docker dependency in FPK.
DOCKER=(docker)
if ! docker info >/dev/null 2>&1; then DOCKER=(sudo -n docker); fi
"${DOCKER[@]}" run --rm --name chiaki-fnos-wasm-build --network host --cpus=2 --memory=4g \
 "${proxy_args[@]}" -e CMAKE_BUILD_PARALLEL_LEVEL=2 -v "$PWD:/work" -w /work/source \
 emscripten/emsdk@sha256:460fff8f8ac87e11b16447fbd66538a686eafa0e4fb977aa0989ed19fe2079f7 \
 bash -lc 'set -e; apt-get update -qq; apt-get install -y -qq python3-venv ninja-build unzip; bash scripts/build-wasm.sh' \
 >logs/wasm-build.log 2>&1
python3 stage-package.py
FNPACK=${FNPACK:-/usr/local/bin/fnpack}
rm -f chiaki-ng-web.fpk
"$FNPACK" build --directory "$PWD/package" | tee logs/fnpack-build.log
# This fnpack version may exit 0 on validation failure. Validate actual artifact.
[ -s chiaki-ng-web.fpk ] && tar -tf chiaki-ng-web.fpk >/dev/null
