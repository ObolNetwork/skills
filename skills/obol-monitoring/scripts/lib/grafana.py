"""Shared Grafana/Prometheus/Loki utilities for Obol monitoring scripts.

All functions use Python stdlib only. No external dependencies required.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

GRAFANA_BASE = "https://grafana.monitoring.gcp.obol.tech"

GENESIS_TIME = {
    "mainnet": 1606824023,
    "hoodi": 1742212800,
    "sepolia": 1655733600,
}

SECONDS_PER_SLOT = 12
SLOTS_PER_EPOCH = 32


def get_auth_headers():
    """Return authorization headers using OBOL_GRAFANA_API_TOKEN env var."""
    token = os.environ.get("OBOL_GRAFANA_API_TOKEN")
    if not token:
        print("Error: OBOL_GRAFANA_API_TOKEN environment variable is not set", file=sys.stderr)
        sys.exit(1)
    return {"Authorization": f"Bearer {token}"}


def fetch_json(url, headers, timeout=30):
    """Fetch JSON from URL. Returns parsed dict or None on error."""
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} fetching {url[:100]}", file=sys.stderr)
        return None
    except urllib.error.URLError as e:
        print(f"URL error: {e.reason}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return None


def discover_datasources(headers):
    """Discover Prometheus and Loki datasource proxy URLs from Grafana.

    Returns (prom_url, loki_url) tuple. Either may be None.
    """
    url = f"{GRAFANA_BASE}/api/datasources"
    datasources = fetch_json(url, headers)
    if not datasources:
        return None, None

    prom_id = None
    loki_id = None
    for ds in datasources:
        if ds.get("type") == "prometheus" and ds.get("name") == "prometheus":
            prom_id = ds.get("id")
        if ds.get("type") == "loki" and ds.get("name") == "Loki":
            loki_id = ds.get("id")

    prom_url = f"{GRAFANA_BASE}/api/datasources/proxy/{prom_id}/api/v1/" if prom_id else None
    loki_url = f"{GRAFANA_BASE}/api/datasources/proxy/{loki_id}/loki/api/v1/" if loki_id else None
    return prom_url, loki_url


def prom_query(prom_url, headers, query, ts=None):
    """Execute a Prometheus instant query. Returns list of result dicts."""
    params = {"query": query}
    if ts:
        params["time"] = str(ts)
    url = f"{prom_url}query?{urllib.parse.urlencode(params)}"
    r = fetch_json(url, headers)
    if not r:
        return []
    return r.get("data", {}).get("result", [])


def prom_query_range(prom_url, headers, query, start, end, step="60s"):
    """Execute a Prometheus range query. Returns list of result dicts."""
    params = urllib.parse.urlencode({
        "query": query, "start": str(start), "end": str(end), "step": step,
    })
    url = f"{prom_url}query_range?{params}"
    r = fetch_json(url, headers)
    if not r:
        return []
    return r.get("data", {}).get("result", [])


def loki_query(loki_url, headers, logql, start_ns, end_ns, limit=1000):
    """Execute a Loki query_range. Returns raw response dict or None."""
    params = urllib.parse.urlencode({
        "query": logql, "start": str(start_ns), "end": str(end_ns),
        "limit": str(limit), "direction": "forward",
    })
    url = f"{loki_url}query_range?{params}"
    return fetch_json(url, headers)


def loki_series(loki_url, headers, match, start_ns, end_ns):
    """Query Loki /series endpoint. Returns set of (cluster_name, cluster_peer) tuples."""
    params = urllib.parse.urlencode({
        "match[]": match, "start": str(start_ns), "end": str(end_ns),
    })
    url = f"{loki_url}series?{params}"
    r = fetch_json(url, headers)
    peers = set()
    if r:
        for s in r.get("data", []):
            cn = s.get("cluster_name", "")
            peer = s.get("cluster_peer", "")
            if cn and peer:
                peers.add((cn, peer))
    return peers


def parse_embedded_ts(line):
    """Parse the embedded ts= field from a charon logfmt line.

    Returns epoch seconds as float, or None if not found.
    Charon logs include ts=2026-03-09T20:53:59.123456789Z which is the actual
    application timestamp. This is more accurate than Loki receipt timestamps
    which can have 1-2s skew due to batching.
    """
    m = re.search(r'ts=(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\.(\d+)Z', line)
    if m:
        dt = datetime.fromisoformat(m.group(1) + "+00:00")
        frac = m.group(2)
        frac_s = int(frac.ljust(9, "0")[:9]) / 1_000_000_000
        return dt.timestamp() + frac_s
    m = re.search(r'ts=(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})Z', line)
    if m:
        dt = datetime.fromisoformat(m.group(1) + "+00:00")
        return dt.timestamp()
    return None


def get_event_ts(loki_ts_str, line):
    """Get best available timestamp: embedded ts= preferred over Loki timestamp.

    Returns epoch seconds as float.
    """
    embedded = parse_embedded_ts(line)
    if embedded is not None:
        return embedded
    return int(loki_ts_str) / 1_000_000_000


def get_cluster_size(prom_url, headers, cluster_name, network="mainnet"):
    """Get authoritative cluster size from cluster_operators metric.

    This is the correct cluster size from the lock file. Do NOT infer
    from count of reporting peers (some nodes may not send metrics).
    """
    q = f'cluster_operators{{cluster_name="{cluster_name}",cluster_network="{network}"}}'
    results = prom_query(prom_url, headers, q)
    if results:
        try:
            return int(float(results[0]["value"][1]))
        except (ValueError, IndexError):
            pass
    return 0


def cluster_selector(cluster_name, network="mainnet"):
    """Return a Prometheus/Loki label selector string."""
    return f'cluster_name="{cluster_name}",cluster_network="{network}"'


def slot_to_time(slot, network="mainnet"):
    """Convert a slot number to UTC datetime string."""
    genesis = GENESIS_TIME.get(network)
    if not genesis:
        return None
    ts = genesis + slot * SECONDS_PER_SLOT
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def slot_to_timestamp(slot, network="mainnet"):
    """Convert a slot number to Unix timestamp."""
    genesis = GENESIS_TIME.get(network)
    if not genesis:
        return None
    return genesis + slot * SECONDS_PER_SLOT


def extract_logfmt(line, field):
    """Extract a field value from a logfmt-formatted line."""
    m = re.search(rf'{field}="([^"]*)"', line)
    if m:
        return m.group(1)
    m = re.search(rf"{field}=(\S+)", line)
    if m:
        return m.group(1)
    return ""


def parse_bn_client(version):
    """Extract BN client name from version string."""
    if "Lighthouse" in version:
        return "Lighthouse"
    if "teku" in version.lower():
        return "Teku"
    if "Prysm" in version:
        return "Prysm"
    if "Nimbus" in version:
        return "Nimbus"
    if "Lodestar" in version:
        return "Lodestar"
    if "Grandine" in version:
        return "Grandine"
    return "Unknown"


def parse_vc_client(user_agent):
    """Extract VC client name from user agent string."""
    if not user_agent:
        return "Lighthouse"  # Lighthouse VC doesn't send user-agent
    ua = user_agent.lower()
    if "lodestar" in ua:
        return "Lodestar"
    if "prysm" in ua:
        return "Prysm"
    if "teku" in ua:
        return "Teku"
    if "nim-presto" in ua or "nimbus" in ua:
        return "Nimbus"
    if "vouch" in ua:
        return "Vouch"
    if "go-http-client" in ua:
        return "Go-http-client"
    return user_agent[:30]
