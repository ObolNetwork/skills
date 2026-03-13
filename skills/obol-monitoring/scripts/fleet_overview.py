#!/usr/bin/env python3
"""Multi-cluster fleet overview with version/client diversity and health stats.

Usage: python3 fleet_overview.py [--network mainnet] [--hours 1]
Requires: OBOL_GRAFANA_API_TOKEN environment variable.
Outputs: JSON to stdout, progress to stderr.
"""

import argparse
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.grafana import (
    get_auth_headers, discover_datasources, prom_query, loki_series,
    parse_bn_client, parse_vc_client,
)


def categorise_cluster(name, size):
    """Categorise cluster by operator type."""
    n = name.lower()
    if "curated" in n and "etherfi" in n: return "etherfi_curated"
    if name.startswith("EtherFi:"): return "etherfi_curated"
    if name.startswith("Pier Two x Etherfi"): return "etherfi_curated"
    if "etherfi" in n: return "etherfi_solo"
    if "stakely" in n and ("lido" in n or "obol" in n): return "lido_curated"
    if "rocklogic" in n: return "lido_curated"
    if "ebunker" in n: return "lido_curated"
    if name == "?" and size == 4: return "lido_curated"
    if "lido x obol" in n: return "lido_sdvt"
    if "stakewise" in n: return "protocol_curated"
    if "swell" in n: return "protocol_curated"
    if "obol" in n and ("mainnet" in n or "eigensquad" in n): return "obol_internal"
    if name == "Stakely Obol Portal": return "obol_internal"
    if name == "?" or size <= 1: return "unknown"
    return "community"


def main():
    parser = argparse.ArgumentParser(description="Fleet overview")
    parser.add_argument("--network", default="mainnet")
    parser.add_argument("--hours", type=int, default=1)
    args = parser.parse_args()

    headers = get_auth_headers()
    prom_url, loki_url = discover_datasources(headers)
    if not prom_url:
        print(json.dumps({"error": "Could not discover Prometheus"}))
        sys.exit(1)

    net = args.network
    window = f"{args.hours}h"
    now = int(time.time())

    def pq(query):
        return prom_query(prom_url, headers, query)

    # 1. Cluster sizes (authoritative)
    print("  Cluster sizes...", file=sys.stderr)
    cluster_sizes = {}
    for d in pq(f'cluster_operators{{cluster_network="{net}"}}'):
        cn = d["metric"].get("cluster_name", "?")
        try:
            cluster_sizes[cn] = int(float(d["value"][1]))
        except (ValueError, TypeError):
            pass

    # 2. Versions
    print("  Versions...", file=sys.stderr)
    node_info = {}
    for d in pq(f'app_version{{cluster_network="{net}"}}'):
        key = (d["metric"].get("cluster_name", "?"), d["metric"].get("cluster_peer", "?"))
        node_info[key] = {
            "charon_version": d["metric"].get("version", "?"),
            "nickname": d["metric"].get("nickname", ""),
        }

    # 3. BN versions
    print("  BN versions...", file=sys.stderr)
    bn_map = {}
    for d in pq(f'app_beacon_node_version{{cluster_network="{net}"}}'):
        key = (d["metric"].get("cluster_name", "?"), d["metric"].get("cluster_peer", "?"))
        if key not in bn_map:
            bn_map[key] = d["metric"].get("version", "?")

    # 4. VC clients
    print("  VC clients...", file=sys.stderr)
    vc_map = {}
    for d in pq(f'core_validatorapi_vc_user_agent{{cluster_network="{net}"}}'):
        key = (d["metric"].get("cluster_name", "?"), d["metric"].get("cluster_peer", "?"))
        vc_map[key] = d["metric"].get("user_agent", "")

    # 5. Validator counts
    print("  Validators...", file=sys.stderr)
    val_map = {}
    for d in pq(f'core_scheduler_validators_active{{cluster_network="{net}"}}'):
        cn = d["metric"].get("cluster_name", "?")
        try:
            val_map[cn] = max(val_map.get(cn, 0), int(float(d["value"][1])))
        except (ValueError, TypeError):
            pass

    # 6. Failure rates
    print("  Failure rates...", file=sys.stderr)
    failure_rates = {}
    for d in pq(f'sum(rate(core_tracker_failed_duty_reasons_total{{cluster_network="{net}"}}[{window}])) by (cluster_name, duty, reason) * 3600'):
        cn = d["metric"].get("cluster_name", "?")
        duty = d["metric"].get("duty", "?")
        reason = d["metric"].get("reason", "?")
        val = float(d["value"][1])
        if val > 0:
            failure_rates.setdefault(cn, {}).setdefault(duty, {})[reason] = round(val, 1)

    # 7. Success rates
    print("  Success rates...", file=sys.stderr)
    success_map = {}
    for d in pq(f'sum(rate(core_tracker_success_duties_total{{cluster_network="{net}",duty="attester"}}[{window}])) by (cluster_name) * 3600'):
        cn = d["metric"].get("cluster_name", "?")
        success_map[cn] = float(d["value"][1])

    expect_map = {}
    for d in pq(f'sum(rate(core_tracker_expect_duties_total{{cluster_network="{net}",duty="attester"}}[{window}])) by (cluster_name) * 3600'):
        cn = d["metric"].get("cluster_name", "?")
        expect_map[cn] = float(d["value"][1])

    # 8. Loki coverage
    print("  Loki coverage...", file=sys.stderr)
    loki_peers = set()
    if loki_url:
        loki_peers = loki_series(loki_url, headers,
                                 f'{{cluster_network="{net}"}}',
                                 (now - 3600) * 1_000_000_000,
                                 now * 1_000_000_000)

    # Build per-cluster data
    print("  Building fleet view...", file=sys.stderr)
    clusters = {}
    total_charon = {}
    total_bn = {}
    total_vc = {}
    total_nodes = 0

    all_observed = set(k[0] for k in node_info) | set(cluster_sizes.keys())

    for cn in sorted(all_observed):
        size = cluster_sizes.get(cn, 0)
        if size == 0:
            # Infer from observed peers
            size = len([k for k in node_info if k[0] == cn])
        if size == 0:
            continue

        category = categorise_cluster(cn, size)
        threshold = math.ceil(size * 2 / 3)
        validators = val_map.get(cn, 0)

        # Known peers
        known_peers = set(k[1] for k in node_info if k[0] == cn)
        unknown_count = max(0, size - len(known_peers))

        # Count clients
        bn_counts = {}
        vc_counts = {}
        charon_counts = {}
        for peer in known_peers:
            key = (cn, peer)
            bn = parse_bn_client(bn_map.get(key, "Unknown"))
            vc = parse_vc_client(vc_map.get(key, ""))
            cv = node_info.get(key, {}).get("charon_version", "?")
            bn_counts[bn] = bn_counts.get(bn, 0) + 1
            vc_counts[vc] = vc_counts.get(vc, 0) + 1
            charon_counts[cv] = charon_counts.get(cv, 0) + 1
            total_bn[bn] = total_bn.get(bn, 0) + 1
            total_vc[vc] = total_vc.get(vc, 0) + 1
            total_charon[cv] = total_charon.get(cv, 0) + 1
            total_nodes += 1

        if unknown_count > 0:
            bn_counts["Unknown"] = bn_counts.get("Unknown", 0) + unknown_count
            vc_counts["Unknown"] = vc_counts.get("Unknown", 0) + unknown_count
            total_bn["Unknown"] = total_bn.get("Unknown", 0) + unknown_count
            total_vc["Unknown"] = total_vc.get("Unknown", 0) + unknown_count
            total_nodes += unknown_count

        # Success rate
        success = success_map.get(cn, 0)
        expected = expect_map.get(cn, 0)
        success_pct = round((success / expected * 100) if expected > 0 else 100, 1)

        # Loki coverage for this cluster
        loki_count = sum(1 for k in loki_peers if k[0] == cn)

        clusters[cn] = {
            "category": category,
            "size": size,
            "threshold": threshold,
            "validators": validators,
            "attester_success_pct": success_pct,
            "failure_reasons": failure_rates.get(cn, {}),
            "bn_clients": bn_counts,
            "vc_clients": vc_counts,
            "charon_versions": charon_counts,
            "observed_peers": len(known_peers),
            "unknown_peers": unknown_count,
            "loki_peers": loki_count,
        }

    # Worst clusters
    worst = sorted(
        [(cn, c) for cn, c in clusters.items() if c["attester_success_pct"] < 100],
        key=lambda x: x[1]["attester_success_pct"]
    )[:10]

    # Aggregate failure reasons
    agg_reasons = {}
    for cn, c in clusters.items():
        for duty, reasons in c.get("failure_reasons", {}).items():
            for reason, rate in reasons.items():
                key = f"{duty}/{reason}"
                agg_reasons[key] = agg_reasons.get(key, 0) + rate

    # Category summary
    categories = {}
    for cn, c in clusters.items():
        cat = c["category"]
        categories.setdefault(cat, {"clusters": 0, "nodes": 0, "validators": 0})
        categories[cat]["clusters"] += 1
        categories[cat]["nodes"] += c["size"]
        categories[cat]["validators"] += c["validators"]

    output = {
        "network": net,
        "total_clusters": len(clusters),
        "total_nodes": total_nodes,
        "total_validators": sum(c["validators"] for c in clusters.values()),
        "categories": categories,
        "version_distribution": dict(sorted(total_charon.items(), key=lambda x: -x[1])),
        "bn_client_distribution": dict(sorted(total_bn.items(), key=lambda x: -x[1])),
        "vc_client_distribution": dict(sorted(total_vc.items(), key=lambda x: -x[1])),
        "worst_clusters": [
            {"name": cn, "success_pct": c["attester_success_pct"], "validators": c["validators"],
             "category": c["category"]}
            for cn, c in worst
        ],
        "top_failure_reasons": dict(sorted(agg_reasons.items(), key=lambda x: -x[1])[:15]),
        "loki_coverage": {
            "peers_with_logs": len(loki_peers),
            "total_observed_peers": sum(c["observed_peers"] for c in clusters.values()),
        },
        "clusters": clusters,
    }

    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    main()
