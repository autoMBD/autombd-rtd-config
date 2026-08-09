---
name: agent-workflow
description: Enforce the closed P0 agent workflow contract, identity bindings, lane manifests, and final clearance before governed changes advance.
---

# Agent Workflow

Use this Skill for work governed by
`agent-discipline/workflow-contract.json`. That file is the sole machine-readable
authority for classes, flags, route order, checkpoints, object fields,
requirements, verdicts, dispositions, and role permissions. Do not reproduce or
extend those domains in prompts, records, or prose.

## Required sequence

1. Load and validate `agent-discipline/workflow-contract.json` before work starts.
2. Follow its `strict_route` in the stored order. Record the route exactly; do
   not infer or shorten it from an issue class or impact flag.
3. Stop at unavailable preflight evidence. Keep execution status and blocker
   evidence consistent with the validated record.
4. Keep Test and Implementation lanes on the approved Base. A Worker reads only
   the approved contract/design and writes implementation plus Worker-owned
   generality tests; it never reads owner tests.
5. Require immutable Human Review 1 evidence bound to the authorized reviewer
   and full Test commit before implementation advances.
6. Assemble a Candidate only from the recorded Test and Implementation lane
   identities. The Tester owns the functional gate and treats that Candidate as
   read-only; it never writes production.
7. Run the Reviewer only after Tester PASS on the same current Candidate. The
   Reviewer remains read-only except for the append-only lessons log.
8. Keep verdicts separate from findings. The Orchestrator alone assigns finding
   dispositions under the contract rules.
9. Bind the draft PR and final Human Review to the same current Candidate.
10. Before completion, validate both lane manifests and run bootstrap clearance
    against the Candidate commit tree and every deployment path.

## Validator

For a workflow record, run:

```console
python agent-discipline/skills/agent-workflow/scripts/workflow_gate.py validate --contract agent-discipline/workflow-contract.json --record <record.json>
```

Exit `0` means the closed contract and record validate. Exit `1` means contract
or record evidence is invalid. Exit `2` means the command input could not be
read or decoded. Validation is a thin evidence gate, not a workflow engine: it
does not perform routing, assign dispositions, assemble Candidates, or mutate
repository state.
