# Alignment with upbound/skills

This skill is a Modelplane-specific layer over the Upbound control-plane-project
suite (`control-plane-project-charter`, `author-composition`, `author-tests`,
`author-configuration-package`). It does not replace them. The charter itself
says the project's own decisions win (charter §2); this file records which
Modelplane decisions those are, so the two don't read as contradictory.

## Rules taken over unchanged

| upbound/skills rule | Where it shows up here |
|---|---|
| Test first, and RED must fail for the intended reason (charter §3, author-composition rule 3) | Phase 2 and 3 "Test first" |
| Claim only what ran; name the layer reached (charter §4, §8; rule 5) | Phase 5 |
| Check every composed Kind against provider and cloud rules, report the result (charter §6) | Phase 0 item 12, end of Phase 2 |
| Never create cloud infrastructure as a side effect (charter §9; rule 2) | Phase 5 layer 3: the user runs the cloud test |
| References (selectors) before status plumbing (author-composition Phase 3.3) | Phase 2 `fn.py`, dependents gating |
| Composition keys are permanent; a rename is a migration (Phase 3.2) | Phase 2 `fn.py` |
| Conditional resources keep "ready OR exists" (Phase 3.5) | `_dependents_observed()` |
| `writeConnectionSecretToRef` on any resource whose details the function reads; no fallback for a missing detail (charter §5) | Phase 2 `fn.py` |
| Mark composed ProviderConfigs ready explicitly (Phase 5.5) | `mark_readiness()` in every reference function |
| Write the XRD by hand and design it, don't transcribe (charter §5) | Phase 2 "Keep the XR API minimal" |
| v2 XRD (`apiextensions.crossplane.io/v2`, Namespaced, no X prefix, no claims), Composition stays v1 | Phase 2 file list |
| Never ask what the project can tell you; unattended, never block (charter §1, rule 1) | Phase 0 |

## Deliberate departures (Modelplane's own decisions)

| upbound/skills default | Modelplane | Why it wins here |
|---|---|---|
| `up` CLI: `upbound.yaml`, `up project build`, `up test run`, `.up/` models | Crossplane CLI project (`crossplane-project.yaml`), `nix run .#build`, models committed under `schemas/python/` | The repo's build; CONTRIBUTING mandates it |
| `CompositionTest` / `assertResources` (partial-positive) | pytest table of `Case`s comparing the whole `RunFunctionResponse` | CONTRIBUTING Tests section, enforced by `hack/check_function_tests.py`. Whole-response comparison already catches surplus resources, which `assertResources` doesn't |
| Gate: `verify-configuration` | `nix flake check`; local control plane `nix run .#run`; e2e `nix run .#e2e -- --verify` | The project's gate script wins (charter §2) |
| `providerConfigRef` omitted when `ClusterProviderConfig/default` is right | Always set explicitly from `spec.credentials` | The XR API exposes credentials (charter §5 allows this when the API exposes it) |
| `managementPolicies` unset | Set on in-cluster Helm releases/Objects (orphan, no `Delete`) and on autoscaled pools (no `LateInitialize`, `nodeCount` via `initProvider`) | Both are "another policy" cases the charter permits (v2-resources.md); the reasons are in each function's comments |
| Conventional Commits (`fix: …`) in upbound/skills itself | Imperative subject, no type prefix | Modelplane CONTRIBUTING. upbound/skills' own commit style applies only to that repo |
| Model co-author trailers rejected (upbound/skills) | Not regulated by Modelplane CONTRIBUTING; follow the user's instruction | Different repos, different rules |

