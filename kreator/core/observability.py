import logging

from kreator.core.platform import wait_for_argocd_sync
from kreator.core.shell import run

logger = logging.getLogger(__name__)


def install_observability_stack(project_name: str) -> None:
    """Wait for the observability ArgoCD apps to sync.

    The stack (Loki, Tempo, Prometheus, Promtail, Grafana) is declared in
    deploy/argocd/apps/observability.yaml and managed by the root app-of-apps.
    This function simply blocks until all five apps are Healthy.
    """
    run(["kubectl", "create", "namespace", "observability"], check=False)
    wait_for_argocd_sync(
        [
            f"{project_name}-loki",
            f"{project_name}-tempo",
            f"{project_name}-prometheus",
            f"{project_name}-promtail",
            f"{project_name}-grafana",
        ],
        timeout=300,
    )
    logger.info("observability stack healthy")
