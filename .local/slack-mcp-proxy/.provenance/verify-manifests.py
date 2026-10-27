import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent.parent
evidence = root / '.provenance'
baseline = json.loads((evidence / 'baseline-sha256.json').read_text())
current = json.loads((evidence / 'current-source-sha256.json').read_text())
build = json.loads((evidence / 'build-sha256.json').read_text())
for name, expected in {**current, **build}.items():
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected, name
changed = sorted(name for name in baseline if baseline[name] != current[name])
assert changed == ['src/app.ts', 'src/constants.ts', 'src/logger.ts', 'src/sanitize.ts'], changed
assert sorted(set(current) - set(baseline)) == ['.prettierignore', 'src/log-security.test.ts']
assert root.stat().st_mode & 0o777 == 0o700
for name in ['LICENSE', 'package.json', 'pnpm-lock.yaml']:
    assert current[name] == baseline[name], name
source_digest = hashlib.sha256(json.dumps(current, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
assert source_digest == 'd43dd39ef8cf16306ee7a7bc3f5cb59cad6f21a053650dfa9185b0166fb963fb'
print(json.dumps({'manifests_verified': True, 'source_manifest_sha256': source_digest, 'source_files': len(current), 'build_files': len(build), 'directory_mode': '0700', 'license_lock_package_unchanged': True}))
