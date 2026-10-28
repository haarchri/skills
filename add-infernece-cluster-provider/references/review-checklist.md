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
      role requires `gpu`; `minNodeCount` requires `maxNodeCount`.
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
- [ ] In-cluster resources are orphan-managed (no `Delete`).
- [ ] Autoscaled pools don't late-initialize `nodeCount`.
- [ ] GPU pools carry `modelplane.ai/pool` and the GPU taint the serving
      stack tolerates (unless the cloud adds it itself, like GKE); the DRA
      driver is the only GPU allocator (device plugin disabled or labelled
      off).
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
- [ ] A DCGM exporter runs on GPU nodes (the cloud's, or the operator's with the shared CSV and no ServiceMonitor), or the gap is stated.
- [ ] e2e leg added (`e2e/clouds/__init__.py`, `e2e/test_legs.py`, `e2e-clouds.yml` matrix) and `nix run .#e2e -- --cloud <cloud>` passes.
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
- [ ] Each new test case was seen failing for the intended reason before
      the code that makes it pass.
- [ ] `nix run .#fix` and `nix flake check` pass, and the report names the
      layer reached (flake check / local control plane / real cloud).
- [ ] Validation section reports only what the user really ran.
- [ ] Branch is on the user's fork.
