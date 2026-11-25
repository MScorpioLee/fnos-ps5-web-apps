#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
START=$(date +%s)
# Ordinary direct networking by default; opt in to a build proxy explicitly.
if [ -n "${BUILD_PROXY:-}" ]; then
  export http_proxy="$BUILD_PROXY" https_proxy="$BUILD_PROXY"
fi
export DOTNET_PROCESSOR_COUNT=2 DOTNET_CLI_TELEMETRY_OPTOUT=1 NO_PROXY=127.0.0.1,localhost
export PATH=/var/apps/nodejs_v22/target/bin:$PATH
mkdir -p downloads logs package/app/{backend,dbtool,www} dist
REV=24138d79f9fec10165d3dce9eebe95bc18ea5fa0
if [ ! -d source/RemotePlay ]; then
 curl -fL --retry 3 "https://codeload.github.com/o1298098/remote-play/tar.gz/$REV" -o downloads/upstream.tar.gz
 printf '%s  %s\n' af6cdb40077e3065d32e10d0962e2598ed00fe3a39d0c835b32f55363712f02a downloads/upstream.tar.gz | sha256sum -c -
 mkdir -p source; tar -xzf downloads/upstream.tar.gz -C source --strip-components=1
fi
if [ ! -x sdk/dotnet ]; then
 curl -fL https://dot.net/v1/dotnet-install.sh -o downloads/dotnet-install.sh
 bash downloads/dotnet-install.sh --version 10.0.404 --install-dir "$PWD/sdk" --no-path >logs/sdk-install.log 2>&1
fi
python3 patch-source.py source
sdk/dotnet publish source/RemotePlay/RemotePlay.csproj -c Release -r linux-x64 --self-contained true -m:2 -o "$PWD/package/app/backend" >logs/backend-build.log 2>&1
sdk/dotnet publish source/RemotePlay.DBTool/RemotePlay.DBTool.csproj -c Release -r linux-x64 --self-contained true -m:2 -o "$PWD/package/app/dbtool" >logs/dbtool-build.log 2>&1
(cd source/RemotePlay.Web; npm ci --no-audit --no-fund; npm run build) >logs/frontend-build.log 2>&1
cp -a source/RemotePlay.Web/dist/. package/app/www/
if [ ! -f downloads/ffmpeg.deb ]; then curl -fL 'https://deb.debian.org/debian/pool/main/f/ffmpeg/ffmpeg_5.1.9-0+deb12u1_amd64.deb' -o downloads/ffmpeg.deb; fi
printf '%s  %s\n' 2ba8ead87657c123ce6de2de5ecdbc1fb4ead9a4b317b85b8ec41e16c890fe01 downloads/ffmpeg.deb | sha256sum -c -
mkdir -p downloads/ffmpeg-debian; dpkg-deb -x downloads/ffmpeg.deb downloads/ffmpeg-debian
python3 bundle-native.py >logs/native-bundle.log 2>&1
cp README.md package/app/README.md
cp source/LICENSE package/LICENSE
# Normalize permissions: source extraction inherits the builder umask, not fnOS policy.
python3 collect-notices.py
python3 finalize-package.py
FNPACK=${FNPACK:-/usr/local/bin/fnpack}
rm -f dist/psrp-web.fpk
(cd dist; "$FNPACK" build --directory "$OLDPWD/package") >logs/fnpack-build.log 2>&1
# Some fnpack versions return zero even when validation fails; reject stale/missing output.
[ -s dist/psrp-web.fpk ] && tar -tf dist/psrp-web.fpk >/dev/null
END=$(date +%s)
printf 'Build elapsed: %s seconds\n' "$((END-START))" | tee logs/build-duration.log
sha256sum dist/*.fpk >dist/SHA256SUMS
