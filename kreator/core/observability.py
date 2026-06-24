import logging
import tempfile

from kreator.core.shell import run

logger = logging.getLogger(__name__)

# Loki's chart defaults to deploymentMode=SimpleScalable, which renders the
# read/write/backend statefulsets and requires object-storage bucketNames
# (helm fails with "Please define loki.storage.bucketNames.chunks"). For local
# dev we force SingleBinary with filesystem storage and zero out the scalable
# components, so no object store is needed.
_LOKI_VALUES = """\
loki:
  auth_enabled: false
  commonConfig:
    replication_factor: 1
  storage:
    type: filesystem
  schemaConfig:
    configs:
      - from: "2024-04-01"
        store: tsdb
        object_store: filesystem
        schema: v13
        index:
          prefix: index_
          period: 24h
deploymentMode: SingleBinary
singleBinary:
  replicas: 1
read:
  replicas: 0
write:
  replicas: 0
backend:
  replicas: 0
chunksCache:
  enabled: false
resultsCache:
  enabled: false
monitoring:
  selfMonitoring:
    enabled: false
    grafanaAgent:
      installOperator: false
test:
  enabled: false
"""


def install_observability_stack() -> None:
    """Install the LGTM observability stack: Loki, Grafana, Tempo, Prometheus, Promtail."""
    run(["kubectl", "create", "namespace", "observability"], check=False)

    _install_loki()
    _install_tempo()
    _install_prometheus()
    _install_promtail()
    _install_grafana()

    logger.info("observability stack installed")


def _install_loki() -> None:
    logger.info("installing loki")
    run(
        [
            "helm",
            "repo",
            "add",
            "grafana",
            "https://grafana.github.io/helm-charts",
        ],
        check=False,
    )
    run(["helm", "repo", "update"])

    with tempfile.NamedTemporaryFile(
        mode="w", suffix="-loki-values.yaml", delete=False
    ) as f:
        f.write(_LOKI_VALUES)
        values_path = f.name

    run(
        [
            "helm",
            "upgrade",
            "--install",
            "loki",
            "grafana/loki",
            "--namespace",
            "observability",
            "--values",
            values_path,
            "--wait",
            "--timeout",
            "5m",
        ]
    )


def _install_tempo() -> None:
    logger.info("installing tempo")
    run(
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


def _install_prometheus() -> None:
    logger.info("installing prometheus")
    run(
        [
            "helm",
            "repo",
            "add",
            "prometheus-community",
            "https://prometheus-community.github.io/helm-charts",
        ],
        check=False,
    )
    run(["helm", "repo", "update"])
    run(
        [
            "helm",
            "upgrade",
            "--install",
            "prometheus",
            "prometheus-community/prometheus",
            "--namespace",
            "observability",
            "--set",
            "alertmanager.enabled=false",
            "--set",
            "prometheus-pushgateway.enabled=false",
            "--wait",
            "--timeout",
            "3m",
        ]
    )


def _install_promtail() -> None:
    logger.info("installing promtail")
    run(
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
    run(
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
            "datasources.datasources\\.yaml.datasources[0].url=http://prometheus-server:80",
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
            "--set",
            "ingress.enabled=true",
            "--set",
            "ingress.ingressClassName=nginx",
            "--set",
            "ingress.hosts[0]=grafana.localhost",
            "--wait",
            "--timeout",
            "3m",
        ]
    )
