# DVpod in the Obol Stack

Use this when the dv-pod goes into an Obol Stack (k3d cluster managed by the `obol` CLI). Stack bring-up and node sync are the `run-obol-stack` skill; cluster creation is `create-cluster-invitation`.

## Rules specific to the Stack

- **Tools**: every `helm` / `kubectl` command in this skill becomes `obol helm …` / `obol kubectl …`. They always target the Stack, whatever `KUBECONFIG` says. Never use the user's default kubeconfig or context.
- **Check `obol version` first.** The flow below needs **obol v0.19.0+** (`obol/` chart alias, release names, overrides-only values, drift guard, data-safe delete, `obol app secret`). On an older obol, have the user upgrade, or use the plain-helm flow at the end. **Before v0.19, `obol app delete` deletes the whole namespace, key-share PVCs included**: never run it there on a dv-pod.
- **Install and change a new dv-pod only through `obol app`**: `obol app install` writes the app's `values.yaml`, `obol app sync` deploys it. Change it by editing that values.yaml (or `obol app sync <app>/<id> --set k=v`, which is saved into it) and syncing again. **Never `obol helm upgrade` an `obol app`-managed dv-pod**: the next sync refuses because the release drifted, and with `--force` reverts the change.
- **Names**: `obol app install obol/dv-pod@<version> --name dv-pod --id <network>` gives release **and** namespace `dv-pod-<network>` (e.g. `dv-pod-hoodi`; `--release`/`--namespace` override them, mainly for adopting an existing release). Because the release contains `dv-pod`, `<fullname>` = release name: the pod is `dv-pod-hoodi-0` in namespace `dv-pod-hoodi`, the ConfigMaps `dv-pod-hoodi-enr` / `dv-pod-hoodi-dkg-status`. The app identifier for `obol app` commands is `dv-pod/hoodi`.
- **values.yaml** lives at `~/.config/obol/applications/dv-pod/<id>/values.yaml` (under `$OBOL_CONFIG_DIR`). It starts from the chart's `values-examples/obol-stack.yaml` (comments kept) plus your `--set`s, and holds only overrides, so chart upgrades bring new defaults. `0x…` values stay quoted.
- **Delete is data-safe (v0.19+)**: `obol app delete dv-pod/<id>` sees the PVCs and ENR Secrets and removes only the helm release; `obol app sync` redeploys onto the same identity and data. `--delete-data` destroys key shares and the ENR key: treat it like `destroy` (backup first, explicit confirmation, never on active validators).

## Gates before installing

1. **Chart available.** This flow targets chart **0.24.0** (charon `v1.11.4`), the first with `mode: enr`. Check it is published:
   ```bash
   obol helm repo add obol https://obolnetwork.github.io/helm-charts && obol helm repo update
   obol helm search repo obol/dv-pod --versions | head
   ```
   If 0.24.0 isn't listed yet, use 0.23.x and skip `mode: enr` (0.23 has no identity-only mode; see "No definition yet" below). Charts < 0.22 lack the modes, status ConfigMaps and `statusReaders` this flow relies on: don't use them in the Stack.
2. **Node synced.** `obol network status ethereum/<id>` must say `synced` (see `run-obol-stack`). Only on a testnet, and only if the user explicitly accepts it, may you install earlier and let `charon.publicnodeFallback` carry the pod; say that mainnet duties must never depend on publicnode.
3. **Inputs from the user**: `network` (must equal the node's network), the operator address (Launchpad route; never invent it), and the route from `create-cluster-invitation` (Launchpad, or a config hash / URL / definition file for the direct route).
4. **No MEV**: the Obol Stack runs no MEV-boost (local blocks until Gloas, in-protocol builder bids after it), so in the Stack `charon.builderApi` stays `false` (the example file sets it). The whole cluster must agree, so tell the user before they join a cluster that runs MEV.
5. **Gloas**: charon v1.11.x (chart 0.24.0 included) is not Gloas-ready; Gloas support comes with charon v2.0.0. Sepolia has already forked into Gloas, and Hoodi's fork is planned for 2026-12-15. Don't start a new Sepolia DV on this chart, and tell Hoodi users their DV (and node, see `run-obol-stack`) needs a later release before the fork.

## Install

```bash
obol app install obol/dv-pod@0.24.0 --name dv-pod --id hoodi \
  --set network=hoodi \
  --set charon.operatorAddress=0xUSER_OPERATOR_ADDRESS \
  --set charon.nickname=<confirmed nickname>
obol app sync dv-pod/hoodi
```

- **Always `--set network=<network>`**: the seeded example says `network: mainnet`, and `--id` doesn't change it.
- The example also sets `mode: launchpad`, `publicnodeFallback: true`, `builderApi: false`, `nickname: "obol-stack"`, a `serviceMonitor` with `release: monitoring` (the Stack's Prometheus) and `statusReaders` for Hermes (`hermes-obol-agent/hermes`). Replace the placeholder nickname with one the user confirmed (see below).
- The beacon node defaults to `http://ethereum-beacon.ethereum-<network>.svc.cluster.local:5052`. If `obol network list` shows the node under another id (a second install of a network gets a petname), add `--set 'charon.beaconNodeEndpoints[0]=http://ethereum-beacon.ethereum-<id>.svc.cluster.local:5052'`. The same applies when a Silver node misbehaves and the user adds a fallback node (`--id hoodi-lighthouse`, see `run-obol-stack`). A Silver node needs obol v0.19+ for in-cluster callers: earlier Silver answered `403 host not allowed` to service names.

That is the Launchpad route: the pod waits in `WaitingForInvite` until the user signs on the Launchpad (pass `--set charon.dkgSidecar.targetConfigHash=0x…` to pin one invite).

### No definition yet: identity first (`mode: enr`, chart 0.24.0+)

For the direct route, or whenever the user needs to hand out an ENR before any cluster definition exists, install with `mode: enr` instead of an operator address:

```bash
obol app install obol/dv-pod@0.24.0 --name dv-pod --id hoodi --set network=hoodi --set mode=enr
obol app sync dv-pod/hoodi
obol kubectl get cm dv-pod-hoodi-enr -n dv-pod-hoodi -o jsonpath='{.data.enr}'
```

The chart creates and publishes the ENR and nothing else: no pod runs, nothing polls the Obol API, and the status ConfigMap reads `WaitingForDefinition`. Once the definition exists, edit values.yaml and sync; the same ENR Secret is reused, so the shared ENR stays valid:

```yaml
mode: definition
dkg:
  definition:
    configHash: "0xCONFIG_HASH"
```
```bash
obol app sync dv-pod/hoodi    # the pod and its PVCs are created now
```

(Or `mode: launchpad` + `charon.operatorAddress` if the cluster is created on the Launchpad after all.)

- **Never park a node on a fake or placeholder Launchpad invite** to get an ENR: it keeps polling the Obol API for an invite that will never be real. Use `mode: enr` (0.24+). On 0.23.x (no `mode: enr`), the waiting pod has to run in `launchpad` mode with the user's real operator address, which polls the Obol API; prefer 0.24.
- **Never switch a running validator to `mode: enr`**: it scales the pod to zero, stopping charon and the validator client (PVCs are kept). Ask before any mode change on a release that has done its DKG.

If the definition already exists and contains this node's ENR (e.g. reinstalling with an existing identity), install directly with `mode=definition`; no operator address is needed.

If the user enables `networkPolicy`, keep `networkPolicy.monitoring` allowing the `monitoring` namespace and add `extraFrom` for `hermes-obol-agent` (commented in the example).

## After install

```bash
obol app list
obol kubectl get pod dv-pod-hoodi-0 -n dv-pod-hoodi                     # Init:N/M until the DKG is done (no pod in mode enr)
obol kubectl get cm dv-pod-hoodi-enr -n dv-pod-hoodi -o jsonpath='{.data.enr}'
obol kubectl get cm dv-pod-hoodi-dkg-status -n dv-pod-hoodi -o jsonpath='{.data.phase}{"\n"}{.data.message}{"\n"}{.data.signatures}{"\n"}'
```

- **Launchpad route**: give the user the network's Launchpad URL and the pod's ENR; they connect the wallet for the operator address, paste **that** ENR and sign. The chart and sidecar never sign. Phase goes `WaitingForInvite` → `WaitingForSignatures` → `DefinitionReady` → `Complete`.
- **Direct route**: `WaitingForDefinition` (mode enr) → hand the ENR to the cluster creator → set `mode: definition` + config hash and sync → `DefinitionReady` (ENR-mode definitions need no signatures) → `Complete`.
- `Failed`: read `message`, then `obol kubectl logs dv-pod-hoodi-0 -n dv-pod-hoodi -c dkg-sidecar` / `-c charon-dkg`.
- Charon itself: `-c dv-pod`. Readiness = `/readyz` (pod `READY`).
- After `Complete`: back up `/charon-data` (see SKILL.md backup; in the Stack `obol kubectl cp dv-pod-hoodi/dv-pod-hoodi-0:/charon-data … -c validator-client`), verify the lock and run `test-a-dv-cluster` before any deposit.

## Peers and the outside world

- **p2p goes through relays.** The Stack publishes no p2p port (k3d maps only 80/8080/443/8443), so operators outside this machine reach a Stack dv-pod only via charon relays (`charon.p2pRelays`, Obol's by default). The DKG and duties work over relays with an extra hop. dv-pods in the same Stack talk directly over cluster DNS. Direct inbound connections need host-level changes (a NodePort, a k3d port mapping that `stack init --force` drops, router forwarding): point the user at "Peer connectivity" in `ObolNetwork/obol-stack/docs/guides/apps.md` rather than improvising.
- **A charon outside the Stack on the same host** (Docker Compose, a test cluster) can use the Stack's node: `obol network expose ethereum/<id> --beacon` (Docker Desktop: `http://host.docker.internal:5052`; Linux: `--bind 172.17.0.1`, then `http://172.17.0.1:<port>`). Never `--allow-public` unless a firewall keeps the port off the internet.

## Nickname and Obol monitoring (Launchpad metrics)

Two optional extras make the node show up properly on the Launchpad cluster page. Offer both, ideally at install (each change later is an `obol app sync` that restarts the pod; after `Complete` that skips a few duties, so ask first).

**Nickname** (`charon.nickname`, ≤ 32 chars; the example's `obol-stack` is a placeholder). It is **public**: it appears on the Launchpad, in Obol's dashboards and in the other operators' logs. Infer the context and propose one; the user confirms or picks another:
- **Organisation / enterprise deployment** (company names, an org wallet, a professional operator setup, "for our clients"): favour the organisation's own name for public legitimacy and visibility, e.g. `DV Labs`.
- **Private / personal use**: favour pseudonymity. Something that identifies the node without identifying a person or machine, e.g. the stack id plus network (`obol doctor` prints `stack <id> running` → `<id>-hoodi`). Never use the hostname, the user's name, email or wallet address unless they choose it.

**Monitoring token**. **Always file → Kubernetes Secret → `centralMonitoring.existingSecret`**, never a values file or `--set` (the same goes for any credential the chart can read from a Secret). The token must never pass through the chat, your context, a Helm value or a command line. So never ask for it in chat, and never `cat`, `head`, `grep` or open the file below. Hand the user a file instead:

1. Create an empty, private file (and don't clobber one that already has content):
   ```bash
   f="${OBOL_CONFIG_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/obol}/obol-monitoring-credential"
   test -s "$f" || ( umask 077 && mkdir -p "$(dirname "$f")" && : > "$f" ) ; echo "$f"
   ```
2. Tell the user, in these words or close: *"I made the file `<path>`. Open it, paste your Obol monitoring token and nothing else, save, and tell me when it's done. I won't read it; I'll load it into the stack so your node's performance metrics, nickname and client choices show up on the Launchpad."* If they don't have a token, they get one from Obol; don't proceed without it.
3. Check it **without reading it**: size and line count only.
   ```bash
   wc -c < "$f"; wc -l < "$f"     # expect tens of bytes or more, and 0 or 1 lines
   ```
   Empty, or several lines: ask the user to fix the file. A trailing newline is fine (Prometheus trims it).
4. Load it into a Secret in the app's namespace (obol reads the file itself and never prints it; it creates the namespace if needed), then point the release at it:
   ```bash
   obol app secret set dv-pod/hoodi obol-monitoring --from-file token="$f"
   obol app secret list dv-pod/hoodi       # names, types and key names only
   ```
   In values.yaml set `centralMonitoring.enabled: true`, `centralMonitoring.existingSecret: obol-monitoring` (key `token`, the chart default) and the confirmed `charon.nickname`, then `obol app sync dv-pod/hoodi`. This adds a `dv-pod-hoodi-prometheus` pod that remote-writes charon's metrics to Obol (not in `mode: enr`, which runs nothing). Never use `centralMonitoring.token`: it lands in the Helm release and `helm get values` prints it.
5. Verify: `obol kubectl logs deploy/dv-pod-hoodi-prometheus -n dv-pod-hoodi --tail=50` shows no remote-write `401`/`403`. A 401 means a wrong token: the user edits the file again, you repeat `obol app secret set` (Prometheus re-reads the token, no restart needed).
6. Offer to delete the file now that the Secret holds the token (`rm "$f"`); to rotate later, repeat from step 1.

## Upgrade

```bash
obol helm repo update
obol app upgrade dv-pod/hoodi --version <new-chart-version>
```

It checks the version exists, sets it in the app's `helmfile.yaml` and syncs with the drift check (if the release drifted, the sync is refused and the version is put back; `--force` overrides, reverting the drift). values.yaml holds only overrides, so the new chart's defaults (charon tag included) apply; values.yaml itself isn't changed, so read the new version's README "Upgrading from chart < X" and its `values-examples/obol-stack.yaml` for new settings. If obol warns that values.yaml is a full copy of old defaults (pre-v0.19 apps), slim it first (`obol app install obol/dv-pod@<new> --name dv-pod --id <id> --force --values <overrides.yaml>`). Ask before upgrading a release with active validators (the restart skips a few duties), and never upgrade more than one node of an active cluster at a time. (Manual equivalent: edit `version:` in `~/.config/obol/applications/dv-pod/<id>/helmfile.yaml`, then `obol app sync`.)

## Existing plain-helm dv-pods

A dv-pod installed before v0.19 with `obol helm upgrade --install` (e.g. release `dv-pod-hoodi` or `my-dv-pod` in namespace `dv-pod`) can either move to obol app or stay on helm. Ask the user which.

**Adopt it** (recommended; keeps the namespace, release, ENR Secret and PVCs, so the identity and data are untouched):

```bash
obol helm list -n dv-pod                                   # release name and its current chart version
obol app install obol/dv-pod@<its-current-chart-version> --name dv-pod --id hoodi \
  --namespace dv-pod --release dv-pod-hoodi --adopt
obol app sync dv-pod/hoodi                                 # records the baseline; no change expected
obol app upgrade dv-pod/hoodi --version 0.24.0             # then upgrade separately
```

Adopt at the version it runs now, so the adoption itself changes nothing. values.yaml is seeded from the release's current values (`helm get values`), and the release's revision becomes the sync baseline. From then on, change it only through values.yaml + `obol app sync` / `obol app upgrade`. Stack-owned namespaces can't be used; `dv-pod` is fine. If other helm releases share that namespace, `obol app delete` removes only this release, and `--delete-data` refuses and names the PVCs to delete.

**Or stay on helm**:

```bash
obol helm upgrade dv-pod-hoodi obol/dv-pod --version 0.24.0 -n dv-pod --reset-then-reuse-values --timeout=10m
```

`--reset-then-reuse-values`, never plain `--reuse-values`: on 0.24 that would keep charon v1.11.3 and old defaults. Central monitoring there: `obol kubectl create secret generic obol-monitoring -n dv-pod --from-file=token="$f" --dry-run=client -o yaml | obol kubectl apply -f - >/dev/null` then `--set centralMonitoring.enabled=true --set centralMonitoring.existingSecret=obol-monitoring` on that upgrade. Don't `obol app delete` a release obol app doesn't manage.

## Hand off to Hermes

With `statusReaders` set, the in-stack Hermes agent can `get` (not list) both ConfigMaps by name and scrape metrics through the Stack's Prometheus. Tell the user to install the steward skill and schedule it (details in `run-obol-stack` → "Run your part of a Distributed Validator"): `obol agent skills add dv-steward distributed-validators`.
