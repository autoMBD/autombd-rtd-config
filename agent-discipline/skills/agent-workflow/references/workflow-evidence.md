# Read-only Workflow Evidence Verification

| Field | Value |
| --- | --- |
| Version | 0.1.2 |
| Date | 2026-09-10 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Real-source and exact remote proof over the existing accepted workflow state. |

## Boundary

The verifier validates the current State and its complete referenced evidence.
It does not consume an event, change source/counters, assemble a Candidate,
write receipts, fetch Git objects, create/approve/merge a PR, dispatch an Agent
or implement a second workflow ledger. Use the existing [transition engine](workflow-transitions.md)
and [handoff protocol](structured-handoffs.md) for their respective boundaries.

Existing State/Context wire and W3/W4 repair semantics are reused. W4 adds the
separate Reviewer lessons Tip under its explicitly pinned capability. The schema
contains only Authority/Result transport and their shared scalar/reference
definitions, not a duplicate State or Context.

## Python and CLI

Place the scripts directory on the caller's module search path:

~~~python
from workflow_evidence import verify_evidence, WorkflowEvidenceError

result = verify_evidence(
    state,
    context=context,
    repository_root=absolute_repository_path,
    authority=authority,
    github_get=trusted_read_only_get,
    command_timeout_seconds=15,
)
~~~

The root is an explicit absolute path. Inputs remain unchanged. The result is
detached; repeated verification of identical inputs and evidence is canonical
and deterministic.

~~~console
python agent-discipline/skills/agent-workflow/scripts/workflow_evidence.py verify --state state.json --context context.json --authority authority.json --repository-root ABSOLUTE_PATH --github-cli gh --command-timeout-seconds 15
~~~

Every deterministic Git/gh operation has the configured positive finite deadline.
This is not an Agent lifetime. The adapter uses argv without a shell, authenticated
`gh api --method GET --hostname github.com`, and only verifier-built endpoints.
No login, token extraction, retries, background work or remote write occurs.
An unowned remote stage does not invoke gh.

## Trusted Authority transport

Authority has exactly:

~~~json
{"schema_version":"1.0","authorized_actors":["repository-owner"],"base_ref":"master","packets":[{"decision_artifact_id":"test-decision","packet_comment_id":12345}]}
~~~

Authorized actors must be nonempty, unique, nonblank logins. Base is a nonblank
branch name. Packet nominations uniquely name decision artifact IDs and positive
comment IDs. Authorization policy belongs to the trusted caller, never a comment.

The injected `github_get(endpoint)` returns exactly
`{"status": integer_http_status, "body": JSON_object}`. It is a trusted authenticated
GET transport, not a collection of unauthenticated snapshots. The verifier builds
`/repos/owner/name/issues/comments/id` and `/repos/owner/name/pulls/number`;
payload URLs never select arbitrary hosts/endpoints.

For every consumed Human decision, metadata replacements resolve to the original
vote. The exact decision and nominated packet must be current top-level issue
comments in the same repository/issue. Required IDs/URLs, User login/type, raw
captured REST fields, body/times and deletion/reply status are checked. The decision
must be unedited and created strictly after its packet. Extra official response
fields are allowed; absent `in_reply_to_id` is valid, non-null is not.

Approved commands are entire exact `/approve-test <full-T>` or
`/approve-candidate <full-delivery-head>`. Request changes is the exact
`/request-test-changes <full-T> <reason>` or
`/request-candidate-changes <full-delivery-head> <reason>`, with a nonempty reason equal to
the recorded reason. Approval is not whitespace-normalized. STOP and the manual
human-command route remain preserved authority but return AUTHORITY_UNVERIFIABLE
in this remote adapter; they do not become automatic VERIFIED. The command name
is unchanged: delivery head means L under W4 and C under W2/W3. TEST approval
continues to bind original T; W1 remains the separate legacy interface.

## Ordered proof and source continuity

Evaluation is input legality, existing ordered state invariants, complete local
artifact/receipt/attachment closure, real Git, Human evidence, final PR evidence,
then result validation. Existing reducer invariant errors retain their semantics.

Each consumed artifact needs a supplied exact CHECKED receipt. Matching receipts
are considered in canonical full-reference order; the first fully valid receipt
is used. Matching includes input path/ID/digest, task/G/K, consumer and visibility,
canonical receipt digest, exit zero, no violations and available evidence.
Recursive receipt attempts are isolated: a rejected attempt contributes no
artifacts, attachment cache entries or deferred source checks to a later choice.
No matching receipt is MISSING_EVIDENCE; candidates but none valid is
INVALID_EVIDENCE. State does not retain event.checked: this selection does not
prove it was the original execution receipt or that a guard actually ran.

The full local closure remains raw-byte bound, including rejected originals and
W3/W4 inline attachment snapshots. LocalRules preserve readiness, manifest,
coverage-join, correction, repair, execution and terminal rules. Incomplete
catalog evidence cannot silently defer proof into VERIFIED.

Every source Tip must match actual Git commit/tree/ordered-parent objects.
Commit structure is read as bytes; only tree/parent object IDs are decoded as
ASCII. Unrelated author, committer and message encodings do not affect this proof.
G's exact workflow blob, schema and registry must agree with the supplied
protocol. For each Candidate, real parents are exactly executable Test first
and Implementation second. Both descend from G, and their complete merge-base set
is exactly G. Leaf-tree changes include path, mode, object type and object ID,
including deletions. Disjoint lane ownership agrees with CoverageJoin; Candidate
content is the exact direct union over G, without merge-only or omitted edits.
Verification never writes Git objects or invokes a merge/checkout.

The mechanical Candidate-content exclusions apply only to paths changed from G:
`.agent-state` and descendants, `tests/.tmp` and descendants,
`agent-discipline/agent-lessons-learned.md`, and exact referenced command-result,
lesson or disclosure-review attachment paths. Ordinary test/fixture/reference
names are legal. Inherited unchanged G content is not retroactively rejected.
Unmarked semantic contamination remains Orchestrator inspection. Under W4,
these exclusions still protect C and its two-lane union; they do not prohibit
the separately proved C→L lessons append. L must have sole parent C and exactly
one changed regular-file path, `agent-discipline/agent-lessons-learned.md`, with
unchanged mode/type and all old bytes retained plus a nonempty append. The
complete L lessons blob must match the report's raw lesson evidence digest.
This verifies source preservation, not a new execution of L.

Completed same-lane READY Implementation determines functional correction count.
Candidate index is independent: corrected READY may be one ahead before assembly.
Metadata/support repairs and invalid-run retries do not consume/reset corrections.
Approved Test, latest registered effective Test and actual current Candidate
first-parent executed Test stay distinct. Correction mapping must cover every
Implementation finding with matching public requirement and production location.
Natural-language diagnostic sufficiency and disclosure safety remain semantic
review, never a field-checker's claim.

## Finalization and result

A successful proposal requires the same current Candidate's Tester PASS and
Reviewer APPROVED, with truthful preserved source and terminal binding.
OPEN_SUCCESS_PR with null PR verifies the local record but owns no remote PR
proof: finalization is NOT_APPLICABLE. A present open PR must target the authorized
base branch at G and the exact delivery head: L under W4, C under W2/W3. The
accepted_candidate field continues to identify C. This proves proposal
availability, not final Human approval; the original Tester and Reviewer
technical evidence continues to bind C.

MERGED additionally needs exact final approval and the matching local merge
object. It is either the delivery head itself (fast-forward) or a two-parent
`[G, delivery head]` merge with delivery-head-identical tree. Squash/rebase/extra edits
are rejected. Historical G is established by actual merge ancestry, not mutable
post-merge PR base.sha. Failure stays failure with null accepted Candidate/PR and
preserved Implementation, never a success conversion. W4 failure with C retains
the separately checked L; before C exists the report has explicit null
lesson_commit and raw lesson evidence. Neither case manufactures accepted C
or a success PR. No retest follows solely from the verified lessons append.

Result contains exactly version/status, task/G/K, input digests, approved/
effective/executed Test SHAs, Implementation/Candidate SHA, Candidate index,
functional correction count, accepted Candidate, terminal disposition, four
stage checks, and endpoint-sorted remote body digests. Stage values are PASS or
NOT_APPLICABLE; missing/unavailable owned evidence never becomes NOT_APPLICABLE.
No raw Human text, cases or private diagnostics are returned.

Errors expose `WorkflowEvidenceError.code/pointer/message` and `as_dict()` as
`{"error":{"code":"...","pointer":"...","message":"..."}}`, without private content
or traceback. Canonical digests and successful stdout use sorted compact UTF-8
JSON plus LF.

| CLI result | Exit | Stream |
| --- | --- | --- |
| VERIFIED | 0 | Canonical result on stdout, empty stderr |
| Semantic/binding rejection | 1 | Safe JSON error on stderr, empty stdout |
| Input/file/usage/internal or remote unavailable | 2 | Safe JSON error on stderr, empty stdout |
| Command timeout | 124 | COMMAND_TIMEOUT on stderr, empty stdout |
| Help | 0 | Normal help on stdout |

Missing local files/objects and owned remote 404 are MISSING_EVIDENCE.
Present contradictory evidence is INVALID_EVIDENCE. Authentication/rate-limit/
network/provider failure is REMOTE_UNAVAILABLE. No source/workflow verdict changes.

## Development verification

Worker generality uses real temporary Git graphs under `tests/.tmp`, synthetic
protocol receipts, accepted regression helpers and explicitly injected fake GET
responses. These prove verifier behavior, not that synthetic receipts originated
from production executions. Selected transition/repair regressions protect the
minimal integration points. No full repository suite, S32DS, E2E or KPI run is
part of this feature's Worker verification; Tester acceptance remains independent.

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-09-09 | 0.1.0 | Added read-only source/remote proof contract, exact authority, repair continuity and CLI boundaries. |
| 2026-09-09 | 0.1.1 | Clarified encoding-independent commit structure and isolated recursive receipt attempts. |
| 2026-09-10 | 0.1.2 | Distinguished W4 tested Candidate C from lessons-only delivery L, with real append/blob proof and exact L-bound remote approval/merge while retaining older-version authority. |
