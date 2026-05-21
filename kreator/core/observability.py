import logging
import subprocess

logger = logging.getLogger(__name__)


def _run(cmd: list[str], check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, check=check, capture_output=capture, text=True)
    except subprocess.CalledProcessError as e:
        msg = f"Command failed: {' '.join(cmd)}"
        if e.stderr:
            msg += f"\n{e.stderr.strip()}"
        raise RuntimeError(msg) from e
    except FileNotFoundError:
        raise RuntimeError(f"Command not found: {cmd[0]}. Is it installed and on your PATH?")


def install_observability_stack() -> None:
    """Install the LGTM observability stack: Loki, Grafana, Tempo, Mimir, Promtail."""
    _run(["kubectl", "create", "namespace", "observability"], check=False)

    _install_loki()
    _install_tempo()
    _install_mimir()
    _install_promtail()
    _install_grafana()

    logger.info("observability stack installed")


def _install_loki() -> None:
    logger.info("installing loki")
    _run(
        [
            "helm",
            "repo",
            "add",
            "grafana",
            "https://grafana.github.io/helm-charts",
        ],
        check=False,
    )
    _run(["helm", "repo", "update"])

    _run(
        [
            "helm",
            "upgrade",
            "--install",
            "loki",
            "grafana/loki",
            "--namespace",
            "observability",
            "--set",
            "loki.auth_enabled=false",
            "--set",
            "singleBinary.replicas=1",
            "--set",
            "monitoring.selfMonitoring.enabled=false",
            "--set",
            "monitoring.selfMonitoring.grafanaAgent.installOperator=false",
            "--set",
            "test.enabled=false",
            "--wait",
            "--timeout",
            "5m",
        ]
    )


def _install_tempo() -> None:
    logger.info("installing tempo")
    _run(
        [
            "helm",
            "upgrade",
            "--install",
            "tempo",
            "grafana/tempo",
            "--namespace",
            "observability",
            "--wait",
            "--timeout",
            "3m",
        ]
    )


def _install_mimir() -> None:
    logger.info("installing mimir")
    _run(
        [
            "helm",
            "upgrade",
            "--install",
            "mimir",
            "grafana/mimir-distributed",
            "--namespace",
            "observability",
            "--set",
            "mimir.structuredConfig.common.storage.backend=filesystem",
            "--set",
            "minio.enabled=false",
            "--wait",
            "--timeout",
            "5m",
        ]
    )


def _install_promtail() -> None:
    logger.info("installing promtail")
    _run(
        [
            "helm",
            "upgrade",
            "--install",
            "promtail",
            "grafana/promtail",
            "--namespace",
            "observability",
            "--set",
            "config.clients[0].url=http://loki:3100/loki/api/v1/push",
            "--wait",
            "--timeout",
            "3m",
        ]
    )


def _install_grafana() -> None:
    logger.info("installing grafana")
    _run(
        [
            "helm",
            "upgrade",
            "--install",
            "grafana",
            "grafana/grafana",
            "--namespace",
            "observability",
            "--set",
            "adminPassword=admin",
            "--set",
            "datasources.datasources\\.yaml.apiVersion=1",
            "--set",
            "datasources.datasources\\.yaml.datasources[0].name=Prometheus",
            "--set",
            "datasources.datasources\\.yaml.datasources[0].type=prometheus",
            "--set",
            "datasources.datasources\\.yaml.datasources[0].url=http://mimir-query-frontend:8080/prometheus",
            "--set",
            "datasources.datasources\\.yaml.datasources[0].isDefault=true",
            "--set",
            "datasources.datasources\\.yaml.datasources[1].name=Loki",
            "--set",
            "datasources.datasources\\.yaml.datasources[1].type=loki",
            "--set",
            "datasources.datasources\\.yaml.datasources[1].url=http://loki:3100",
            "--set",
            "datasources.datasources\\.yaml.datasources[2].name=Tempo",
            "--set",
            "datasources.datasources\\.yaml.datasources[2].type=tempo",
            "--set",
            "datasources.datasources\\.yaml.datasources[2].url=http://tempo:3100",
            "--wait",
            "--timeout",
            "3m",
        ]
    )
