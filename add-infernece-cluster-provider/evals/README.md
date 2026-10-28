# Evals

`evals.json` follows the skill-creator format (prompt, expected output,
assertions). The provider in evals 1–4 is fictional or a replay with the facts
spelled out, so a correct answer follows from the skill's decision tree, not
from what a model remembers about a cloud.

- **1–3 and 7, plan only.** 7 tests the serving-stack half. Cheap; run them on every change to SKILL.md. Grade the
  assertions with an LLM grader or by hand.
- **4, full implementation.** Replays Civo (#475) from the commit before it
  landed. Run on a worktree, never on main. Grade with:

  ```bash
  python3 evals/check_provider_change.py --repo <worktree> \
      --base 3975e78^ --head HEAD --cloud civo --cache no
  nix flake check
  ```

  plus the judgement assertions in `evals.json`.
- **5–6, triggering.** One phrasing that should load the skill, one change to
  an existing provider that shouldn't.

Run each eval with and without the skill; an assertion that passes either way
isn't telling you anything.

## The grader against real history

`check_provider_change.py` checks the structural rules (files, enums, CEL,
credentials parity, cache present only when the cloud has RWX, no Longhorn,
commit hygiene). Controls run against the merged PRs:

| Range | Result | Failures |
|---|---|---|
| Civo #475 | 42/46 | no `getting-started/civo/model-deployment.yaml` and no Civo tab in deploying-a-model.md (a real docs gap); `feat(...)` subject prefixes and an "address review comments" commit, both against CONTRIBUTING |
| Civo #475 with shortNames added, credentials block removed, Longhorn mentioned | 39/46 | all three mutations caught |
| AKS #346 (`--provider azure`) | 33/46 | mostly structure added to the repo after July (activation tuples, ServingStack `cloud`, InferenceCluster credentials) |

Point it at a range based on current main; on older bases the checks for
later additions fail by design.
