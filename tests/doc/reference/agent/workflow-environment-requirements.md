# #79 开发环境能力与隔离：完整需求

| Field | Value |
| --- | --- |
| Version | 0.1.0 |
| Date | 2026-09-10 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | 公开 K 的完整中文需求与公开接口审阅参考。 |

来源为 K revision 0，SHA-256 a2c2e93ed9302f7a3d2301695093206d753dfdf039d7fba23149fd9fa95d34d5；Governor 0e840c9fd0b9e16d56642da20f718c87ffe8f8f9。本文件是审阅呈现，不替代公开 K。

## R01

将可移植的开发环境能力与隔离规则同 Codex、Claude Code、OpenCode 平台适配分离。既有固定版本工作流契约、结构化交接注册表、纯转换内核和只读证据验证器继续作为各自权威；不新增生命周期、执行器、审批关口或隐式旧版回退。

来源：[#79](https://github.com/autoMBD/autombd-rtd-config/issues/79)；[Governor Charter](https://github.com/autoMBD/autombd-rtd-config/blob/0e840c9fd0b9e16d56642da20f718c87ffe8f8f9/AGENTS.md)

## R02

在结果和文档中区分工作目录分离、Git 引用/对象隔离、操作系统读取/输入隔离。linked worktree 本身不能证明 Worker 输入隔离；独立单分支 clone 可阻断共享 Git 引用/对象访问，但不能标成 OS 读取隔离。强输入隔离必须具有真实且适用的证据，不能仅凭指令文本、目录改名、权限配置名或命令退出 0。

来源：[#79](https://github.com/autoMBD/autombd-rtd-config/issues/79)；[Governor Charter](https://github.com/autoMBD/autombd-rtd-config/blob/0e840c9fd0b9e16d56642da20f718c87ffe8f8f9/AGENTS.md)

## R03

在明确请求的精确提交上，安全创建、检查独立单分支派生 checkout。新 clone 使用独立对象库，不得有 alternates、共享对象链接、无关引用或残留源 remote 导致隐式跨 lane fetch。引用、路径或 HEAD 漂移时拒绝请求；不修改源 checkout，不静默切换、重置或覆盖既有目标。

来源：[#79](https://github.com/autoMBD/autombd-rtd-config/issues/79)

## R04

仅从已初始化项目和调用者明确提供、已验证的初始化输入中捕获可复用证据；输入原始字节 SHA-256 必须等于可信预期。验证所选平台、实际生成角色字节、Skill 目标/源和依赖缓存有效性。捕获过程不补做缺失初始化，不打开 GUI，不推断 Human 选择，不复制凭证，也不声称已独立认证 Human 意图。

来源：[#79](https://github.com/autoMBD/autombd-rtd-config/issues/79)；[Governor Charter](https://github.com/autoMBD/autombd-rtd-config/blob/0e840c9fd0b9e16d56642da20f718c87ffe8f8f9/AGENTS.md)

## R05

基于捕获的源，对已授权派生 checkout 提供非交互 hydration。绑定源规范根路径、Git/源资源身份、所选输入摘要、已部署 discipline 和相关可复用缓存证据；源证据变化或缺失时拒绝。使用目标本地的规范 discipline 源及已选且已验证的外部 Skill 源；只部署原始批准平台的请求子集。

来源：[#79](https://github.com/autoMBD/autombd-rtd-config/issues/79)

## R06

hydration 在任何目标写入前拒绝：证据格式错误、预期摘要错误、源初始化缺失/过期、源或目标身份错误、未批准平台、源等于目标、不合格首次 clone、目标不在明确允许的派生基目录内，以及逃逸 symlink/junction/祖先路径。此类失败不得 mkdir、删除、重置、写缓存或部分部署。有效新派生 checkout 可以没有 ignored 文件；这种缺失本身不构成新的 Human 初始化请求。

来源：[#79](https://github.com/autoMBD/autombd-rtd-config/issues/79)

## R07

保留 clean clone/reset 的 GUI-first 初始化和所选平台部署语义。hydration 是明确的派生 checkout 操作，不能自动绕过 clean-clone/reset 初始化。不能把源 reset 重放到派生目标，不能在 Loop 内重开 GUI；既有角色描述断言漂移属于 #92，不在本 issue 修复。

来源：[#79](https://github.com/autoMBD/autombd-rtd-config/issues/79)；[Governor Charter](https://github.com/autoMBD/autombd-rtd-config/blob/0e840c9fd0b9e16d56642da20f718c87ffe8f8f9/AGENTS.md)

## R08

声明 Orchestrator、Explorer、Worker、Tester、Reviewer 能力配置，以及仅在所选操作需要时要求的 Git、GitHub、当前平台 Agent CLI/黑盒与 S32DS。按真实角色、操作和功能 Test Impact Set 选择要求；不执行相关工具的 gate 不要求所有 Agent 厂商、S32DS、全量 RTD-MEX/KPI 或黑盒能力。

来源：[#79](https://github.com/autoMBD/autombd-rtd-config/issues/79)；[Governor Charter](https://github.com/autoMBD/autombd-rtd-config/blob/0e840c9fd0b9e16d56642da20f718c87ffe8f8f9/AGENTS.md)

## R09

preflight 消费明确的当前操作需求和源绑定观测；仅当所有必需能力可用且已授权时返回 READY，并在调用者 dispatch 前返回 BLOCKED 诊断。必需事实缺失、unknown、过期或未授权时该操作关闭；可选能力缺失不阻塞。无人值守操作期间不得交互审批、认证、打开 GUI、自动配置凭证或升级权限。

来源：[#79](https://github.com/autoMBD/autombd-rtd-config/issues/79)

## R10

能力/证据身份绑定 task_run、Governor 提交、W blob、K 摘要、规范 checkout 根、精确 HEAD，以及适用时的 Candidate SHA。调用者继续前必须使用同一请求身份和有效能力报告；拒绝绑定改变、过期/缺失证据或先前 BLOCKED 报告。本 gate 自身不 dispatch Agent，也不消费工作流转换。

来源：[#79](https://github.com/autoMBD/autombd-rtd-config/issues/79)；[Governor Charter](https://github.com/autoMBD/autombd-rtd-config/blob/0e840c9fd0b9e16d56642da20f718c87ffe8f8f9/AGENTS.md)

## R11

适配器探针使用明确提供的可信 argv/cwd 和预授权执行上下文，执行有界非交互命令。不拼接不可信 shell 文本，不等待 stdin 交互，不在失败后扩大权限，不扫描安装目录，不保存可能含凭证的原始输出。真实可用性与有界命令证据单独报告，不充当功能 verdict；命令 deadline 不限制整个 Agent 会话。

来源：[#79](https://github.com/autoMBD/autombd-rtd-config/issues/79)；[Governor Charter](https://github.com/autoMBD/autombd-rtd-config/blob/0e840c9fd0b9e16d56642da20f718c87ffe8f8f9/AGENTS.md)

## R12

分别记录 host、sandbox、connector 可用性。Codex GitHub 操作优先可用 connector，否则接受明确授权且可用的 host-cli。sandbox 认证失败不抹除健康 host 能力，也不触发重新认证。保留 connector/host-cli/unavailable 模式，不压成混合布尔值；不能把 host keyring 密钥传到 sandbox。

来源：[#79 GitHub 上下文评论](https://github.com/autoMBD/autombd-rtd-config/issues/79#issuecomment-5036108564)

## R13

默认选择当前贡献者可用的 CLI，显式调用者选择优先。不得无条件默认 OpenCode/Codex/Claude，也不得要求另外两家已安装。贡献者上下文未知/歧义或所选 CLI 不可用时明确报错，不能静默换厂商。旧贡献者的缓存偏好不能覆盖明确已知当前平台。

来源：[#79](https://github.com/autoMBD/autombd-rtd-config/issues/79)

## R14

把 actor 选择集成到 tools/blackbox_e2e.py 和可扩展适配器注册表，保留显式 --agent 行为和真实偏好来源。支持 Codex、Claude Code、OpenCode 选择，不要求所有可执行文件均存在；必要最小的一次性适配集成仅限本选择/能力工作。不实现 #98 的轮询、进度、中断、超时重设计或进程树生命周期。

来源：[#79](https://github.com/autoMBD/autombd-rtd-config/issues/79)；[#79 消费边界评论](https://github.com/autoMBD/autombd-rtd-config/issues/79#issuecomment-5541712568)

## R15

当选择 E2E 时保留真正黑盒边界：独立 Agent CLI 仅接收已部署运行时 Skill、暂存 fixture 和 prompt，不接收仓库/owner Test 源，也不能用嵌入子 Agent 替代。保留适用 S32DS 退出 0 且零 SEVERE [TOOL] 判据；actor/preflight 工作不能弱化实际 vendor 或 E2E 验收。

来源：[#79](https://github.com/autoMBD/autombd-rtd-config/issues/79)；[Governor Charter](https://github.com/autoMBD/autombd-rtd-config/blob/0e840c9fd0b9e16d56642da20f718c87ffe8f8f9/AGENTS.md)

## R16

定义并执行源/证据卫生：验收中的精确 Candidate 只读；gate 后写入限明确 allowlist 的 ignored 证据位置，不能改 Candidate 源、用例、manifest 或冻结批准。重新计算源绑定和被引用证据摘要；源/证据改变使受影响旧结果失效，不能把旧结果重新标为当前。

来源：[#79](https://github.com/autoMBD/autombd-rtd-config/issues/79)；[Governor Charter](https://github.com/autoMBD/autombd-rtd-config/blob/0e840c9fd0b9e16d56642da20f718c87ffe8f8f9/AGENTS.md)

## R17

对明确命名的当前运行临时/证据路径提供受限清理计划和执行；写入前验证规范包含关系及路径/链接边界。保留被引用审阅证据和源/Candidate 分支；拒绝主目录/源根、无关路径、绑定证据及目标逃逸。不实现 #98 进程树清理或按年龄自动删除。测试使用 tests/.tmp，仅保留报告绑定证据。

来源：[#79](https://github.com/autoMBD/autombd-rtd-config/issues/79)；[Governor Charter](https://github.com/autoMBD/autombd-rtd-config/blob/0e840c9fd0b9e16d56642da20f718c87ffe8f8f9/AGENTS.md)

## R18

可移植记录带版本、确定性、JSON 可序列化，明确证据来源/限度和安全诊断。调用者提供事实或摘要不能证明远程 Human 权威、全局隔离或功能验收。既有缓存只持久化非秘密且可复用环境事实；本次契约和证据留在规范 ignored 任务存储。

来源：[#79](https://github.com/autoMBD/autombd-rtd-config/issues/79)；[Governor Charter](https://github.com/autoMBD/autombd-rtd-config/blob/0e840c9fd0b9e16d56642da20f718c87ffe8f8f9/AGENTS.md)

## R19

实现优先标准库并保持窄所有权。新源文件使用项目统一 MIT 文件头。Agent workflow 参考位于 agent-discipline；不向产品 docs/ 引入 Agent 义务或机器本地路径。不修改 lessons、owner review archive、无关模块，Implementation 不修改当前 owner Test。

来源：[#79](https://github.com/autoMBD/autombd-rtd-config/issues/79)；[Governor Charter](https://github.com/autoMBD/autombd-rtd-config/blob/0e840c9fd0b9e16d56642da20f718c87ffe8f8f9/AGENTS.md)

## R20

Tester 不读 Implementation，从 K 独立推导按需求选择的功能 Impact Set、脚本、完整可读需求及简洁用例。包含适用的真实 RED、known-good/known-bad 和 full-chain 预验证；不适用项给具体理由。synthetic fixture 可验证适配器，但不得称为真实 live Agent/vendor PASS。Human Gate 1 冻结精确用例/范围，不新增设计或逐步 Human gate。

来源：[#79](https://github.com/autoMBD/autombd-rtd-config/issues/79)；[Governor Charter](https://github.com/autoMBD/autombd-rtd-config/blob/0e840c9fd0b9e16d56642da20f718c87ffe8f8f9/AGENTS.md)

## R21

Worker 通过 TDD 和通用性覆盖实现公开能力面，不依赖 owner 用例字面量。Tester/Worker 从同一 G/K 独立开始，保持各自所有权，通过当前结构化交接报告精确源/证据。不以历史聊天/任务执行证据或临时例外为来源。

来源：[#79](https://github.com/autoMBD/autombd-rtd-config/issues/79)；[Governor Charter](https://github.com/autoMBD/autombd-rtd-config/blob/0e840c9fd0b9e16d56642da20f718c87ffe8f8f9/AGENTS.md)

## R22

向 #98/#87 消费者暴露能力/隔离证据，不接管 runner 生命周期或路由执行。复用适用的 #85/#86 身份/证据接口，不再造工作流状态机。#85、#86 是已接受硬依赖；#92 和 KPI #100–102 不是新增阻碍。

来源：[#79 消费边界评论](https://github.com/autoMBD/autombd-rtd-config/issues/79#issuecomment-5541712568)；[Governor Charter](https://github.com/autoMBD/autombd-rtd-config/blob/0e840c9fd0b9e16d56642da20f718c87ffe8f8f9/AGENTS.md)

## R23

本次开发执行不把尚未完成的 #79 目标功能当成自身 dispatch 前提。诚实使用当前 Governor 的角色边界、隔离工作树、选择性逐字节交接、监督和补偿检查，不声称这些现有措施已证明待实现技术能力。保留 #79 原始验收范围，以及 Human 将初始化描述测试冲突归入 #92 的当前处置。

来源：2026-09-10 当前 Human 澄清：未完成的 #79 不是自身前置门槛；初始化描述测试冲突归 #92；本参考 R23 已完整呈现。；[Governor Charter](https://github.com/autoMBD/autombd-rtd-config/blob/0e840c9fd0b9e16d56642da20f718c87ffe8f8f9/AGENTS.md)

## 公开接口与错误优先级

下列原始接口定义是需求的组成部分；不约束不透明 snapshot 的内部字段。平台为 codex、claude、opencode；错误由带 .code/.as_dict() 的 EnvironmentError 表达。

### IF_INIT — agent-discipline/skills/initialize-agent-discipline/scripts/init_agent_env_hydrate.py

capture_initialization(source_root: pathlib.Path, input_path: pathlib.Path, *, expected_input_sha256: str) -> dict; hydrate_checkout(source_root: pathlib.Path, target_root: pathlib.Path, *, initialization: dict, expected_initialization_sha256: str, allowed_target_base: pathlib.Path, platforms: Sequence[str], expected_target_head: str) -> dict. capture returns an opaque versioned JSON-serializable snapshot produced from real initialized source; consumers hash canonical JSON (sorted compact UTF-8, ensure_ascii=False, final LF) to supply expected_initialization_sha256. No caller edits of the snapshot are needed for normal hydration. Hydration success returns at least status='HYDRATED', platforms and changed_paths (target-relative strings). Errors raise EnvironmentError with .code and .as_dict(); class may be re-exported from workflow_environment.py. Paths and source/assets are revalidated on every call; capture is read-only, hydration mutates only after all input/path validation. Existing collector/deployer public entrypoints remain compatible.

### IF_CHECKOUT — agent-discipline/skills/agent-workflow/scripts/workflow_environment.py

inspect_checkout(root: pathlib.Path, *, expected_head: str) -> dict; create_isolated_checkout(source_root: pathlib.Path, target_root: pathlib.Path, *, allowed_target_base: pathlib.Path, branch: str, expected_source_head: str) -> dict. Inspection returns root, head, git_dir, common_dir, checkout_kind ('worktree'|'clone'), shared_objects (bool), ref_isolated (bool), os_read_isolated=False unless separately proven by an applicable adapter; ref_isolated requires an independent single-branch object/ref store with no alternates. Creation uses exact source HEAD, independent objects, one new local requested branch, no source remote, and never overwrites an existing target. Return the target inspection. EnvironmentError on rejected identity/path/Git conditions.

### IF_PREFLIGHT — agent-discipline/skills/agent-workflow/scripts/workflow_environment.py

required_capabilities(role: str, *, requires_blackbox: bool=False, requires_s32ds: bool=False) -> tuple[str,...]; evaluate_preflight(request: dict, observations: dict) -> dict; require_preflight(report: dict, *, expected_request_sha256: str, current_bindings: dict) -> None. Request v1 fields: version=1, role (orchestrator|explorer|worker|tester|reviewer), platform (codex|claude|opencode), bindings={task_run,governor,workflow_blob,contract_sha256,checkout_root,head,candidate_sha256:null|40-hex}, required_capabilities:[unique strings], isolation='checkout'|'input'. Supported capability IDs include filesystem-read, filesystem-write, git, github, agent-cli, blackbox, s32ds, input-isolation. Baselines: every role needs filesystem-read; orchestrator/worker/tester need filesystem-write and git; reviewer/explorer have read-only ownership; optional role operations are explicitly added through required_capabilities. Observations v1: version=1, bindings identical, capabilities:[{id,context:'host'|'sandbox'|'connector',status:'available'|'unavailable'|'unknown',approved:bool,mode:str,evidence_sha256:64-hex}], checkout=inspection from IF_CHECKOUT. A trusted adapter is responsible for truthful observations and their evidence; the evaluator checks shape/identity and makes no OS/remote-auth claim from booleans alone. Report contains version=1, status='READY'|'BLOCKED', request_sha256 (canonical request digest), bindings, selected_capabilities, diagnostics:[{code,capability,message}]. Required union includes role baseline plus declared capabilities, plus input-isolation when isolation=input. Every selected capability must have available, approved, correctly bound evidence; known failed/unknown/absent mandatory facts BLOCK. GitHub selection follows R12; for Codex prefer connector, then approved host-cli. require_preflight rejects non-READY, wrong digest/bindings. Functions do not dispatch agents or execute workflow transitions; callers must call require_preflight before dispatch.

### IF_PROBE — agent-discipline/skills/agent-workflow/scripts/workflow_environment.py

probe_command(argv: Sequence[str], cwd: pathlib.Path, *, approved: bool, context: str, timeout_seconds: int=60) -> dict. Caller supplies trusted preflight-owned explicit command, never a repository-controlled arbitrary shell string. Reject unapproved, invalid argv/cwd/context/deadline before spawning. Execute without shell and with stdin closed; no escalation or interactive fallback. Return status ('available'|'unavailable'), context, exit_code (int|null), timed_out (bool), stdout_sha256 and stderr_sha256; do not return or persist raw output. A command's success is command evidence only, not read-isolation proof. Adapters additionally distinguish actual checkout topology and applicable non-secret allow/deny canary observations before asserting an input-isolation capability; document that existing observation input is trusted and the portable evaluator is not an OS sandbox.

### IF_ACTOR — tools/blackbox_e2e.py

select_agent(current_platform: str|None, available_agents: Sequence[str], *, explicit_agent: str|None=None) -> str is exposed (directly or re-exported) from workflow_environment.py. Explicit supported available agent wins; otherwise select the supported available current_platform. Missing/unknown/ambiguous platform or unavailable selected agent raises EnvironmentError (no silent vendor fallback). Extend resolve_agent(cli_agent, cache_path, *, current_platform=None, available_agents=None) compatibly for explicit-agent callers; add --current-platform to the existing CLI. Unknown context may use an unambiguous current-platform signal from caller/environment or unique available installed adapter, never an unconditional static vendor default. Legacy preference cache is a preference, not contributor identity, and cannot override explicit current_platform. Preserve the existing tuple(agent,source) return, with truthful source='flag'|'current-platform'|'cache'|'available'. New minimal adapter integrations retain existing RunResult/AgentAdapter protocols and must be grounded in current CLI syntax rather than model/session-history inspection.

### IF_HYGIENE — agent-discipline/skills/agent-workflow/scripts/workflow_environment.py

snapshot_evidence(root: pathlib.Path, paths: Sequence[str], *, bindings: dict) -> dict; verify_evidence(root: pathlib.Path, snapshot: dict, *, bindings: dict, allowed_new_paths: Sequence[str]=()) -> None; cleanup_paths(root: pathlib.Path, paths: Sequence[str], *, allowed_base: pathlib.Path, protected_paths: Sequence[str]=(), dry_run: bool=True) -> dict. snapshot records exact current Git HEAD/tree/dirty source status and byte digests of the explicitly listed evidence plus bound identity. verify rejects changed bindings/source/referenced bytes and non-allowlisted new task evidence files within the recorded evidence scope; allowlisted new ignored evidence does not alter existing bound bytes/source. Snapshot/evidence return objects are opaque versioned JSON; tests observe public operation behavior, no undocumented private keys. cleanup defaults to dry-run and returns status='PLANNED'|'CLEANED' plus target-relative paths; validate every path and protect all named evidence before any deletion. Operate only within allowed_base below the root, never root/.git/main source trees, and unlink a permitted link itself without following its destination. Do not traverse/delete bound evidence or implement process lifecycle.

### IF_CLI — agent-discipline/skills/agent-workflow/scripts/workflow_environment.py

Provide a thin JSON CLI: workflow_environment.py inspect-checkout --root PATH --expected-head SHA; preflight --request FILE --observations FILE; verify-preflight --report FILE --expected-request-sha256 DIGEST --bindings FILE. init_agent_env_hydrate.py capture --source-root PATH --input FILE --expected-input-sha256 DIGEST; hydrate --source-root PATH --target-root PATH --initialization FILE --expected-initialization-sha256 DIGEST --allowed-target-base PATH --platform PLATFORM (repeatable) --expected-target-head SHA. Successful JSON goes to stdout, errors are safe structured JSON. Exit 0 success/READY, 1 rejected/BLOCKED, 2 unreadable/malformed CLI input. CLI must not write input files or silently persist outputs; caller redirection owns output publication.

### IF_DOCS — agent-discipline/skills/agent-workflow/references/workflow-environment.md

Document the above API/wire, role/service capability profiles, portable-vs-platform boundaries, first initialization versus derived hydration, explicit CLI examples and evidence limits. Durable public implementation reference is Worker-owned. Tester independently persists every K.payload.requirements item in tests/doc/reference/agent/workflow-environment-requirements.md and derives a concise workflow-environment-cases.md, linked from tests/doc/README.md. Current cases/index and acceptance scripts are private owner Test until accepted and are never Worker inputs. Internal implementation modules/schema details may be split by responsibility without changing these public interfaces; new public interface semantics require Orchestrator reconciliation before relying on them.

| 优先级 | 条件 | 结果/错误 |
| --- | --- | --- |
| 0 / DR01 | 输入格式、平台歧义或源摘要不一致 | INVALID_INPUT；在目标/子进程副作用前拒绝 |
| 1 / DR02 | 规范路径、链接/祖先、源=目标或清理保护失败 | PATH_BOUNDARY；首个写入前拒绝全部请求 |
| 2 / DR03 | 初始化、已部署/input/cache/source 指纹缺失或漂移 | INITIALIZATION_UNAVAILABLE；保留目标，不打开 GUI |
| 3 / DR04 | 请求平台未经源初始化批准 | PLATFORM_NOT_APPROVED；目标不变 |
| 4 / DR05 | 实际 HEAD/G/W/K/Candidate/request/evidence 身份不同 | STALE_IDENTITY；不复用旧结果 |
| 5 / DR06 | 必需能力缺失/unknown/不可用/未批准/无适用成功证据 | BLOCKED；require_preflight 抛 CAPABILITY_UNAVAILABLE；不授权 dispatch 或升级 |
| 6 / DR07 | 显式支持且可用 actor，或已知可用当前贡献者平台 | 先显式选择，后当前平台；不套用另一厂商默认/缓存 |
| 7 / DR08 | 派生 checkout 的身份、初始化、平台、路径验证全部通过 | 仅 hydration 所选 discipline/cache，验证输出并返回实际 changed_paths |
| 8 / DR09 | 当前操作所需能力均有匹配可用且已授权证据 | READY；独立调用者 require_preflight 复核后才可继续，不表示功能验收 |
| 9 / DR10 | 所需目标能力恰是 #79 正在实现的未完成能力 | 不制造循环开发前提；继续按现有角色/输入纪律实现和测试 |

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-09-10 | 0.1.0 | 从 K0 独立呈现 R01–R23、公开接口和错误优先级，作为首次 Gate 1 需求参考。 |
