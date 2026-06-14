from pathlib import Path

from kreator.core.cluster import (
    BASE_HTTP_PORT,
    BASE_HTTPS_PORT,
    PORT_STEP,
    allocate_ports,
    cluster_name,
    release_ports,
)

# Treat every port as free so allocation is deterministic regardless of the host.
ALL_FREE = lambda _port: True  # noqa: E731


def _alloc(name: str, sf: Path) -> tuple[int, int]:
    return allocate_ports(name, state_file=sf, port_available=ALL_FREE)


def test_cluster_name() -> None:
    assert cluster_name("jobhunterapp") == "kreator-jobhunterapp"
    assert cluster_name("my-app") == "kreator-my-app"


def test_allocate_ports_first_is_base(tmp_path: Path) -> None:
    sf = tmp_path / "clusters.json"
    assert _alloc("kreator-a", sf) == (BASE_HTTP_PORT, BASE_HTTPS_PORT)


def test_allocate_ports_is_stable(tmp_path: Path) -> None:
    sf = tmp_path / "clusters.json"
    assert _alloc("kreator-a", sf) == _alloc("kreator-a", sf)


def test_allocate_ports_increments_per_cluster(tmp_path: Path) -> None:
    sf = tmp_path / "clusters.json"
    a = _alloc("kreator-a", sf)
    b = _alloc("kreator-b", sf)
    c = _alloc("kreator-c", sf)
    assert a == (BASE_HTTP_PORT, BASE_HTTPS_PORT)
    assert b == (BASE_HTTP_PORT + PORT_STEP, BASE_HTTPS_PORT + PORT_STEP)
    assert c == (BASE_HTTP_PORT + 2 * PORT_STEP, BASE_HTTPS_PORT + 2 * PORT_STEP)


def test_released_ports_are_reused(tmp_path: Path) -> None:
    sf = tmp_path / "clusters.json"
    _alloc("kreator-a", sf)
    b = _alloc("kreator-b", sf)
    release_ports("kreator-a", state_file=sf)
    # New cluster takes the freed lowest slot, not b's slot.
    assert _alloc("kreator-d", sf) == (BASE_HTTP_PORT, BASE_HTTPS_PORT)
    assert _alloc("kreator-b", sf) == b


def test_release_missing_is_noop(tmp_path: Path) -> None:
    sf = tmp_path / "clusters.json"
    release_ports("kreator-nope", state_file=sf)  # must not raise
    assert _alloc("kreator-a", sf) == (BASE_HTTP_PORT, BASE_HTTPS_PORT)


def test_allocation_skips_busy_host_ports(tmp_path: Path) -> None:
    sf = tmp_path / "clusters.json"
    busy = {BASE_HTTP_PORT, BASE_HTTPS_PORT + PORT_STEP}  # http base busy; 2nd https busy

    def avail(port: int) -> bool:
        return port not in busy

    # base http busy -> skip to next pair; that pair's https also busy -> skip again
    http, https = allocate_ports("kreator-a", state_file=sf, port_available=avail)
    assert http == BASE_HTTP_PORT + 2 * PORT_STEP
    assert https == BASE_HTTPS_PORT + 2 * PORT_STEP
