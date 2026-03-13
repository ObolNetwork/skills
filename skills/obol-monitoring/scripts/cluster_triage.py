#!/usr/bin/env python3
"""First-pass cluster health check.

Usage: python3 cluster_triage.py "Cluster Name" [--network mainnet] [--hours 1]
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
    get_cluster_size, cluster_selector, parse_bn_client, parse_vc_client,
)


def main():
    parser = argparse.ArgumentParser(description="Cluster health triage")
    parser.add_argument("cluster_name", help="Cluster name")
    parser.add_argument("--network", default="mainnet")
    parser.add_argument("--hours", type=int, default=1)
    args = parser.parse_args()

    headers = get_auth_headers()
    prom_url, loki_url = discover_datasources(headers)
    if not prom_url:
        print(json.dumps({"error": "Could not discover Prometheus datasource"}))
        sys.exit(1)

    sel = cluster_selector(args.cluster_name, args.network)
    window = f"{args.hours}h"
    now = int(time.time())

    def pq(query):
        return prom_query(prom_url, headers, query)

    # 1. Cluster config
    print("  Cluster config...", file=sys.stderr)
    size = get_cluster_size(prom_url, headers, args.cluster_name, args.network)
    threshold_r = pq(f'cluster_threshold{{{sel}}}')
    threshold = int(float(threshold_r[0]["value"][1])) if threshold_r else math.ceil(size * 2 / 3)
    validators_r = pq(f'core_scheduler_validators_active{{{sel}}}')
    validators = max((int(float(d["value"][1])) for d in validators_r), default=0)

    # 2. Readyz
    print("  Health status...", file=sys.stderr)
    readyz = {}
    for d in pq(f'app_monitoring_readyz{{{sel}}}'):
        readyz[d["metric"].get("cluster_peer", "?")] = int(float(d["value"][1]))

    # 3. Versions
    print("  Versions...", file=sys.stderr)
    versions = {}
    for d in pq(f'app_version{{{sel}}}'):
        peer = d["metric"].get("cluster_peer", "?")
        versions.setdefault(peer, {})["charon"] = d["metric"].get("version", "?")
        versions[peer]["nickname"] = d["metric"].get("nickname", "")

    for d in pq(f'app_beacon_node_version{{{sel}}}'):
        peer = d["metric"].get("cluster_peer", "?")
        versions.setdefault(peer, {})["bn"] = parse_bn_client(d["metric"].get("version", "?"))
        versions[peer]["bn_version"] = d["metric"].get("version", "?")

    for d in pq(f'core_validatorapi_vc_user_agent{{{sel}}}'):
        peer = d["metric"].get("cluster_peer", "?")
        versions.setdefault(peer, {})["vc"] = parse_vc_client(d["metric"].get("user_agent", ""))

    observed_peers = set(versions.keys()) | set(readyz.keys())
    missing_count = max(0, size - len(observed_peers))

    # 4. Consensus
    print("  Consensus performance...", file=sys.stderr)
    consensus = {}
    for duty in ["attester", "proposer", "sync_contribution"]:
        to_r = pq(f'sum(rate(core_consensus_timeout_total{{{sel},duty="{duty}"}}[{window}])) by (cluster_peer) * 3600')
        dec_r = pq(f'sum(rate(core_consensus_duration_seconds_count{{{sel},duty="{duty}"}}[{window}])) by (cluster_peer) * 3600')
        total_to = sum(float(d["value"][1]) for d in to_r)
        total_dec = sum(float(d["value"][1]) for d in dec_r)
        total = total_to + total_dec
        consensus[duty] = {
            "timeout_rate_per_hour": round(total_to, 1),
            "decision_rate_per_hour": round(total_dec, 1),
            "timeout_pct": round((total_to / total * 100) if total > 0 else 0, 2),
        }

    # 5. Participation
    print("  Participation...", file=sys.stderr)
    participation = {}
    for d in pq(f'sum(rate(core_tracker_participation_missed_total{{{sel},duty="attester"}}[{window}])) by (cluster_peer, peer) * 3600'):
        src = d["metric"].get("cluster_peer", "?")
        dst = d["metric"].get("peer", "?")
        val = float(d["value"][1])
        if val > 0:
            participation.setdefault(dst, {"missed_by_peers": {}})
            participation[dst]["missed_by_peers"][src] = round(val, 0)
            participation[dst]["avg_missed"] = round(
                sum(participation[dst]["missed_by_peers"].values()) / len(participation[dst]["missed_by_peers"]), 0
            )

    # 6. Failure reasons
    print("  Failure reasons...", file=sys.stderr)
    failure_reasons = {}
    for d in pq(f'sum(rate(core_tracker_failed_duty_reasons_total{{{sel}}}[{window}])) by (duty, reason) * 3600'):
        duty = d["metric"].get("duty", "?")
        reason = d["metric"].get("reason", "?")
        val = float(d["value"][1])
        if val > 0:
            failure_reasons.setdefault(duty, {})[reason] = round(val, 1)

    # 7. P2P
    print("  P2P connectivity...", file=sys.stderr)
    p2p = {}
    for d in pq(f'p2p_ping_success{{{sel}}}'):
        src = d["metric"].get("cluster_peer", "?")
        dst = d["metric"].get("peer", "?")
        val = d["value"][1]
        p2p.setdefault(src, {"ping_success": {}})[  "ping_success"][dst] = val == "1"

    for d in pq(f'histogram_quantile(0.9, sum(rate(p2p_ping_latency_secs_bucket{{{sel}}}[{window}])) by (cluster_peer, peer, le))'):
        src = d["metric"].get("cluster_peer", "?")
        dst = d["metric"].get("peer", "?")
        try:
            ms = round(float(d["value"][1]) * 1000, 1)
            p2p.setdefault(src, {}).setdefault("ping_latency_p90_ms", {})[dst] = ms
        except (ValueError, TypeError):
            pass

    for d in pq(f'p2p_peer_connection_types{{{sel}}}'):
        src = d["metric"].get("cluster_peer", "?")
        dst = d["metric"].get("peer", "?")
        typ = d["metric"].get("type", "?")
        try:
            if float(d["value"][1]) > 0:
                p2p.setdefault(src, {}).setdefault("connections", {}).setdefault(dst, []).append(typ)
        except (ValueError, TypeError):
            pass

    # 8. Beacon node health
    print("  BN health...", file=sys.stderr)
    beacon_node = {}
    for d in pq(f'app_beacon_node_peers{{{sel}}}'):
        peer = d["metric"].get("cluster_peer", "?")
        try:
            beacon_node.setdefault(peer, {})["peers"] = int(float(d["value"][1]))
        except (ValueError, TypeError):
            pass

    for d in pq(f'histogram_quantile(0.5, sum(rate(app_eth2_latency_seconds_bucket{{{sel},endpoint="attestation_data"}}[{window}])) by (cluster_peer, le))'):
        peer = d["metric"].get("cluster_peer", "?")
        try:
            beacon_node.setdefault(peer, {})["attestation_data_p50_ms"] = round(float(d["value"][1]) * 1000, 1)
        except (ValueError, TypeError):
            pass

    # 9. Balance
    print("  Balance...", file=sys.stderr)
    balance_r = pq(f'sum(core_scheduler_validator_balance_gwei{{{sel}}}) by (cluster_peer)')
    balance_eth = 0
    if balance_r:
        # Take value from one peer (all report same pubkey balances)
        balance_eth = round(float(balance_r[0]["value"][1]) / 1e9, 2)

    # 10. Loki presence
    print("  Log availability...", file=sys.stderr)
    logs_available = {}
    if loki_url:
        loki_peers = loki_series(loki_url, headers,
                                 f'{{{sel}}}',
                                 (now - 3600) * 1_000_000_000,
                                 now * 1_000_000_000)
        for peer in observed_peers:
            logs_available[peer] = (args.cluster_name, peer) in loki_peers

    # Determine overall health
    attester_fail = consensus.get("attester", {}).get("timeout_pct", 0)
    any_readyz_bad = any(v != 1 for v in readyz.values())
    if attester_fail > 10 or any_readyz_bad:
        overall = "critical"
    elif attester_fail > 2:
        overall = "degraded"
    else:
        overall = "healthy"

    output = {
        "cluster_name": args.cluster_name,
        "network": args.network,
        "cluster_config": {
            "operators": size,
            "threshold": threshold,
            "fault_tolerance": size - threshold,
            "validators": validators,
            "observed_peers": len(observed_peers),
            "missing_peers": missing_count,
        },
        "health": {
            "overall": overall,
            "readyz": readyz,
        },
        "versions": versions,
        "consensus": consensus,
        "participation_missed": participation,
        "duty_failures": failure_reasons,
        "p2p": p2p,
        "beacon_node": beacon_node,
        "balance": {
            "total_eth": balance_eth,
            "validators": validators,
        },
        "logs_available": logs_available,
    }

    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    main()
