# Workflow Evidence Verification Cases

| Field | Value |
| --- | --- |
| Version | 0.1.0 |
| Date | 2026-09-09 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Concise owner functional cases derived independently from the complete public #86 K1 requirements. |

| Case | Requirements | Scenario | Expected result |
| --- | --- | --- | --- |
| WE01 | R01,R02,R14 | Empty accepted State and public verifier API. | Detached closed deterministic result; unowned sources stay null and no remote call occurs. |
| WE02 | R02,R15,R16 | Malformed authority, duplicate actors, invalid deadline or relative repository root. | Stable input rejection before proof. |
| WE03 | R03,R08,R15 | Contradictory State with other evidence absent. | Existing INVALID_STATE priority and input preservation. |
| WE04 | R03,R04,R06,R15 | Consumed artifact, matching receipt, attachment or Git object is missing; present bytes are corrupted. | Missing proof is MISSING_EVIDENCE; contradictory present bytes are INVALID_EVIDENCE, never NOT_APPLICABLE. |
| WE05 | R03,R15 | Invalid matching receipts, or both invalid and valid matching receipts in different orders. | Reject when none is valid; select a valid exact receipt without unrelated/invalid alternatives poisoning proof. |
| WE06 | R04,R07,R14 | Ready, C0, corrected READY before C1, and C1 states. | Source tips remain exact; Candidate index and correction count are independently projected. |
| WE07 | R07,R08,R13,R19 | Multiple incremental corrections through successful merge or exhausted failure. | Preserve strict source continuity, maximum three corrections and truthful success/failure sources. |
| WE08 | R04,R08,R14 | Registered support repair before or after executable Candidate ownership. | Original case approval stays anchored; effective and executed Test reflect actual ownership. |
| WE09 | R05,R06 | Candidate has real ordered lane parents but omits Test or introduces merge-only path/blob/mode changes. | Reject the non-union tree despite plausible parent and coverage metadata. |
| WE10 | R05,R06 | Disjoint Test changes add an ordinary reference fixture, delete an inherited leaf, or change its executable/symlink mode. | Accept the exact leaf-tree union; preserve inherited history and legitimate file names. |
| WE11 | R06 | Task introduces ignored-state, temporary overlay or Reviewer lessons into the Candidate tree. | Reject the exact prohibited acceptance content. |
| WE12 | R09,R15 | A consumed correction omits a second IMPLEMENTATION finding from disclosure mapping. | Reject incomplete diagnosis coverage without publishing private finding content. |
| WE13 | R10,R15 | Remote vote has wrong comment/repository/issue/actor identity or changed body/time/deletion/reply facts. | Reject contradictory current authority facts; accept required fields plus ordinary GitHub extras. |
| WE14 | R10,R11 | Captured/current approval contains trailing whitespace or additional text; REQUEST_CHANGES has the exact nonempty reason. | Reject prefix/normalized approval; accept the exact supported request-changes command. |
| WE15 | R10 | Nominated packet belongs to a wrong issue/ID or is not strictly earlier than the vote. | Reject invalid packet binding or temporal order. |
| WE16 | R10,R15,R16 | Owned comment transport returns 404, authorization/rate/server errors, an exception or illegal response shape. | 404 is missing evidence; unavailable or invalid transport is REMOTE_UNAVAILABLE. |
| WE17 | R02,R10 | Valid captured authority files are supplied without authenticated GET transport. | Do not infer authentication from snapshots; report REMOTE_UNAVAILABLE. |
| WE18 | R11 | Accepted vote uses the preserved manual Human-command source. | AUTHORITY_UNVERIFIABLE preserves the manual workflow source without automatic verification. |
| WE19 | R12,R13,R14 | Locally accepted success proposal has no PR yet. | Validate local truth, retain accepted Candidate, finalization NOT_APPLICABLE and no PR request. |
| WE20 | R12,R13 | Remote open PR has wrong URL/number/repository/base/head or is not genuinely open and unmerged. | Reject anything other than the exact accepted Candidate proposed against G. |
| WE21 | R12,R13 | Merged PR has exact fast-forward or two-parent [G,Candidate] lineage; mutable current base has moved. | Accept Candidate-identical allowed merge history; do not use mutable postmerge base as historical G. |
| WE22 | R12 | Merged source is squash/rebuild, wrong-parent merge or contains extra edits. | Reject inconsistent finalization proof. |
| WE23 | R01,R02,R08,R15,R16 | Repeated verification and observed Git operations; command deadline expires. | No input/files/source mutation or write-oriented Git operation; configured deadline and safe timeout error. |
| WE24 | R08,R19 | Same reducer event/artifact is replayed. | DUPLICATE_EVENT remains stable and cannot advance source or counters. |
| WE25 | R14,R15,R16 | CLI success/help, usage errors and semantic rejection. | Canonical JSON channel/exit rules hold; help stays normal and errors expose no traceback. |
| WE26 | R10,R12,R16 | CLI uses an explicitly injected executable transport for owned remote GET proof. | Only repository-relative authenticated GitHub GET argv, explicit hostname and deadline; exact HTTP exit mapping. |
| WE27 | R02,R14 | Published transport schema accompanies the verifier. | Authority and Result are closed; State/Context are not duplicated. |
| WE28 | R01,R03,R07,R08,R17,R18,R19 | Directly affected accepted transition and W3 metadata/support behavior. | Existing replay, corrected-READY projection, proposal boundary and source-repair semantics remain unchanged. |

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-09-09 | 0.1.0 | Added independently derived K1 evidence-verifier cases; execution details and evidence remain outside this reference. |

