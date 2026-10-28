#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Grade a branch that adds a provisioned InferenceCluster provider.

Deterministic checks for the structural rules in SKILL.md, run against a git
range in a Modelplane checkout. Judgement calls (is the API minimal, are the
comments true) stay with a human or an LLM grader.

    check_provider_change.py --repo PATH --base REF --head REF \
        --cloud civo --cache no [--provider azure] [--json]

Exit code 0 when every check passes, 1 otherwise.
"""

import argparse
import json
import re
import subprocess
import sys


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, check=False).stdout


def show(repo, ref, path):
    out = subprocess.run(["git", "-C", repo, "show", f"{ref}:{path}"], capture_output=True, text=True, check=False)
    return out.stdout if out.returncode == 0 else None


class Grader:
    def __init__(self):
        self.results = []

    def check(self, text, passed, evidence=""):
        self.results.append({"text": text, "passed": bool(passed), "evidence": evidence})


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", required=True)
    p.add_argument("--base", required=True)
    p.add_argument("--head", required=True)
    p.add_argument("--cloud", required=True, help="lowercase slug, e.g. civo")
    p.add_argument("--provider", help="provider slug in package and doc names when it differs, e.g. azure for aks")
    p.add_argument("--cache", choices=["yes", "no"], required=True, help="does the cloud have managed RWX storage")
    p.add_argument("--json", action="store_true")
    a = p.parse_args()

    repo, base, head, c = a.repo, a.base, a.head, a.cloud.lower()
    prov = (a.provider or c).lower()
    g = Grader()
    changed = set(git(repo, "diff", "--name-only", f"{base}..{head}").split())
    xrd_path = f"apis/{c}clusters/definition.yaml"
    xrd = show(repo, head, xrd_path) or ""

    # The Kind's display name, e.g. "Civo" from "kind: CivoCluster".
    m = re.search(r"kind:\s*(\w+)Cluster\b", xrd)
    cloud = m.group(1) if m else c.capitalize()

    # Dependency.
    project = show(repo, head, "crossplane-project.yaml") or ""
    g.check(
        "crossplane-project.yaml depends on the cloud's provider",
        re.search(rf"package:\s*\S*provider-[\w-]*{prov}\S*", project),
        "provider package entry",
    )
    g.check(
        "crossplane-project.yaml packages the new function",
        f"_output/functions/compose-{c}-cluster" in project,
    )
    g.check(
        "provider models regenerated under schemas/python",
        any(f.startswith(f"schemas/python/models/io/upbound/m/{prov}/") for f in changed),
    )
    g.check("schemas/.lock.json updated", "schemas/.lock.json" in changed)

    # Cluster XR and function.
    g.check("XRD exists", bool(xrd), xrd_path)
    g.check("XRD is apiextensions v2 and Namespaced", "apiextensions.crossplane.io/v2" in xrd and "scope: Namespaced" in xrd)
    g.check("XRD declares no shortNames", "shortNames" not in xrd)
    g.check("XRD publishes status.secrets", re.search(r"^\s+secrets:", xrd, re.M))
    has_cache_status = re.search(r"^\s+cache:", xrd, re.M) is not None
    if a.cache == "yes":
        g.check("XRD publishes status.cache (cloud has RWX storage)", has_cache_status)
    else:
        g.check("XRD has no status.cache (cloud has no RWX storage)", not has_cache_status)
    g.check("Composition exists", show(repo, head, f"apis/{c}clusters/composition.yaml") is not None)
    fn_path = f"functions/compose-{c}-cluster/function/fn.py"
    fn = show(repo, head, fn_path) or ""
    g.check("function fn.py exists", bool(fn), fn_path)
    g.check("function tests exist", show(repo, head, f"functions/compose-{c}-cluster/tests/test_fn.py") is not None)
    g.check("function writes the cluster connection secret", "writeConnectionSecretToRef" in fn)
    g.check("function labels pools with modelplane.ai/pool", "modelplane.ai/pool" in fn)
    flake = show(repo, head, "flake.nix") or ""
    g.check("flake.nix lists the function", f'"compose-{c}-cluster"' in flake)
    uvlock = show(repo, head, "uv.lock") or ""
    g.check("uv.lock has the workspace member", f'"compose-{c}-cluster"' in uvlock)
    g.check(
        "own XR model generated",
        show(repo, head, f"schemas/python/models/ai/modelplane/infrastructure/{c}cluster/v1alpha1.py") is not None,
    )

    # InferenceCluster / InferenceClass / ServingStack APIs.
    ic = show(repo, head, "apis/inferenceclusters/definition.yaml") or ""
    g.check("InferenceCluster source enum has the cloud", re.search(rf"enum:\s*\[[^\]]*\b{cloud}\b", ic))
    g.check("InferenceCluster CEL requires the cloud block", f"self.source != '{cloud}' || has(self.{c})" in ic)
    block = re.search(rf"^(\s+){c}:\n((?:\1\s+.*\n)+)", ic, re.M)
    g.check(
        "InferenceCluster cloud block has credentials (parity with other sources)",
        block is not None and "credentials:" in block.group(2),
    )
    icl = show(repo, head, "apis/inferenceclasses/definition.yaml") or ""
    g.check("InferenceClass provider enum has the cloud", re.search(rf"enum:\s*\[[^\]]*\b{cloud}\b", icl))
    g.check("InferenceClass CEL requires the cloud block", f"self.provider != '{cloud}' || has(self.{c})" in icl)
    ss = show(repo, head, "apis/servingstacks/definition.yaml") or ""
    g.check("ServingStack cloud enum has the cloud", re.search(rf"^\s+- {cloud}\s*$", ss, re.M))

    # Dispatch.
    cic = show(repo, head, "functions/compose-inference-cluster/function/fn.py") or ""
    upper = c.upper()
    g.check("dispatch constant", f'CLUSTER_SOURCE_{upper}: Final = "{cloud}"' in cic)
    g.check("activation tuple", f"_ACTIVATE_{upper} = (" in cic)
    g.check("compose_<cloud> method", f"def compose_{c}(" in cic)
    g.check("Usage blocks cluster deletion", f'kind="{cloud}Cluster"' in cic and "usage" in cic.lower())
    cache_map = re.search(r"provisioned = \{(.*?)\}", cic, re.S)
    in_cache_map = cache_map is not None and f"CLUSTER_SOURCE_{upper}" in cache_map.group(1)
    if a.cache == "yes":
        g.check("cache_storage_class maps the cloud", in_cache_map)
    else:
        g.check("cache_storage_class does not map the cloud", not in_cache_map)

    # Serving stack.
    comp = show(repo, head, "functions/compose-serving-stack/function/stacks/components.py") or ""
    g.check("serving-stack Cloud Literal has the cloud", re.search(rf'Cloud = Literal\[[^\]]*"{cloud}"', comp))
    init = show(repo, head, "functions/compose-serving-stack/function/stacks/__init__.py") or ""
    generated = show(repo, head, f"functions/compose-serving-stack/function/stacks/clouds/generated/aicr/{c}.py")
    handwritten = show(repo, head, f"functions/compose-serving-stack/function/stacks/clouds/{c}.py")
    g.check("serving-stack cloud half exists", generated is not None or handwritten is not None)
    g.check("serving-stack registers the half", f'"{cloud}": {c}.COMPONENTS' in init)

    # e2e leg for the serving stack on KWOK-faked GPU nodes.
    legs = show(repo, head, "e2e/clouds/__init__.py")
    if legs is not None:
        g.check("e2e cloud leg exists", f'"{c}": Cloud(' in legs)
        matrix = show(repo, head, ".github/workflows/e2e-clouds.yml") or ""
        g.check("e2e-clouds matrix includes the cloud", re.search(rf"cloud:\s*\[[^\]]*\b{c}\b", matrix))

    # Tests in shared functions.
    cic_tests = show(repo, head, "functions/compose-inference-cluster/tests/test_fn.py") or ""
    # CamelCase names on today's main ("CivoFirstPass"); older trees used sentences ("Civo cluster ready ...").
    g.check("compose-inference-cluster has cases for the cloud", re.search(rf'name="{cloud}(?:[A-Z]| )', cic_tests))

    # Docs.
    providers = show(repo, head, "docs/content/platform/providers.md") or ""
    row = next(
        (ln for ln in providers.splitlines() if ln.startswith("|") and cloud.lower() in ln.split("|")[1].lower()),
        "",
    )
    g.check("providers.md row marks provisioning supported", row.count("✓") >= 2, row.strip())
    for path in (
        f"docs/manifests/concepts/inference-cluster-{c}.yaml",
        f"docs/manifests/getting-started/clusterproviderconfig-{prov}.yaml",
        f"docs/manifests/reference/{c}clusters.yaml",
        f"docs/manifests/getting-started/{c}/platform.yaml",
        f"docs/manifests/getting-started/{c}/inference-gateway.yaml",
        f"docs/manifests/getting-started/{c}/model-deployment.yaml",
    ):
        g.check(f"docs manifest {path.split('/')[-1]}", show(repo, head, path) is not None)
    deploy = show(repo, head, "docs/content/getting-started/deploying-a-model.md") or ""
    g.check("deploying-a-model.md has a tab for the cloud", f"getting-started/{c}/model-deployment.yaml" in deploy)
    icdoc = show(repo, head, "docs/content/platform/inference-cluster.md") or ""
    g.check("inference-cluster.md mentions the cloud", f"`{cloud}`" in icdoc)

    # No self-hosted cache substitute.
    diff = git(repo, "diff", f"{base}..{head}", "--", "apis", "functions")
    added = "\n".join(ln for ln in diff.splitlines() if ln.startswith("+"))
    g.check("no Longhorn or other self-hosted RWX substitute", not re.search(r"longhorn", added, re.I))

    # Commits.
    log = git(repo, "log", "--reverse", "--format=%H%x00%s%x00%b%x1e", f"{base}..{head}")
    commits = [e.strip("\n").split("\x00") for e in log.split("\x1e") if e.strip()]
    prefixed = [s for _, s, _ in commits if re.match(r"^\w+(\([^)]*\))?!?:", s)]
    g.check("commit subjects have no type prefix", not prefixed, "; ".join(prefixed))
    unsigned = [s for _, s, b in commits if "Signed-off-by:" not in b]
    g.check("every commit is signed off", not unsigned, "; ".join(unsigned))
    fixups = [s for _, s, _ in commits if re.search(r"review|wip|fix(ed)? tests|address", s, re.I)]
    g.check("no review/WIP/fixup commits", not fixups, "; ".join(fixups))
    if commits:
        first = set(git(repo, "show", "--name-only", "--format=", commits[0][0]).split())
        stray = sorted(f for f in first if not (f == "crossplane-project.yaml" or f.startswith("schemas/")))
        g.check("first commit only adds the dependency and regenerated schemas", not stray, ", ".join(stray[:5]))

    passed = sum(r["passed"] for r in g.results)
    if a.json:
        print(json.dumps({"expectations": g.results, "passed": passed, "total": len(g.results)}, indent=2))
    else:
        for r in g.results:
            mark = "PASS" if r["passed"] else "FAIL"
            ev = f"  [{r['evidence']}]" if r["evidence"] and not r["passed"] else ""
            print(f"{mark}  {r['text']}{ev}")
        print(f"\n{passed}/{len(g.results)} checks passed")
    return 0 if passed == len(g.results) else 1


if __name__ == "__main__":
    sys.exit(main())
