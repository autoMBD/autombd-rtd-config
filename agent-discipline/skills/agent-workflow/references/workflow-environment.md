# Workflow Environment Capabilities

| Field | Value |
| --- | --- |
| Version | 0.1.0 |
| Date | 2026-09-11 |
| Author | autoMBD <tkung.lqk@foxmail.com> |
| Description | Portable capability preflight, derived initialization and source/evidence hygiene. |

## Responsibility and limits

The public entry point is
[workflow_environment.py](../scripts/workflow_environment.py). It supplies
capability checks to callers; it does not dispatch Agents, execute transitions,
approve Test, assemble Candidates, authenticate Human decisions or decide
functional acceptance. The existing [handoff protocol](structured-handoffs.md),
pinned declaration, transition reducer and
[evidence verifier](workflow-evidence.md) retain their authority. The canonical
JSON encoder is shared with the structured handoff implementation.

| Boundary | Evidence | Limit |
| --- | --- | --- |
| Checkout separation | Canonical Git top level and exact HEAD; worktree/clone topology | Does not isolate private refs or OS reads |
| Git ref/object separation | Independent Git store, one branch, no remotes, alternates, shared objects or disconnected residual objects | Does not deny reads outside the checkout |
| Input isolation | Trusted adapter evidence from actual applicable allowed/denied non-secret canary operations | A directory name, permission label or command exit code is insufficient |

Inspection always reports os_read_isolated=false. An adapter may separately
supply input-isolation only after checking its real execution context. The
evaluator cannot authenticate OS restrictions from a boolean or hash. Callers
retain the underlying scoped evidence and refresh it when applicability changes.
An independent clone or embedded subagent does not become a true black-box
Agent merely through a name or role instruction.

## Checkout API

~~~python
inspect_checkout(root: Path, *, expected_head: str) -> dict

create_isolated_checkout(
    source_root: Path, target_root: Path, *,
    allowed_target_base: Path, branch: str, expected_source_head: str,
) -> dict
~~~

Roots and allowed bases are explicit absolute paths. Traversal, symlink or
junction ancestors, source=target, targets outside the base, existing targets
and invalid/reserved branch names reject before creation. The source must be a
real Git top level at the requested full 40-digit SHA.

Creation initializes a new repository and fetches only the exact requested
shallow commit, then creates the requested local branch. It does not copy a
shared object directory, install a source remote, or retain unrelated refs,
tags and branch objects. Inspection returns root, head, git_dir, common_dir,
checkout_kind, shared_objects, ref_isolated and os_read_isolated.

The source is never reset or switched. An execution failure after creation may
leave a partial target for inspection; there is no automatic destructive
rollback. Callers serialize mutations. These checks do not claim an OS
transaction against concurrent filesystem changes.

## Role and operation capabilities

~~~python
required_capabilities(
    role: str, *, requires_blackbox: bool = False,
    requires_s32ds: bool = False,
) -> tuple[str, ...]
~~~

| Role | Baseline |
| --- | --- |
| Orchestrator | filesystem-read, filesystem-write, git |
| Worker | filesystem-read, filesystem-write, git |
| Tester | filesystem-read, filesystem-write, git |
| Explorer | filesystem-read |
| Reviewer | filesystem-read |

Add github only for a selected GitHub operation. requires_blackbox adds
agent-cli and blackbox; requires_s32ds adds s32ds. The explicit request list
can add selected operations. A capability is not permission to violate role
ownership. Profiles do not require every vendor, all RTD-MEX cases, KPI or
S32DS when the selected functional checks do not use them.

### Version 1 preflight wire

evaluate_preflight(request, observations) accepts closed records. Unknown
members, duplicate choices, invalid versions, malformed hashes and inconsistent
identities reject.

The request contains:

- version: integer 1.
- role: orchestrator, explorer, worker, tester or reviewer.
- platform: codex, claude or opencode.
- bindings: the source identity below.
- required_capabilities: unique supported IDs.
- isolation: checkout or input.

Bindings contain task_run, full 40-digit governor, workflow_blob and head,
64-digit contract_sha256, canonical absolute checkout_root, and
candidate_sha256 (null or the exact Candidate HEAD). Digests are lowercase.
Supported capability IDs are filesystem-read, filesystem-write, git, github,
agent-cli, blackbox, s32ds and input-isolation.

Observations contain version=1, identical bindings, the inspection result in
checkout, and a capabilities list. Each capability record has this shape:

~~~json
{
  "id": "github",
  "context": "connector",
  "status": "available",
  "approved": true,
  "mode": "connector",
  "evidence_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
}
~~~

Context is host, sandbox or connector; status is available, unavailable or
unknown; approved is boolean. Mode identifies the concrete evidence origin.
Duplicate ID/context/mode observations are ambiguous.

For Codex GitHub access, an approved available connector record wins over
approved host/host-cli. Sandbox auth failure does not erase host availability.
The evaluator never copies keyring secrets or starts authentication/escalation.

The required union includes role baseline, declared capabilities and
input-isolation when requested. Each selected record must be available,
approved and bound to this request. Missing optional capabilities are ignored.
Unusable mandatory evidence produces BLOCKED with capability diagnostics;
a complete set produces READY. Reports include request/binding digests,
selected observations, diagnostics and integrity data. They are source-bound
data, not authenticated receipts or functional verdicts.

Immediately before proceeding, a caller must invoke:

~~~python
require_preflight(
    report, expected_request_sha256=request_digest,
    current_bindings=current_bindings,
)
~~~

This rejects BLOCKED or altered reports, missing selections, wrong request
digests, stale bindings and a real checkout whose HEAD changed. It does not
launch the operation. Stored hashes cannot re-probe a remote service; a trusted
adapter remains responsible for current, applicable observations.

### Bounded noninteractive probes

~~~python
probe_command(
    argv: Sequence[str], cwd: Path, *, approved: bool,
    context: str, timeout_seconds: int = 60,
) -> dict
~~~

Use explicit preflight-owned argv and a pre-authorized context. Execution has
no shell and stdin is closed. Batch commands require an explicit trusted
interpreter. Invalid/unapproved input rejects before spawning.
The deadline limits one deterministic child command, never an Agent session.

The versioned result contains availability, context, cwd, command digest,
exit code, timeout state and hashes of raw stdout/stderr bytes. It never
returns or persists raw output. Exit zero establishes command evidence only.
No installation scan, permission broadening, credential provisioning or
interactive fallback follows failure. An input-isolation adapter must also
demonstrate actual applicable allow/deny canary behavior; a generic successful
probe cannot replace that evidence.

## First initialization and derived hydration

The existing GUI-first collector and deployer remain unchanged. A clean clone
or reset uses the original initialization process. Do not reopen the GUI
inside an automated Loop. Explicit derived hydration uses
[init_agent_env_hydrate.py](../../initialize-agent-discipline/scripts/init_agent_env_hydrate.py):

~~~python
capture_initialization(
    source_root: Path, input_path: Path, *, expected_input_sha256: str,
) -> dict

hydrate_checkout(
    source_root: Path, target_root: Path, *,
    initialization: dict, expected_initialization_sha256: str,
    allowed_target_base: Path, platforms: Sequence[str],
    expected_target_head: str,
) -> dict
~~~

Capture is read-only. The supplied initialization input must match its trusted
raw-byte digest and pass the existing collector/deployer validators. Capture
verifies selected platforms, generated role bytes, actual Skill links and
canonical/approved external sources, and reusable dependency-cache validity.
Git inspection disables optional index refresh writes. Capture neither infers
Human selections nor independently authenticates their approval.

The returned snapshot is opaque versioned JSON. Hash its canonical encoding
(sorted compact keys, UTF-8, ensure_ascii=False, final LF) and pass that digest
with the unedited snapshot. It binds actual source Git/assets, raw input,
cache and deployed bytes, and selected Skill sources. Source or external
Skill changes, including newline-only changes, invalidate the snapshot.

A qualified target is an existing exact-HEAD checkout strictly under the
explicit derived base, with the captured source commit in its actual lineage
and matching canonical discipline content. It can be a linked worktree or an
independent checkout; neither is labelled OS read isolation. An unrelated
first-time repository fails qualification. A qualified derived checkout can
legitimately have no ignored state yet.

All input/source/platform/path/link/cache/output checks precede the first
target mutation. Missing/stale initialization, wrong identities, unapproved
platforms, source=target, escaping paths and conflicting existing outputs
reject without mkdir, partial deployment or cache writes. Only a subset of
the source's selected platforms may be requested.

Canonical Skill links use target-local sources; external links use the exact
approved external sources. Actual generated bytes are verified and a compatible
existing cache is preserved. HYDRATED reports selected platforms and actual
target-relative changed_paths; a repeated call returns an empty change list.
Original reset intent is never replayed. No implicit legacy cleanup/reset or
GUI is performed.

Git may materialize LF text as CRLF. Only that content-equivalent conversion
is allowed when source and target have the same Git asset tree and no Git
content diff. Source capture remains raw-byte bound, as do external Skills
and binary assets. Actual target asset/generated-file digests are retained;
normalized comparison hashes are never represented as raw SHA-256.
Changed content, Git trees or stale generated outputs still reject.

Runtime I/O/link-creation failure after validation can leave partial new
outputs. Preserve and inspect them before retrying; no reset is silently
performed. The separate initializer role-description assertion drift is not
changed or relabelled by this implementation.

## Current contributor as black-box actor

~~~python
select_agent(
    current_platform: str | None, available_agents: Sequence[str], *,
    explicit_agent: str | None = None,
) -> str
~~~

An explicit supported available actor wins; otherwise the available current
contributor is selected. Unknown or unavailable selections fail explicitly.
The portable selector does not inspect history or choose a default vendor.

The harness extends resolve_agent(cli_agent, cache_path, *,
current_platform=None, available_agents=None) and adds --current-platform.
Callers may provide verified availability; otherwise PATH alone is inspected.
Explicit selections persist preference with source=flag. Current-platform
selection reports current-platform and overrides another contributor's cache.
RTD_CURRENT_PLATFORM is the explicit environment signal; unambiguous native
platform signals can also identify the contributor. Without a signal, exactly
one available installed adapter may be selected with source=available, or
cache when that same sole actor was cached. Cache never resolves ambiguous
contributors. PATH discovery does not establish authentication.

The existing RunResult/AgentAdapter registry includes a minimal Claude print
adapter. It starts a fresh staged session with bare discovery, JSON output,
noninteractive permission handling and no session persistence. Model is
explicit; the one-shot JSON protocol supplies no canonical KPI timestamps.
The flags are grounded in the
[official Claude CLI reference](https://code.claude.com/docs/en/cli-reference).
Synthetic argv/result checks are not a live Agent or vendor pass.

Selected E2E still uses an independent CLI receiving only deployed runtime
Skill, staged fixture and prompt. Repository/owner-Test source and inherited
embedded-agent context are not authorized inputs. Staging/CLI flags alone do
not prove OS read denial: applicable capability evidence must cover the chosen
execution context. Independent S32DS recheck still requires exit 0 and zero
SEVERE [TOOL] resource problems. Polling, interruption, timeout redesign and
process-tree lifecycle remain separate work.

## Source/evidence hygiene and cleanup

~~~python
snapshot_evidence(root, paths, *, bindings) -> dict
verify_evidence(root, snapshot, *, bindings, allowed_new_paths=()) -> None
cleanup_paths(root, paths, *, allowed_base, protected_paths=(), dry_run=True) -> dict
~~~

Snapshots bind actual HEAD/tree/index/source status and tracked/untracked
non-ignored source bytes, plus explicitly listed evidence. An ignored evidence
file establishes its parent directory as the recorded task evidence scope;
a source file remains individually scoped. New files within that scope must
be explicitly allowlisted and ignored. A trailing-slash allowlist allows new
descendants, never changes to bound bytes. Other ignored locations remain the
caller's responsibility outside this snapshot's evidence scope.

Changed bindings, source, referenced bytes, deleted evidence or unapproved
new evidence invalidate the prior result. An allowlist cannot authorize
modified Candidate source, cases, manifests or frozen approval. Snapshots are
opaque evidence, not read locks or substitutes for read-only acceptance.

Cleanup accepts named paths strictly below a declared current-run base under
tests/.tmp/ or .agent-state/agent-loop/. It validates the complete request
before deletion, rejects overlap, source/Git roots, nested repositories,
escaping ancestors and protected evidence, and defaults to PLANNED.
A valid dry_run=False request returns CLEANED. A permitted leaf symlink/junction
is unlinked itself, never its destination. No branch/process cleanup or
automatic age-based deletion is implemented.

## JSON CLI and errors

Examples use explicit caller-owned inputs and stdout:

~~~console
python agent-discipline/skills/agent-workflow/scripts/workflow_environment.py inspect-checkout --root <absolute-checkout> --expected-head <40-hex>
python agent-discipline/skills/agent-workflow/scripts/workflow_environment.py preflight --request request.json --observations observations.json
python agent-discipline/skills/agent-workflow/scripts/workflow_environment.py verify-preflight --report report.json --expected-request-sha256 <64-hex> --bindings bindings.json
python agent-discipline/skills/initialize-agent-discipline/scripts/init_agent_env_hydrate.py capture --source-root <absolute-source> --input <absolute-input> --expected-input-sha256 <64-hex>
python agent-discipline/skills/initialize-agent-discipline/scripts/init_agent_env_hydrate.py hydrate --source-root <absolute-source> --target-root <absolute-target> --initialization snapshot.json --expected-initialization-sha256 <64-hex> --allowed-target-base <absolute-derived-base> --platform codex --expected-target-head <40-hex>
~~~

Success/READY returns exit 0, rejected/BLOCKED operations return exit 1, and
unreadable or malformed input returns exit 2. A well-formed digest mismatch
is rejected with exit 1 and code INVALID_INPUT; that code alone does not
determine CLI exit status. Input read/JSON parse/shape or value-format errors
return exit 2. Errors are safe versioned JSON with status, code and message.

Stable codes are INVALID_INPUT, PATH_BOUNDARY, INITIALIZATION_UNAVAILABLE,
PLATFORM_NOT_APPROVED, STALE_IDENTITY and CAPABILITY_UNAVAILABLE.
Commands do not write inputs or silently persist outputs. Caller redirection
owns publication. Digests are not Human authority or functional PASS.

## Development verification boundary

Worker generality fixtures exercise the public surface independently of owner
Test. Tester derives its functional Impact Set and readable requirements/cases
from K, freezes reviewed scope at Human Gate 1, and tests the exact read-only
Candidate. Reviewer performs the existing single terminal review.

This unfinished feature is not its own development dispatch prerequisite.
Existing role boundaries, isolated worktrees, selective checked handoffs and
compensating checks remain honestly labelled during development. No extra
lifecycle, Human approval or KPI gate is introduced.

| Date | Version | Description |
| --- | --- | --- |
| 2026-09-11 | 0.1.0 | Added portable capability, checkout, hydration, actor and evidence interfaces with explicit evidence limits. |
