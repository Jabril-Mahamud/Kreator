# Kreator — Known Issues (all fixed)

Issues found while dogfooding kreator on a real project (**JobHunterApp**,
2026-06-14). All five are fixed and guarded by regression tests in
`tests/test_dogfood.py`. A heavier runtime check (build the images and verify
the frontend API URL rewrite) lives in `scripts/smoke.sh`; it needs Docker so it
runs manually, not in CI.

This file is kept as a record of what was found and how it was fixed. New issues
should be added at the top if discovered during further dogfooding.

---

## 1. Generated Next.js frontend can't reach the API from the browser (silent `:80` fallback) [FIXED]

**Severity: high — every generated nextjs app is broken in the browser until hand-patched.**

**Resolved:** `templates/frontend/nextjs/Dockerfile.j2` now copies the static dir
with `COPY --chown=1001:1001`, so the entrypoint `sed -i` rewrite runs as
`appuser` and `NEXT_PUBLIC_API_URL` picks up the real `$API_URL` (with port).

- **Root cause:** `templates/frontend/nextjs/Dockerfile.j2`. Line 21 copies the
  build output as root:
  ```dockerfile
  COPY --from=builder /build/.next/static ./.next/static
  ```
  but the container runs as a non-root user (`appuser`, uid 1001) and the
  entrypoint (line ~27) tries to rewrite the baked API URL in place:
  ```sh
  find /home/appuser/.next/static -name '*.js' -exec sed -i "s|http://api.localhost|$API_URL|g" {} +
  ```
  The static files are root-owned and **not writable by `appuser`**, so `sed -i`
  fails silently. `NEXT_PUBLIC_API_URL` stays the build-time default
  `http://api.localhost` (**no port**), so the browser calls port `:80` instead
  of the cluster's host port → all API calls fail with "NetworkError".
- **Why it's nasty:** `curl` works (no port enforcement / different path), so it
  looks like a DNS or backend problem, not a frontend build bug. The error is
  far from the cause.
- **Fix:** make the static dir writable by the runtime user so the entrypoint
  rewrite actually runs:
  ```dockerfile
  COPY --chown=1001:1001 --from=builder /build/.next/static ./.next/static
  ```
- **Discovered:** JobHunterApp (patched there; the template is still broken).

## 2. Generated local Postgres loses all data on pod recreation (no persistent volume) [FIXED]

**Severity: high — any db-pod restart wipes the local database.**

**Resolved:** the local composition's StatefulSet now has a `volumeClaimTemplates`
entry (`data`, 1Gi, `standard` storageClass) mounted at
`/var/lib/postgresql/data`, with `PGDATA` set to a `pgdata` subdir. Data survives
pod recreation. (Civo uses a managed database, so no PVC is needed there.)

- **Root cause:** `templates/platform/crossplane/compositions/local/database.yaml.j2`.
  The `postgres-statefulset` resource (starts ~line 37) defines a StatefulSet with
  **no `volumeClaimTemplate`** and the postgres container has **no `volumeMounts`**.
  PGDATA (`/var/lib/postgresql/data`) lives on the pod's ephemeral container layer.
- **Symptom:** when `<name>-db-0` is recreated (by Crossplane reconcile, a
  re-run, eviction, etc.) the database is wiped. Users/data vanish, the backend
  recreates empty tables on next start, and login returns **401 "Invalid
  credentials"** with an empty dashboard — again, a symptom far from the cause.
- **Fix:** add a `volumeClaimTemplate` (local-path storageClass locally) mounted
  at `/var/lib/postgresql/data`. Civo composition should be checked for the same.
- **Discovered:** JobHunterApp.

## 3. No lightweight way to get new commits into local ArgoCD (git-server snapshot) [FIXED]

**Severity: medium — confusing; Argo shows "Synced" while behind HEAD.**

**Resolved:** added `kreator dev --refresh`. It skips cluster creation and
platform installs: it rebuilds and re-pins images, recreates the git-server pod
so it re-clones the latest commit, and hard-refreshes the project's ArgoCD apps
(`argocd.argoproj.io/refresh=hard`) so the new revision deploys. See `_refresh`
in `kreator/commands/dev.py` and `hard_refresh_apps` in `kreator/core/platform.py`.

- **Context:** local ArgoCD syncs from the in-cluster git-server, which serves a
  frozen `git clone --bare` snapshot. `kreator dev` recreates it
  (`deploy_git_server()`, `kreator/commands/dev.py:128`) — but only as part of the
  **full** setup (rebuild+push all images, reinstall Crossplane/ArgoCD/ingress).
  There is no targeted "refresh git + resync" path.
- **Symptom:** after committing, ArgoCD's synced revision sits several commits
  behind your real HEAD and reports **"Synced ✓"** — so it looks authoritative
  but isn't. New manifest changes don't deploy until either a heavy full `kreator
  dev` re-run or a manual
  `kubectl replace --force -f deploy/local/git-server.yaml` + a hard-refresh
  annotation.
- **Fix idea:** a `kreator dev --refresh` / `kreator sync` subcommand that just
  recreates the git-server Pod and triggers an Argo hard refresh; and/or surface
  the stale-revision gap in `kreator doctor`.
- **Discovered:** JobHunterApp.

## 4. `kreator dev` auto-commits the user's working tree [FIXED]

**Severity: medium — surprising; pollutes project history.**

- **Symptom:** running `kreator dev` silently created commits and swept in
  whatever was in the working tree (WIP, unrelated edits), leaving noisy
  "prepare for local dev" commits on the user's branch.

**Resolved:** `kreator dev` no longer commits to the user's branch. It now
snapshots the working tree onto a dedicated `kreator-local-dev` branch using a
throwaway index and `git commit-tree` (`_snapshot_dev_branch` in
`kreator/commands/dev.py`), so the user's branch, HEAD, working tree, and index
are never touched. The in-cluster git server serves that branch as HEAD via
`git symbolic-ref` (`deploy_git_server` in `kreator/core/platform.py`), which is
what ArgoCD tracks. WIP still gets deployed locally (that's the point of dev) but
nothing lands on the user's real branch.

## 5. README hardcodes `:9080`, but per-project clusters assign different ports [FIXED]

**Severity: low — doc/UX mismatch.**

**Resolved:** the README "Local development" section now uses a `<port>`
placeholder and points readers at the `kreator dev` output and
`~/.kreator/clusters.json` for the real per-project port.

- **Root cause:** `README.md` "Local development" uses `:9080` in every example
  URL, but the per-project-clusters feature (`allocate_ports`) gives each project
  its own host port (JobHunterApp got `:9100`). The CLI output already prints the
  correct port (`dev.py:139-144`); only the README misleads.
- **Symptom:** users copy `:9080` from the README and hit the wrong cluster (or
  an unrelated stack already on that port).
- **Fix:** make README examples use a placeholder (`<assigned-port>`) and point at
  `~/.kreator/clusters.json` / the `kreator dev` output for the real port.
- **Discovered:** JobHunterApp.
