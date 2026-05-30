# RTD Config Core Spec Comments Tracking

This file tracks how the user's inline `REVIEW` comments were resolved. The
reviewed draft with comments preserved in context is archived at:

`docs/superpowers/specs/achieved/2026-05-30-s32k3-rtd-mex-config-core-design.reviewed.md`

## Tracking Table

| ID | Original area | Comment intent | Resolution | Target document |
| --- | --- | --- | --- | --- |
| C01 | Purpose | Clarify that human-agent collaboration is the development mode, not the tool's purpose. | Rewrote purpose to state that the tool is for AI agents to directly and autonomously configure RTD quickly, efficiently, accurately, and reliably. | Core design spec, Purpose |
| C02 | Purpose | Do not put milestone limits in the spec purpose. | Removed staged wording from the spec and moved milestone limits to the roadmap. | Core design spec; roadmap |
| C03 | Purpose | State the complete long-term target: all RTD modules, RTD RTOS, stacks, external peripheral drivers, `.mex`, EB tresos, more chips, and RTD versions. | Expanded the purpose and backend sections to describe full RTD surface, S32 ConfigTools, EB tresos, S32K3/K1/K5, RTD releases, and future modules. | Core design spec, Purpose and Supported Configuration Backends |
| C04 | Purpose | Avoid first-phase language in the spec. | Removed first-phase framing from the spec; milestone-specific scope now lives in the roadmap. | Core design spec; roadmap |
| C05 | Development mode | Agent closed-loop development/testing workflow is important but should not be project spec content. | Removed AI workflow-platform wording from the spec and moved validation discipline into the test strategy. Future development-process details can live in a separate process document. | Core design spec; test strategy |
| C06 | Scope | Put staged plan and limits in implementation plan/roadmap. | Replaced the spec scope section with project goals and moved staged limits into `Milestone 1`. | Roadmap |
| C07 | MEX document core | `.mex` files may be large; runtime parsing/indexing must consider efficiency and may need validation before final strategy. | Added targeted indexing, measured strategy evolution, and fallback to targeted indexes/prepared summaries if broad indexing is too slow. | Core design spec, Backend Document Core and Performance Requirements |
| C08 | Module providers | Providers must model dependencies such as FlexIO Uart -> Mcl and interrupt mode -> Platform. | Added explicit cross-module dependency planning and capability-table dependency fields. | Core design spec, Architecture and Module Capability Model |
| C09 | Module providers | Providers must model chip/module constraints from RTD descriptors such as `.xdm`. | Added constraint/resource cache requirements and stated constraints must come from prepared runtime cache data. | Core design spec, Module Capability Model and Resource And Constraint Data |
| C10 | Runtime boundary | Development source materials must not appear in code or runtime dependencies. | Added a runtime boundary: runtime loads only committed JSON/cache assets and configured validation tools, not Excel, RTD scans, or development notes. | Core design spec; source materials reference |
| C11 | Spec tone | Spec should describe what to build, not PoC problems. | Removed PoC-problem wording from active spec. The original comment remains in the archived reviewed draft. | Core design spec; achieved reviewed draft |
| C12 | Module responsibilities | Module responsibilities should be a maintainable table, extensible for new modules. | Replaced prose-only module responsibilities with a module capability model table and required metadata fields. | Core design spec, Module Capability Model |
| C13 | Data assets | Do not mention phase-specific validation in spec. | Removed phase-specific wording from data assets and moved S32K344-first validation to roadmap. | Core design spec; roadmap |
| C14 | Port roadmap | State in roadmap that Port must implement complete generic pin configuration early. | Added Milestone 1 scope item for complete generic pin mapping/configuration for the validated device/package. | Roadmap, Milestone 1 |
| C15 | References | Do not hard-code reference source files in spec; add a reference document. | Removed the hard-coded local Excel path and RTD path from active spec; added a source materials reference document. | Source materials reference |
| C16 | MEX/XDM editing | MEX writing must consider efficiency; later `.xdm` editing can be summarized. | Added backend document-core efficiency requirements for `.mex` and a summarized EB tresos `.xdm` writer direction. | Core design spec, Backend Document Core |
| C17 | Fixtures | Do not specify a specific fixture project in spec; describe generic fixture structure. | Replaced concrete fixture names with generic backend/family/device/scenario fixture layout. | Core design spec, Fixtures |
| C18 | Validation scope | The validation method applies to all modules and future work, not only a milestone. | Moved reusable test layers and validation method into the test strategy. | Test strategy |
| C19 | Test cases | Add a separate test document with detailed test cases; spec should require that document. | Added test strategy document with test layers, fixture structure, and test case template; spec now points to maintainable test docs. | Test strategy; core design spec |
| C20 | Subagent validation | Move independent subagent validation details to the test document. | Moved subagent validation rules to test strategy. | Test strategy |
| C21 | KPI | KPI applies to all module configuration and needs a separate summary. | Added KPI section in test strategy and summarized acceptance/KPI in the spec. | Test strategy; core design spec |
| C22 | Success criteria | Do not say Phase 1 in spec success criteria. | Rewrote success criteria as project-level criteria. | Core design spec, Success Criteria |
| C23 | Acceptance | Acceptance should be based on two things: KPI and test case pass results. | Rewrote acceptance section around required test cases passing and KPI being met. | Core design spec, Tests And Acceptance |
| C24 | Test document evolution | Test documents need staged, maintainable, updateable coverage. | Test strategy defines reusable template and allows backend/milestone-specific test documents. | Test strategy |
| C25 | Summary | Spec should be complete and maintainable; staged limited development belongs in plan/roadmap. | Reorganized spec as long-term design and roadmap as staged delivery. | Core design spec; roadmap |
| C26 | Supporting docs | Add reference and test files for maintainability. | Added source materials reference, test strategy, roadmap, and comments tracking. | References; tests; roadmap; this tracking file |
| C27 | Development mode vs spec | Separate development mode from project spec. | Removed development-mode content from spec; retained validation discipline in test strategy. A future process document can cover the broader development mode. | Core design spec; test strategy |
| C28 | Runtime assets | Distinguish development-time resource references from runtime dependencies. | Added runtime boundary to source materials reference and resource/cache rules to spec. | Source materials reference; core design spec |
| C29 | Reviewed draft traceability | Comments need their original content context. | Archived a reviewed draft with inline comments preserved in context under `specs/achieved/`. | Achieved reviewed draft |
| C30 | Comments resolution visibility | Need a tracking record showing how comments were resolved. | Added this comments tracking file with per-comment resolution and target document. | This tracking file |
| C31 | Remove low-value isolated archive | Standalone comments without context are not enough. | Removed the standalone comments archive and replaced it with contextual reviewed draft plus tracking. | Achieved reviewed draft; this tracking file |

## Open Follow-Up

The current documents separate project spec, roadmap, source references, and
test strategy. A future development-process document should capture the
human-assisted agent development loop, skill growth, and closed-loop validation
workflow as that process becomes concrete.
