# DVpod in the Obol Stack

Use this when the dv-pod goes into an Obol Stack (k3d cluster managed by the `obol` CLI). Stack bring-up and node sync are the `run-obol-stack` skill; cluster creation is `create-cluster-invitation`.

## Rules specific to the Stack

- **Tools**: every `helm` / `kubectl` command in this skill becomes `obol helm …` / `obol kubectl …`. They always target the Stack, whatever `KUBECONFIG` says. Never use the user's default kubeconfig or context.
- **Install with `obol helm upgrade --install`**, as the chart README does. `obol app install` also works, but `obol app delete` deletes the whole namespace, PVCs (key shares) included.
- **Release name**: use `dv-pod-<network>` (e.g. `dv-pod-hoodi`). Because it contains `dv-pod`, `<fullname>` = release name, so the pod is `dv-pod-hoodi-0` and the ConfigMaps are `dv-pod-hoodi-enr` / `dv-pod-hoodi-dkg-status`.

## Gates before installing

1. **Chart and sidecar available.** The Stack flow needs chart **0.22.0+** (modes, status/ENR ConfigMaps, `statusReaders`), which needs the image `obolnetwork/charon-dkg-sidecar:1.1.0`:
   ```bash
   obol helm repo add obol https://obolnetwork.github.io/helm-charts && obol helm repo update
   obol helm search repo obol/dv-pod --versions | head
   curl -fsS -o /dev/null -w '%{http_code}\n' https://hub.docker.com/v2/repositories/obolnetwork/charon-dkg-sidecar/tags/1.1.0
   ```
   If 0.22.0 is missing or the tag check isn't `200`, the pod would sit in `ErrImagePull`: tell the user the Stack flow is **pending that release**. The interim option is the newest published chart < 0.22 in Launchpad mode only (no `mode`/`dkg.*`/`statusReaders`; read the public ENR from the ENR Secret's `enr` field; Hermes sees pods and logs but not DKG status; the DKG runs with the sidecar's bundled charon, so confirm its version with the other operators). Don't mix: every operator in one cluster should be on the same route and charon minor.
2. **Node synced.** `obol network status ethereum/<id>` must say `synced` (see `run-obol-stack`). Only on a testnet, and only if the user explicitly accepts it, may you install earlier and let `charon.publicnodeFallback` carry the pod; say that mainnet duties must never depend on publicnode.
3. **Inputs from the user**: `network` (must equal the node's network), the operator address (Launchpad route; never invent it), and the route from `create-cluster-invitation` (Launchpad, or a config hash / URL / definition file for the direct route).
4. **No MEV**: The Obol Stack runs no MEV-boost (local blocks until Gloas, in-protocol builder bids after it), so in the Stack `charon.builderApi` stays `false` (the example file sets it). The whole cluster must agree, so tell the user before they join a cluster that runs MEV.

## Install

Start from the chart's own example, pinned to the version you install:

```bash
obol helm pull obol/dv-pod --version 0.22.0 --untar --untardir ./dv-pod-chart
# -> ./dv-pod-chart/dv-pod/values-examples/obol-stack.yaml
```

It sets `mode: launchpad`, `network: mainnet` (the beacon defaults to the Stack's `ethereum-<network>` node), `publicnodeFallback: true`, `builderApi: false`, `serviceMonitor` with `release: monitoring` (the Stack's Prometheus), and `statusReaders` for Hermes (`hermes-obol-agent/hermes`). Override everything that is user-specific on the command line so it's visible:

```bash
obol helm upgrade --install dv-pod-hoodi obol/dv-pod --version 0.22.0 \
  -n dv-pod --create-namespace \
  -f ./dv-pod-chart/dv-pod/values-examples/obol-stack.yaml \
  --set network=hoodi \
  --set charon.operatorAddress=0xUSER_OPERATOR_ADDRESS \
  --set charon.builderApi=false \
  --timeout=10m
```

The beacon node defaults to `ethereum-hoodi`'s. If `obol network list` shows the node under another id (a second install of a network gets a petname), add `--set 'charon.beaconNodeEndpoints[0]=http://ethereum-beacon.ethereum-<id>.svc.cluster.local:5052'`.

That is the Launchpad route, and also step 1 of the direct route: the pod needs to exist to have an ENR, and in Launchpad mode it just waits (`WaitingForInvite`). Once the creator has published the definition containing that ENR, switch the same release to it — the ENR identity is kept on upgrade, and restarting a pod that hasn't done its DKG is harmless:

```bash
obol helm upgrade dv-pod-hoodi obol/dv-pod --version 0.22.0 -n dv-pod --reuse-values \
  --set mode=definition --set dkg.definition.configHash=0xCONFIG_HASH --timeout=10m
```

(If the definition already exists and contains this pod's ENR — e.g. reinstalling — install directly with `mode=definition`; no operator address is needed then.)

If the user enables `networkPolicy`, keep `networkPolicy.monitoring` allowing the `monitoring` namespace and add `extraFrom` for `hermes-obol-agent` (commented in the example).

## After install

```bash
obol kubectl get pod dv-pod-hoodi-0 -n dv-pod                     # Init:N/M until the DKG is done
obol kubectl get cm dv-pod-hoodi-enr -n dv-pod -o jsonpath='{.data.enr}'
obol kubectl get cm dv-pod-hoodi-dkg-status -n dv-pod -o jsonpath='{.data.phase}{"\n"}{.data.message}{"\n"}{.data.signatures}{"\n"}'
```

- **Launchpad route**: give the user the network's Launchpad URL and the pod's ENR; they connect the wallet for the operator address, paste **that** ENR and sign. The chart and sidecar never sign. Phase goes `WaitingForInvite` → `WaitingForSignatures` → `DefinitionReady` → `Complete`.
- **Direct route**: hand the ENR to the cluster creator, then run the `mode=definition` upgrade above with their config hash; the phase moves to `DefinitionReady` (ENR-mode definitions need no signatures).
- `Failed`: read `message`, then `obol kubectl logs dv-pod-hoodi-0 -n dv-pod -c dkg-sidecar` / `-c charon-dkg`.
- Charon itself: `-c dv-pod`. Readiness = `/readyz` (pod `READY`).
- After `Complete`: back up `/charon-data` (see SKILL.md backup), verify the lock and run `test-a-dv-cluster` before any deposit.

## Nickname and Obol monitoring (Launchpad metrics)

Two optional extras make the node show up properly on the Launchpad cluster page. Offer both, ideally at install
(each change later is a `helm upgrade` that restarts the pod; after `Complete` that skips a few duties, so ask first).

**Nickname** (`charon.nickname`, ≤ 32 chars). It is **public**: it appears on the Launchpad, in Obol's dashboards and
in the other operators' logs. Infer the context and propose one; the user confirms or picks another:
- **Organisation / enterprise deployment** (company names, an org wallet, a professional operator setup, "for our
  clients"): favour the organisation's own name for public legitimacy and visibility, e.g. `DV Labs`.
- **Private / personal use**: favour pseudonymity. Something that identifies the node without identifying a person or
  machine, e.g. the stack id plus network (`obol doctor` prints `stack <id> running` → `<id>-hoodi`). Never use the
  hostname, the user's name, email or wallet address unless they choose it.

**Monitoring token** (needs chart **0.22.1+** for `centralMonitoring.existingSecret`). **Always prefer
file → Kubernetes Secret → `centralMonitoring.existingSecret`** over putting the token in a values file or `--set`
(the same goes for any credential the chart can read from a Secret). The token must never pass through the chat, your
context, a Helm value or a command line. So never ask for it in chat, and never `cat`, `head`,
`grep` or open the file below. Hand the user a file instead:

1. Create an empty, private file (and don't clobber one that already has content):
   ```bash
   f="${OBOL_CONFIG_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/obol}/obol-monitoring-credential"
   test -s "$f" || ( umask 077 && mkdir -p "$(dirname "$f")" && : > "$f" ) ; echo "$f"
   ```
2. Tell the user, in these words or close: *"I made the file `<path>`. Open it, paste your Obol monitoring token and
   nothing else, save, and tell me when it's done. I won't read it; I'll load it into the stack so your node's
   performance metrics, nickname and client choices show up on the Launchpad."* If they don't have a token, they get
   one from Obol; don't proceed without it.
3. Check it **without reading it**: size and line count only.
   ```bash
   wc -c < "$f"; wc -l < "$f"     # expect tens of bytes or more, and 0 or 1 lines
   ```
   Empty, or several lines: ask the user to fix the file. A trailing newline is fine (Prometheus trims it).
4. Load it into a Secret in the release's namespace, then point the release at it:
   ```bash
   obol kubectl create secret generic obol-monitoring -n dv-pod --from-file=token="$f" \
     --dry-run=client -o yaml | obol kubectl apply -f - >/dev/null && echo stored
   obol kubectl get secret obol-monitoring -n dv-pod -o name   # presence check: name only, never -o yaml/json
   obol helm upgrade dv-pod-hoodi obol/dv-pod --version 0.22.1 -n dv-pod --reuse-values \
     --set centralMonitoring.enabled=true --set centralMonitoring.existingSecret=obol-monitoring \
     --set charon.nickname=<confirmed nickname> --timeout=10m
   ```
   This adds a `dv-pod-hoodi-prometheus` pod that remote-writes charon's metrics to Obol. Never use
   `centralMonitoring.token`: it lands in the Helm release and `helm get values` prints it.
5. Verify: `obol kubectl logs deploy/dv-pod-hoodi-prometheus -n dv-pod --tail=50` shows no remote-write `401`/`403`.
   A 401 means a wrong token: the user edits the file again, you repeat step 4's first command (Prometheus re-reads
   the token, no restart needed).
6. Offer to delete the file now that the Secret holds the token (`rm "$f"`); to rotate later, repeat from step 1.

## Hand off to Hermes

With `statusReaders` set, the in-stack Hermes agent can `get` (not list) both ConfigMaps by name and scrape metrics through the Stack's Prometheus. Tell the user to install the steward skill and schedule it (details in `run-obol-stack` → "Run your part of a Distributed Validator"): `obol agent skills add dv-steward distributed-validators`.
