#!/usr/bin/env python3
"""Restore pinned PSRP source in a NEW directory; check every source SHA256.

Usage: python3 verify-replay.py NEW_DIRECTORY [--archive upstream.tar.gz]
No production services, package installation, PS5 connection or Git commit.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import urllib.request


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--archive', type=Path)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    manifest = json.loads((here / 'manifest.json').read_text())
    destination = args.destination.resolve()
    if destination.exists():
        parser.error('destination must not exist (no overwrite)')
    with tempfile.TemporaryDirectory(prefix='psrp-source-') as temporary:
        archive = args.archive
        if archive is None:
            archive = Path(temporary) / 'upstream.tar.gz'
            urllib.request.urlretrieve(manifest['upstream']['archive_url'], archive)
        if digest(archive.read_bytes()) != manifest['upstream']['archive_sha256']:
            raise ValueError('upstream archive checksum mismatch')
        with tarfile.open(archive) as stream:
            members = stream.getmembers()
            expected_root = 'remote-play-' + manifest['upstream']['revision']
            for member in members:
                path = Path(member.name)
                if path.is_absolute() or '..' in path.parts or path.parts[0] != expected_root:
                    raise ValueError('unsafe archive path')
                if not (member.isdir() or member.isfile()):
                    raise ValueError('archive links/special entries are not allowed')
            stream.extractall(temporary)
        source = Path(temporary) / expected_root
        for component in manifest['excluded_components']:
            # The pinned archive currently only has .DS_Store to remove;
            # never read local runtime/build directories.
            for base, directories, names in os.walk(source, topdown=False):
                import shutil
                if component in directories:
                    shutil.rmtree(Path(base) / component)
                if component in names:
                    (Path(base) / component).unlink()
        for item in manifest['series']:
            patch = here / item['file']
            if digest(patch.read_bytes()) != item['sha256']:
                raise ValueError('patch checksum mismatch: ' + item['file'])
            subprocess.run(['git', 'apply', '--check', str(patch)], cwd=source, check=True)
            subprocess.run(['git', 'apply', str(patch)], cwd=source, check=True)
        actual = {p.relative_to(source).as_posix(): digest(p.read_bytes())
                  for p in source.rglob('*') if p.is_file()}
        if actual != manifest['source_files']:
            raise ValueError('restored source tree does not match manifest')
        if actual['LICENSE'] != manifest['license_sha256']:
            raise ValueError('upstream license mismatch')
        # copytree refuses a concurrently created destination as well.
        import shutil
        shutil.copytree(source, destination)
    print(json.dumps({'passed': True, 'verified_source_files': len(actual),
                      'patches': len(manifest['series']),
                      'revision': manifest['upstream']['revision']}))


if __name__ == '__main__':
    main()
