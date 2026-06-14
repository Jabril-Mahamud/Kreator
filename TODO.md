# Kreator TODO

## Local dev

- [ ] **Auto-roll workloads on image rebuild (`:latest` tag problem).**
  `kreator dev` rebuilds and pushes images under the `:latest` tag, but if the
  Helm manifests don't change, neither ArgoCD nor Kubernetes restarts the pods,
  so code changes don't actually deploy. Today this requires a manual
  `kubectl rollout restart deploy -n <ns>` after every iteration.

  Fix options (prefer the first — immutable GitOps):
  1. Tag images with the project's git short SHA (or a content hash) after the
     pre-deploy commit, patch `deploy/helm/*/values.yaml` `image.tag` to that
     SHA, and commit so the git server serves it. ArgoCD then sees a changed
     manifest and rolls out automatically. Bonus: real rollback history.
  2. Otherwise, after sync, run `kubectl rollout restart` for the project's
     Deployments (note: with ArgoCD selfHeal this fights the `restartedAt`
     annotation; option 1 is cleaner).

  Impact: blocks the normal edit→`kreator dev`→see-change loop. Discovered while
  iterating on the JobHunterApp worker/scorer.
