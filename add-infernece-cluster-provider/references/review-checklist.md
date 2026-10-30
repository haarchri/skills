# Review checklist for a new InferenceCluster provider

Each item is a rule the existing providers follow or review has asked for.
Check each before opening the PR.

## API surface
- [ ] XRD fields are only what users must choose. Operator-owned values (CNI,
      system pool size, chart pins, add-on removal) are constants in `fn.py`.
- [ ] No `shortNames` on the new XRD.
- [ ] `spec.cluster.<cloud>` on InferenceCluster has a `credentials` block
      like `aks`, `eks`, `civo`, and compose-inference-cluster propagates it.
- [ ] Default Kubernetes version is the newest the cloud offers, or left
      unset when the cloud needs exact build strings.
- [ ] CEL rules: `source`/`provider` discriminator requires the block; GPU
      role requires `gpu`; `minNodeCount` requires `maxNodeCount`; pool
      `name != 'system'` (both the InferenceCluster and the `<Cloud>Cluster`
      XRD — `system` is the injected system pool); the class's `accelerator`
      is required when a device claims a non-`dra.cpu` DRA driver and
      forbidden when none does.
- [ ] `diskSizeGb` on the pool and the class block when the cloud unbundles
      disks from the plan, and the default disk fits an inference serving
      image.
- [ ] Breaking changes to shared types (e.g. `fabric` changing from a
      string to an object) are called out in the PR.

## Function code
- [ ] Module docstring and comments describe what the code actually does and
      the real reason. No stale claims about labels nobody reads.
- [ ] Implicit fallbacks (e.g. credentials taken from the `default`
      ClusterProviderConfig) emit `response.warning`.
- [ ] Nothing composed that the cloud already provisions on the cluster.
- [ ] Children reference the cluster by selector where the provider allows
      it; Ready-gating only where a child needs an observed value, and then
      gated children survive a Ready regression (`_dependents_observed`).
- [ ] The cluster MR has `writeConnectionSecretToRef`; no missing connection
      detail falls back to a default.
- [ ] Every composed Kind checked against the provider models' conditional
      rules and the cloud's API rules; the result is in the report.
- [ ] In-cluster resources are orphan-managed (no `Delete`), and an observed
      orphan-managed release survives removal of the spec that asked for it
      (the cluster-autoscaler stays composed with an empty group list when
      `spec.autoscaler` goes away, or the orphan fights Crossplane's
      `nodeCount`).
- [ ] Autoscaled pools don't late-initialize `nodeCount`.
- [ ] GPU pools carry `modelplane.ai/pool` and the GPU taint the serving
      stack tolerates (unless the cloud adds it itself, like GKE); the DRA
      driver is the only GPU allocator (device plugin disabled or labelled
      off). CPU pools carry the `modelplane.ai/cpu` label and taint.
- [ ] A pool's role comes from the class's `accelerator` presence
      (GPU vs CPU) in `compose_<cloud>_cluster()`, and the cloud is in
      compose-inference-cluster's `_SUPPORTED` drivers map.
- [ ] Optional status fields are assigned only when observed (an explicit
      `None` is a null tombstone under `exclude_unset`); identifiers other
      functions need (e.g. a cluster UUID for LB names) are published on the
      cluster XR's status.
- [ ] If the cloud's LBs need Service annotations (naming, TCP mode), the
      `<cloud>_gateway_service_annotations()` helper sets them on the
      ServingStack spec and the InferenceCluster status, published before
      the gateway address exists.
- [ ] Activation tuple lists every MR CRD the function composes.

## Optional capabilities
- [ ] No ModelCache unless the cloud has managed RWX storage usable on GPU
      nodes. When absent: no `status.cache`, no StorageClass, cloud named in
      the "absent" docstring and the docs' "none" bullet with the reason.
- [ ] No self-hosted substitute (Longhorn etc.) without a separate design and
      a measured performance bar.
- [ ] Fabric mapped only where it exists.

## Serving stack
- [ ] Hand-written half in `stacks/clouds/<cloud>.py`; `common.py`, stack files and `generated/` untouched.
- [ ] NFD worker tolerates the GPU taint (or the cloud's own NFD is relied on, never two).
- [ ] `nvidiaDriverRoot` matches where the driver lives; DRA driver `depends_on` the operator when the half installs it.
- [ ] Release names `mp-<chart>`, keys stable, shared pins mirrored from the other halves.
- [ ] A DCGM exporter runs on GPU nodes: the cloud's, the operator's with
      the shared CSV and no ServiceMonitor, or the standalone chart (shared
      CSV in `customMetrics`, `kubernetesDRA` on, GPU-taint toleration, the
      DRA kubelet plugin's affinity terms). Empty `modelplane_gpu_*` series
      are not an acceptable default.
- [ ] GPU-only charts tagged `dra_drivers=["gpu.nvidia.com"]`, the half
      declares `EXTERNAL_DRIVERS`, the cloud is in the supported-drivers
      table, and `test_stacks.py` has a `SupportedDriversCase` plus literal
      assertions for hand-pinned values.
- [ ] e2e leg added (`e2e/clouds/__init__.py` with `cpu_labels` and
      `dra_drivers`, `e2e/test_legs.py`, `e2e-clouds.yml` matrix, the
      `--cloud` list in `e2e/README.md`) and `nix run .#e2e -- --cloud
      <cloud>` passes. Fake-node OS release labels copied from a live node.
- [ ] `<Cloud>Standard`/`<Cloud>Dynamo` key-set cases added.

## Docs
- [ ] providers.md row links the provider actually used (Upbound
      Marketplace package / upbound repo), not a different vendor repo.
- [ ] Every manifest under `docs/manifests/` validates (`nix flake check`).
- [ ] `getting-started/<cloud>/model-deployment.yaml` and a deploying-a-model.md tab exist (Vultr and Civo lack them).
- [ ] Manifest comments re-read after review changes (the Civo ClusterProviderConfig comment is stale).
- [ ] Local `examples/<cloud>/` kit applies end to end; its manifests match the docs copies.
- [ ] New terms added to the Vale accept list.
- [ ] Cache gap and other limitations stated in inference-cluster.md.

## Process
- [ ] Issue exists and PR says `Fixes #N.`
- [ ] Commits are logical layers (dependency+schemas, cluster XR+function,
      InferenceCluster/serving-stack wiring, docs), imperative subjects, no
      `feat:` prefixes, bodies lead with the problem, signed off.
- [ ] Review fixes folded into their commits, not left as
      "address review comments".
- [ ] Rebased onto current main, and the Phase 3 `git grep` parity sweep
      re-run after the rebase — platform PRs merging mid-review (CPU pools,
      new common components) widen what the new cloud must cover.
- [ ] Each new test case was seen failing for the intended reason before
      the code that makes it pass.
- [ ] `nix run .#fix` and `nix flake check` pass, and the report names the
      layer reached (flake check / local control plane / real cloud).
- [ ] Validation section reports only what the user really ran.
- [ ] Branch is on the user's fork.
