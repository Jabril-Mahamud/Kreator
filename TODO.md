# Kreator TODO

## Local dev

- [x] **Auto-roll workloads on image rebuild (`:latest` tag problem).**
  Done via option 1 (immutable GitOps). `kreator dev` now commits the source,
  reads the resulting git short SHA, builds and pushes images under that SHA tag,
  patches `deploy/helm/*/values.yaml` `image.tag` to it, and commits the bump so
  the in-cluster git server serves it. Every code change is a new SHA, so ArgoCD
  sees a changed `image.tag` and rolls the workloads on its own. No more manual
  `kubectl rollout restart`. See `_set_image_tags` / `_git_short_sha` in
  `kreator/commands/dev.py`.
