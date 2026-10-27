# Scoped local proxy writer evidence — 2026-10-23

## Scope and source

- Authorized writer directory only: `/Users/efren.herrera/workspace/efren-bot/.local/slack-mcp-proxy`, created absent, mode 0700. No Git commands, other source/config edits, listeners, Slack calls, MCP calls, authentication, credential reads, Docker or services.
- Source: `https://github.com/NikaBuligini/opencode-slack-mcp-proxy`, commit `d056996bc99d0571ce6ddf396622dbb2371b8254`.
- Download: Python stdlib `urllib.request.urlopen` (60-second timeout) from `https://codeload.github.com/NikaBuligini/opencode-slack-mcp-proxy/tar.gz/d056996bc99d0571ce6ddf396622dbb2371b8254`. Outer command timeout 90 seconds. Archive SHA256 `387adf6f58e9f614cebe75ad7bd7396d8b37b11ba3f6f190a9f05bd1596e5590`.
- Before writing any extracted member, validated every member: expected root prefix, no absolute paths or `..`, only regular files/directories (all symlinks, hardlinks and special files rejected), archive capped at 20 MB and members at 10 MB. Extracted explicitly to the new directory with umask 077, not `extractall`. 23 baseline files.
- Baseline source SHA256 map is `baseline-sha256.json`; file hash `f3ad6146fc90767a331b329248de391b1d7e113a0a9e41cc24d3cb3ba6a7624a`. Acquisition metadata is `source.json`.
- Final source-directory digest: `d43dd39ef8cf16306ee7a7bc3f5cb59cad6f21a053650dfa9185b0166fb963fb`, defined as SHA256 of UTF-8 `json.dumps(current_source_map, sort_keys=True, separators=(',', ':'))`. Covers 25 upstream/local source files, excludes dependencies, build and provenance. Current map: `current-source-sha256.json`; build map: `build-sha256.json`.
- License, package.json and pnpm-lock.yaml hashes match baseline. No dependency versions or destinations changed. No source changes outside logging.

## Delta

- `src/app.ts`: no raw callback/authorize/token/MCP URL queries, user-supplied paths, header values, request/OAuth response bodies, remote discovery payloads, client IDs or exception text in logs. Keep fixed event messages and method/route/status/timeout. Transport request path, headers, body, callback rewrite and response payloads remain intact.
- `src/constants.ts`: include state, PKCE verifier/challenge, token/password and proxy authorization in legacy sensitive keys.
- `src/sanitize.ts`: strip userinfo/query/fragment from URLs; redact Error/opaque text; central allowlist of bounded operational metadata. This is not a claim arbitrary payloads can be safely logged after generic sanitization.
- `src/logger.ts`: filter structured log fields and bindings, including direct/nested Pino child creation; optional test output stream. Callers still must use constant event messages. Existing production callsites do so; arbitrary free-form log messages/interpolation are not a supported safe input API.
- `src/log-security.test.ts`: 22 regressions exercise actual callsite capture and Pino serialization, OAuth success/error, JSON/form/query/encoded/nested URL fields, headers/cookies, MCP content/IDs, response token bodies, network exceptions and malformed JSON. Asserts operational logs remain useful and responses still contain original forwarded data.
- `.prettierignore`: exclude only `.pnpm-store/`, `.provenance/`, `node_modules/` and `build/`; no source exclusions. Temporary `.oxfmtignore` was renamed after local CLI evidence showed it is not auto-discovered.

## Classification and exact command ledger

All checks/install steps below were classified **mandatory before execution**. Source: explicit delegated security criterion + TDD in `.odd/openchamber-slack-proxy.md`, root AGENTS.md requirement to classify/preserve failures, and reviewed upstream package scripts. Local helper inspections remediate actual failed checks, not optional exploration. No optional checks were run.

Working directory for every command below: `/Users/efren.herrera/workspace/efren-bot/.local/slack-mcp-proxy`. For compactness **P** expands exactly to `env PATH=/opt/homebrew/bin:/usr/bin:/bin`. Commands had foreground timeouts: checks 120 seconds, installation and test:all 180 seconds, helpers 30 seconds. No background commands.

| Attempt | Exact command (expand P) | Exit/result | Remediation or interpretation |
| --- | --- | --- | --- |
| Install | `env PATH=/opt/homebrew/bin:/usr/bin:/bin NPM_CONFIG_USERCONFIG=/dev/null NPM_CONFIG_GLOBALCONFIG=/dev/null pnpm install --frozen-lockfile --ignore-scripts --store-dir .pnpm-store --registry https://registry.npmjs.org` | 0; pnpm 10.17.1, 95 packages | Lock resolution skipped; all install scripts disabled; local store, official registry; no globals/updates/native fallback installs. |
| Red | `P pnpm exec vitest run src/log-security.test.ts` | 1; 17 failed, 2 passed | Synthetic secret markers reproduced in raw producer logs and legacy sanitizer. |
| Baseline | `P pnpm exec vitest run src/app.test.ts` | 0; 6 passed | Unmodified original tests. |
| Fix attempt 1 | `P pnpm exec vitest run src/log-security.test.ts` | 1; 19 failed, 1 passed | Pino passed undefined base bindings; sanitizer default parameter added. |
| Fix attempt 1 | `P pnpm typecheck` | 0 | Types alone did not catch runtime formatter invocation. |
| Fix attempt 1 | `P pnpm lint` | 0; 0 warnings/errors | No unrelated fixes. |
| Fix attempt 1 | `P pnpm format:check` | 1; 98 files | Local store included plus 3 causal source format issues. No automatic rewrite. |
| Fix attempt 2 | `P pnpm test` | 1; 25 passed, 1 failed | Real Pino child binding formatter reset reproduced; central child wrapper added. |
| Fix attempt 2 | `P pnpm typecheck` | 0 | Before child wrapper. |
| Fix attempt 2 | `P pnpm lint` | 0; 0 warnings/errors | Before child wrapper. |
| Fix attempt 2 | `P pnpm format:check` | 1; 96 files | `.oxfmtignore` not auto-discovered; 95 dependency store manifests + sanitize.ts. |
| Fix attempt 2 | `P pnpm build` | 0 | Intermediate build only, not final evidence. |
| Local CLI evidence | `P pnpm exec oxfmt --help` | 0 | Documents `.gitignore`/`.prettierignore`; renamed ignore file. Also read local Pino child implementation, which deliberately resets bindings formatter. |
| Fix attempt 3 | `P pnpm test` | 0; 26 passed | Runtime and child protection now pass. |
| Fix attempt 3 | `P pnpm typecheck` | 2; TS2684 | Generic child.call type incompatibility; switched invocation to Reflect.apply. |
| Fix attempt 3 | `P pnpm format:check` | 1; sanitize.ts only | Source remained included; manual PATCH of formatter output. |
| Read-only format evidence | `P pnpm exec oxfmt --stdin-filepath src/sanitize.ts < src/sanitize.ts` | 0 | Printed formatted source only; did not write any file. |
| Fix attempt 4 | `P pnpm test:all` | 2; lint/format passed, TS2352 | Child wrapper return signature lost Pino custom-level generic; corrected generic signature. Build/tests not reached in this attempt. |
| Final | `P pnpm test:all` | 0 | lint 0 warnings/errors; format all 19 files matched; typecheck/build passed; 28 tests = 6 original + 22 security passed. |
| Compiled stdout | `env PATH=/opt/homebrew/bin:/usr/bin:/bin NODE_ENV=production node --input-type=module` with heredoc equal to `.provenance/compiled-stdout-check.mjs` | 0 | Actual compiled logger stdout: 2 lines, no synthetic markers; nested children + useful method/path/status preserved, no server. |
| Read-only source/build audit | `python3` with inline hashlib/json/pathlib audit | 0 | Exact modified baseline set is 4 logging files, 25 final source files, 8 build modules; mode 0700; license/package/lock unchanged. Final audit equivalent is persisted as `.provenance/verify-manifests.py`. |

Artifact-script readback/reproduction commands (mandatory evidence integrity), both executed after saving these files and **exit 0**:

```sh
env PATH=/opt/homebrew/bin:/usr/bin:/bin NODE_ENV=production node .provenance/compiled-stdout-check.mjs
python3 .provenance/verify-manifests.py
```

Observed: compiled stdout check passed (2 lines, no markers, no server); manifests verified (25 source files, 8 build files, mode 0700, license/lock/package unchanged). No source edits occurred after the passing final test:all; subsequent edits only preserved ignored provenance/evidence.

## Delivery / boundaries

- Runtime entrypoint compiled: `/Users/efren.herrera/workspace/efren-bot/.local/slack-mcp-proxy/build/index.js`. Companion modules: app/config/constants/http-utils/logger/sanitize/slack under `build/`; no compiled tests.
- Installation scripts remained disabled for the entire dependency installation. No `pnpm format`, start/prestart, global installation, package upgrade, or borrowed client identity.
- No actual Slack/OpenChamber connection verified by this writer. Parent owns loopback runtime, legitimate client authorization, global MCP entry, human login and metadata/catalog-only connection verification. Do not infer those from the build/tests.
- Parent plan/mirror untouched. Accompanying isolated Engram bugfix observation: 3899, topic `odd/openchamber-slack-proxy/log-redaction`; no judgment candidates returned.
