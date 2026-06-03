# RTD Config Core Spec Comments Tracking

| Field | Value |
| --- | --- |
| Version | 0.4.1 |
| Date | 2026-06-02 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | Tracks how review comments were resolved across design document revisions. |

This file tracks how the user's inline `REVIEW` comments were resolved. The
reviewed draft with comments preserved in context is archived at:

`docs/superpowers/specs/achieved/rtd-config-core-design.reviewed.md`

Second-round reviewed drafts are archived under:

`docs/superpowers/specs/achieved/second-review/`

Third-round reviewed drafts are archived under:

`docs/superpowers/specs/achieved/third-review/`

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
| C17 | Fixtures | Do not specify a specific fixture project in spec; describe generic fixture structure. | Replaced concrete fixture names with generic backend/family/device/module/projects/project fixture layout. | Core design spec, Fixtures |
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
| C32 | Spec header | Add version, date, author, AI-assisted note, overview description, and table of contents. | Added metadata, overview, and contents section to the active spec. | Core design spec |
| C33 | Purpose and architecture | Agent Skills are required because the tool targets AI agents. | Added Agent Skills to goals, architecture, project structure, and success criteria. | Core design spec |
| C34 | Goals | Configuration completion and from-scratch configuration file creation are also long-term goals. | Added these as long-term goals while leaving staged delivery in the roadmap. | Core design spec; roadmap |
| C35 | Architecture | Companion Agent Skills must be explicit in the architecture. | Added an Agent Skills layer that adapts public CLI workflows without bypassing the CLI contract. | Core design spec, Architecture |
| C36 | Module capability table | Move the module table to a separate file for maintainability and point the spec to it. | Added `docs/superpowers/specs/rtd-config-module-capabilities.md` and replaced the inline table with a pointer and table requirements. | Module capabilities; core design spec |
| C37 | Subagent independence | Spec should briefly state subagent validation is black-box and receives no main-agent context or development text. | Added concise black-box subagent validation wording to the spec and detailed rules in test strategy. | Core design spec; test strategy |
| C38 | Test layers | Independent subagent validates fixture integration and vendor headless validation; main agent may run fast deterministic tests. | Updated test strategy to assign fast deterministic tests to development and subagent validation to integration/vendor layers. | Test strategy |
| C39 | Reference locations | Reference document should state where source materials are located. | Added concrete known development reference locations for IOMUX workbook, RTD `.xdm` pattern, Uart `.xdm` example, and fixture projects. | Source materials reference |
| C40 | Second-review traceability | Preserve second-round comments with their document context. | Backed up the second-round reviewed docs under `specs/achieved/second-review/`. | Achieved second-review backups |
| C41 | File naming | Do not put dates in filenames because changelogs already carry date information. | Renamed dated documentation files to semantic names and updated internal links. | Documentation filenames; this tracking file |
| C42 | Third-review traceability | Preserve the third-round inline comments with original document context before removing comments from active docs. | Backed up the reviewed core design, test strategy, and roadmap docs under `specs/achieved/third-review/`. | Achieved third-review backups |
| C43 | Tool naming | Standardize the tool name as RTD CfgFile CLI and define that it edits RTD config files according to vendor rules so code generation is correct. | Renamed the core design title/overview/terminology to RTD CfgFile CLI and clarified the vendor-rule/code-generation contract. | Core design spec, Overview and Terminology |
| C44 | Static check vs runtime verification | Align static check with runtime verification and decide whether they should merge. | Defined runtime verification as the umbrella process. Static check remains the fast tool-owned stage, while backend validation remains the vendor-backed stage; both share the result model but stay separate execution steps. | Core design spec, Terminology and Runtime Verification Pipeline; AGENTS.md |
| C45 | Goal wording | Avoid saying the tool replaces hand-editing XML; RTD is normally configured through S32 ConfigTools or EB tresos. | Rewrote the purpose and goals to state that agents use RTD CfgFile CLI instead of directly operating vendor GUI configuration workflows. | Core design spec, Purpose and Goals |
| C46 | Agent reasoning goal | Add a goal for AI agents to decompose complex requirements such as communication configuration sheets and Port pin layouts before using the CLI. | Added goal G03 and expanded the Agent Skills description to cover analysis, decomposition, dependency reasoning, and validation feedback handling. | Core design spec, Goals and Architecture |
| C47 | Development/runtime boundary | Do not treat separation of development source material and runtime assets as a project goal; make it a development rule. | Removed that item from the goals table and added a Development Release Boundary section to `AGENTS.md`. | Core design spec, Goals; AGENTS.md |
| C48 | Spec maintainability wording | Do not list spec/table maintainability as a project goal. | Removed maintainability as a goal and kept maintainable docs as document structure rather than product objective. | Core design spec, Goals |
| C49 | Purpose and goals format | Simplify Purpose and express Goals as a table. | Compressed the Purpose section and replaced the goals bullet list with a goal table containing IDs and success signals. | Core design spec, Purpose and Goals |
| C50 | Architecture diagram | Add an architecture diagram if Markdown can render it, otherwise provide a Draw.io file and reference it. | Added an inline Mermaid architecture diagram and an editable Draw.io source file under `docs/superpowers/specs/figures/`. | Core design spec, Architecture; architecture Draw.io file |
| C51 | Module capability text | Remove process-oriented capability-table maintenance wording from the spec. | Removed the paragraph that told maintainers to update the table on every feature addition, while keeping the structural requirements for the table. | Core design spec, Module Capability Model |
| C52 | CLI command explanation | Explain `pin-options` and convert core commands into a table. | Replaced core command code block with a table explaining purpose, write behavior, and vendor-tool launch behavior; documented `pin-options` as a runtime pin-mapping query. | Core design spec, Intent And Commands |
| C53 | Shortcut command explanation | Convert shortcut commands into a table. | Replaced shortcut command examples with a module-group table explaining each shortcut's role and intent-normalization behavior. | Core design spec, Intent And Commands |
| C54 | Test case catalog | Use retired RTD module skills to define first-milestone test cases for the seven modules, with IDs in a table. | Added a Milestone 1 S32K3 MEX test case catalog with IDs covering Mcu, BaseNXP, Platform, Port, Dio, Mcl, Uart, cross-module Uart flows, and deferred-feature diagnostics. | Test strategy |
| C55 | Test failure loop | State that failed tests must return to code development and iterate until the development-test loop closes. | Added a Failure Iteration Loop section requiring root-cause analysis, code/runtime-data/fixture/test fixes, and reruns before acceptance. | Test strategy |
| C56 | Roadmap overview | Add an overview roadmap table before milestone detail sections. | Added a Roadmap Overview table with focus, primary deliverable, and carried-forward exclusions for each milestone. | Roadmap |
| C57 | Milestone 1 scope | Move tests outside Milestone 1 scope to later reserved cases; exact execution is decided during later milestone planning. | Split the test strategy into mandatory minimum, advanced, and reserved future case tables. Missing-module completion, `.mex` creation, DMA, low-power/RAM/reset, Platform MPU/MCM/INTM, partitioning, and non-Uart Mcl resources moved to reserved future cases. | Test strategy; roadmap |
| C58 | Minimal testing | Mark only the minimal Milestone 1 tests as required; keep other current-surface tests as advanced and execute them only by explicit user instruction. | Added mandatory minimum and advanced test classes, made mandatory minimum the default Milestone 1 acceptance gate, and added roadmap language for default test scope. | Test strategy; roadmap |
| C59 | Tool name consistency | Standardize all active documentation on the official tool name RTD CfgFile CLI. | Renamed active document titles/descriptions and replaced generic tool references in active docs. | Core design; module capabilities; source materials; test strategy; roadmap; AGENTS.md |
| C60 | Definitions | Add explicit definitions to avoid conflicts between development testing, runtime verification, static check, backend validation, mandatory/advanced/reserved tests, and subagent prompts. | Added terminology in the core design and test strategy, and summarized operational rules in `AGENTS.md`. | Core design; test strategy; AGENTS.md |
| C61 | Subagent prompts and KPI | Add subagent prompt content to every test case, keep prompts limited to simulated user configuration demands, use 3-minute focused KPI, 5-minute E2E KPI, and 10-minute maximum run before main-agent intervention. | Added `Subagent user prompt` to mandatory, advanced, and reserved case tables and clarified subagent validation/KPI rules. | Test strategy; core design; AGENTS.md |
| C62 | Capability/test alignment | Align capability table and case catalog so module capability entries point to mandatory, advanced, and reserved test IDs. | Reworked the module capability table with M1 mandatory cases, M1 advanced cases, and reserved future cases per module. | Module capabilities; test strategy |
| C63 | Vendor tool environment | Clarify that vendor validation tools may rely on their configured installation environment, and the current computer is configured for that flow. | Added vendor tool environment terminology and source-material boundary clarification. | Core design; source materials; AGENTS.md |
| C64 | Review archives | Mark review backup files as unavailable and forbid using them as requirements sources. | Added archive warnings to all reviewed draft backups and added a documentation-boundary rule in `AGENTS.md`. | Achieved review archives; AGENTS.md |
| C65 | Fixture layout | Align documentation and actual Uart fixture project with `fixtures/<backend>/<family>/<device>/<module>/projects/<project>/`. | Updated fixture structure in core design, test strategy, and source-materials reference; moved the Uart fixture project to `fixtures/mex/s32k3/s32k344/uart/projects/Uart_Example_S32K344/`. | Core design; test strategy; source materials; fixtures |

## Open Follow-Up

The current documents separate project spec, roadmap, source references, and
test strategy. A future development-process document should capture the
human-assisted agent development loop, skill growth, and closed-loop validation
workflow as that process becomes concrete.

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-06-02 | 0.4.1 | Tracked fixture layout update for module-scoped projects directories. |
| 2026-06-02 | 0.4.0 | Tracked final consistency review updates for milestone test scope, tool naming, definitions, KPI, capability alignment, vendor environment, and archive boundaries. |
| 2026-06-02 | 0.3.0 | Added third-round review tracking records and archive location. |
| 2026-05-30 | 0.2.2 | Formatted document metadata and changelog as tables. |
| 2026-05-30 | 0.2.1 | Removed dates from documentation filenames and updated tracking. |
| 2026-05-30 | 0.2.0 | Added second-round review tracking records. |
| 2026-05-30 | 0.1.0 | Created review comment tracking table. |
