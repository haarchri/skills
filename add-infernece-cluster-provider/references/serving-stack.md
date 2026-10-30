# Serving stack for a new cloud

Read `design/serving-stack-generation.md` in the Modelplane repo first; this
file is the checklist that design implies for one new cloud.

## Where the cloud fits

A ServingStack installs `join(cloud, stack)`: one cloud half plus
`common.py` (every cloud, every stack: Envoy Gateway, AI Gateway, GAIE CRDs,
gateway namespace and EnvoyProxy, PKI, trust-manager, the DRA driver pod
quota) plus the stack file (`standard.py`: LeaderWorkerSet; `dynamo.py`:
Grove, kai-scheduler and Queues, ModelExpress).

| Cloud half | Where | Who writes it |
|---|---|---|
| EKS, AKS, GKE | `stacks/clouds/generated/aicr/` | `nix run .#stacks` from NVIDIA AICR; never hand-edit |
| Nebius, Vultr, Civo, Existing, your cloud | `stacks/clouds/<cloud>.py` | by hand, in the generator's shape |

A new cloud is a hand-written half unless AICR has a `service` value for it.
Adding a cloud to the generator is a separate, larger change (see
CONTRIBUTING "Bumping aicr"); don't fold it into a provider PR.

Don't touch `common.py`, `standard.py`, `dynamo.py` or `generated/` for a new
cloud. If you think you must, that's a design question for the issue.

## What the half must provide

The stack contract (design doc, "The contract a stack has to keep") needs a
working `gpu.nvidia.com` DeviceClass and ResourceSlices, plus what `common.py`
depends on across the join. Every half carries, by component key:

| Key | Required | Notes |
|---|---|---|
| `cert-manager` | always | `wait=True` (Envoy Gateway in `common.py` depends on it across halves); `crds.enabled: true` so CRDs survive uninstall. Same pin as the other halves |
| `kube-prometheus-stack` | always | same pin and values as the other hand-written halves |
| `node-feature-discovery` | unless the cloud runs NFD itself | worker tolerates `nvidia.com/gpu` (`operator: Exists`). Without it: no `pci-10de` label, no kubelet plugin, no ResourceSlices, every claim unallocatable while everything looks healthy. Vultr omits it because its managed operator runs NFD and a second one would race it |
| `gpu-operator` | only when the node image has no driver and the cloud has no managed operator | driver on, toolkit off if the image has it, device plugin off, NFD off (standalone above), DaemonSets tolerate the GPU taint, `wait=True`, `depends_on` NFD and cert-manager. Driver pin mirrors the generated halves |
| `nvidia-dra-driver-gpu` | always | namespace `nvidia-dra-driver` (common.py's quota targets it), release `mp-dra-driver-nvidia-gpu`, `gpuResourcesEnabledOverride: true`, compute domains off. `nvidiaDriverRoot`: default `/` when the image has the driver; `/run/nvidia/driver` when the operator installs it, plus `depends_on: [gpu-operator]` |
| `dcgm-exporter` | when neither the cloud nor an installed GPU operator supplies one | NVIDIA's standalone chart, as `upcloud.py` has it: the shared `DCGM_METRICS_CSV` in `customMetrics` (unset, the chart's shorter default silently exports fewer fields than every other cloud), `kubernetesDRA.enabled: true` so series attribute to DRA-allocated pods, the GPU taint toleration, affinity = the DRA kubelet plugin's PCI `nodeSelectorTerms`, `serviceMonitor` off (the collector finds the pod itself) |

GPU-only charts — NFD, the DRA driver, the DCGM exporter — carry
`dra_drivers=["gpu.nvidia.com"]` so they stay off clusters whose classes
claim no GPUs, and the half declares `EXTERNAL_DRIVERS` (DRA drivers that
arrive outside the stack; usually `[]`). `stacks/__init__.py`'s
supported-drivers table folds `EXTERNAL_DRIVERS` into what the chart tags
derive.

## Decide from the cloud's GPU stack

| Node image / cloud | Half looks like | Cluster function does |
|---|---|---|
| driver in image, no operator | Nebius, UpCloud: NFD + DRA driver (+ standalone dcgm-exporter on UpCloud) | taints GPU pools |
| managed GPU Operator add-on | Vultr: no NFD, DRA driver at `/` | labels GPU pools `nvidia.com/gpu.deploy.device-plugin=false`; gates readiness on an observe-only Object of the operator's validator |
| no driver, no operator | Civo: NFD + gpu-operator (driver) + DRA driver at `/run/nvidia/driver` | no GPU readiness gate: the operator arrives after the cluster XR is Ready, so a gate would deadlock |

In every row the DRA driver is the only GPU allocator. Two ledgers over the
same devices (device plugin and DRA) is the bug to avoid.

## Things that are easy to miss

- **Identity is permanent.** `key` and `release` (`mp-<chart>`) must not
  change after release: provider-helm reads a renamed release as uninstall +
  install, which deletes the DeviceClass every claim depends on.
  `test_release_names` enforces `mp-<chart>`.
- **`depends_on` resolves across the join** and drives teardown ordering. Any
  chart something depends on sets `wait=True` (`test_dependencies_wait`).
- **Mirror shared pins.** Where a component also exists in a generated half,
  state the same version, so one review moves both. Note it in the module
  docstring.
- **Module docstring** says why the half has the components it has, in the
  same voice as `nebius.py`, `vultr.py`, `civo.py`.
- **GPU metrics.** `modelplane_gpu_*` series come from a DCGM exporter the
  collector scrapes directly. Where the cloud runs one (GKE, Vultr's add-on),
  rely on it. Where your half installs the GPU operator, enable `dcgm` and
  `dcgmExporter` with the shared metrics CSV from
  `generated/aicr/dcgm.py` (`DCGM_METRICS_CSV`) and keep its ServiceMonitor
  off, as `civo.py` does. Where neither exists, install the standalone
  `dcgm-exporter` chart (table above), as `upcloud.py` does. Empty GPU series
  are not an acceptable default; Nebius's gap predates the standalone chart.
- **Load balancer.** `common.py` pins the gateway Service to
  `externalTrafficPolicy: Cluster` because some clouds reject `Local`. If the
  cloud's controller needs Service annotations — UpCloud needs an explicit LB
  name (its default truncates to a colliding prefix) and `frontends` in TCP
  mode (its HTTP default resets the gateway's TLS) — don't edit `common.py`:
  compose-inference-cluster projects them through the ServingStack's
  `spec.gateway.serviceAnnotations`, and `gateway.py` composes a per-gateway
  EnvoyProxy (`gateway-lb-proxy`) that carries them with `{gateway}` replaced
  by the Gateway's name. That EnvoyProxy replaces (not merges with) the
  GatewayClass-level one, so it restates the `externalTrafficPolicy` pin.
  Check that the gateway gets an address in the user's e2e run.
- **Fabric drivers aren't stack components.** The NVIDIA network operator
  (AKS InfiniBand) and the EFA DRA driver (EKS) are composed by the cluster
  function, gated on a pool asking for fabric.
- **Per-cluster state** the half can't know at build time (Civo's single-H100
  NVLink disable) goes through a ServingStack field projected by
  `compose-inference-cluster`, with the transform in the cloud's module and a
  one-line branch in `fn.py`. Only add this when a real pool needs it.

## Files touched

- `functions/compose-serving-stack/function/stacks/clouds/<cloud>.py` (new)
- `functions/compose-serving-stack/function/stacks/__init__.py` (import,
  `_CLOUDS`, the supported-drivers table)
- `functions/compose-serving-stack/function/stacks/components.py` (`Cloud` Literal)
- `apis/servingstacks/definition.yaml` (`spec.cloud` enum)
- `functions/compose-inference-cluster/function/fn.py` (its `Cloud` Literal
  mirrors ServingStack `spec.cloud`)
- `functions/compose-serving-stack/tests/test_fn.py`: `<Cloud>Standard` and
  `<Cloud>Dynamo` in `COMPOSED_RESOURCE_KEYS_CASES` (the key set is the
  identity contract) and per-cloud cases for anything cloud-specific
- `tests/test_stacks.py`: the invariants are parametrized over
  `stacks.clouds()`; add a `SupportedDriversCase`, literal assertions for
  hand-pinned values (UpCloud pins the exporter's CSV, affinity terms and
  `kubernetesDRA` as literals so a drive-by change fails in review), and a
  case table only if you add a transform
- `e2e/clouds/__init__.py` (the leg), `e2e/test_legs.py` (`COMPOSITIONS`,
  unless the cloud taints GPU nodes itself like GKE),
  `.github/workflows/e2e-clouds.yml` (matrix)
