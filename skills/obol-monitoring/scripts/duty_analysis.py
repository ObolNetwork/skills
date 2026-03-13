#!/usr/bin/env python3
"""Deep slot-level duty failure analysis with timeline reconstruction.

Usage: python3 duty_analysis.py "Cluster Name" 13867535 [--duty attester] [--network mainnet]
Requires: OBOL_GRAFANA_API_TOKEN environment variable.
Outputs: JSON to stdout, progress to stderr.
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.grafana import (
    get_auth_headers, discover_datasources, prom_query, loki_query,
    cluster_selector, slot_to_time, slot_to_timestamp,
    parse_embedded_ts, extract_logfmt, get_cluster_size,
)


def main():
    parser = argparse.ArgumentParser(description="Duty analysis for a specific slot")
    parser.add_argument("cluster_name", help="Cluster name")
    parser.add_argument("slot", type=int, help="Slot number")
    parser.add_argument("--duty", default="attester", help="Duty type (default: attester)")
    parser.add_argument("--network", default="mainnet")
    args = parser.parse_args()

    headers = get_auth_headers()
    prom_url, loki_url = discover_datasources(headers)
    sel = cluster_selector(args.cluster_name, args.network)

    slot_ts = slot_to_timestamp(args.slot, args.network)
    if not slot_ts:
        print(json.dumps({"error": f"Unknown genesis for network {args.network}"}))
        sys.exit(1)

    slot_time = slot_to_time(args.slot, args.network)
    size = get_cluster_size(prom_url, headers, args.cluster_name, args.network) if prom_url else 0

    print(f"Analyzing slot {args.slot} ({slot_time}) for {args.cluster_name}...", file=sys.stderr)

    events = []

    if loki_url:
        # Query 30s window around slot
        start_ns = (slot_ts - 5) * 1_000_000_000
        end_ns = (slot_ts + 30) * 1_000_000_000

        duty_pattern = f"{args.slot}/{args.duty}"
        logql = (
            f'{{{sel}}} '
            f'|~ `{duty_pattern}|slot={args.slot}` '
            f'|~ `QBFT|consensus|Beacon node call|Slot ticked|aggregated|submitted|timeout`'
        )

        print("  Querying Loki...", file=sys.stderr)
        raw = loki_query(loki_url, headers, logql, start_ns, end_ns, limit=500)

        if raw:
            for stream in raw.get("data", {}).get("result", []):
                peer = stream.get("stream", {}).get("cluster_peer", "unknown")
                for ts_str, line in stream.get("values", []):
                    embedded = parse_embedded_ts(line)
                    ts = embedded if embedded else int(ts_str) / 1e9
                    offset = ts - slot_ts

                    msg = extract_logfmt(line, "msg")
                    level = extract_logfmt(line, "level")
                    rnd = extract_logfmt(line, "round")
                    new_round = extract_logfmt(line, "new_round")
                    rule = extract_logfmt(line, "rule")
                    timeout_reason = extract_logfmt(line, "timeout_reason")
                    leader_name = extract_logfmt(line, "leader_name")
                    leader_index = extract_logfmt(line, "leader_index")
                    endpoint = extract_logfmt(line, "endpoint")
                    rtt = extract_logfmt(line, "rtt")

                    event = {
                        "offset_s": round(offset, 3),
                        "peer": peer,
                        "level": level,
                        "msg": msg,
                    }
                    if rnd: event["round"] = rnd
                    if new_round: event["new_round"] = new_round
                    if rule: event["rule"] = rule
                    if timeout_reason: event["timeout_reason"] = timeout_reason
                    if leader_name: event["leader_name"] = leader_name
                    if leader_index: event["leader_index"] = leader_index
                    if endpoint: event["endpoint"] = endpoint
                    if rtt: event["rtt"] = rtt

                    events.append(event)

    events.sort(key=lambda e: e["offset_s"])

    # Determine outcome
    decided = False
    decided_round = None
    decided_leader = None
    timed_out = False

    for e in events:
        if "consensus decided" in e.get("msg", "").lower():
            decided = True
            decided_round = e.get("round")
            decided_leader = e.get("leader_name")
        if "consensus timeout" in e.get("msg", "").lower():
            timed_out = True

    # Extract BN call timings
    bn_calls = []
    for e in events:
        if e.get("endpoint") and e.get("rtt"):
            bn_calls.append({
                "peer": e["peer"],
                "endpoint": e["endpoint"],
                "rtt": e["rtt"],
                "offset_s": e["offset_s"],
            })

    # Identify participating peers
    participating_peers = set()
    for e in events:
        if "upon rule" in e.get("msg", "").lower() or "decided" in e.get("msg", "").lower():
            participating_peers.add(e["peer"])

    output = {
        "cluster_name": args.cluster_name,
        "network": args.network,
        "slot": args.slot,
        "slot_time": slot_time,
        "duty_type": args.duty,
        "cluster_size": size,
        "outcome": {
            "decided": decided,
            "timed_out": timed_out,
            "decided_round": decided_round,
            "decided_leader": decided_leader,
        },
        "participating_peers": sorted(participating_peers),
        "event_count": len(events),
        "events": events,
        "bn_calls": bn_calls,
    }

    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    main()
