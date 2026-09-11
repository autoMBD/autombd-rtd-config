# #79 开发环境能力与隔离：功能用例

| Field | Value |
| --- | --- |
| Version | 0.1.0 |
| Date | 2026-09-10 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | 供 Human Gate 1 审阅的简洁场景及预期结果。 |

| 用例 | 需求 | 场景 | 预期结果 |
| --- | --- | --- | --- |
| ENV-01 | R01、R18 | 公开模块及错误接口 | 公开 API 可调用；结构化错误可 JSON 序列化。 |
| ENV-02 | R02、R03 | 真实 linked worktree 与独立 clone | 正确区分共享引用/对象；两者均不凭 checkout 声称 OS 读取隔离。 |
| ENV-03 | R03 | 源存在无关分支/对象，创建精确提交的独立 clone | 仅保留请求分支，无 remote/alternates/对象硬链接；不能读取无关对象；源不变。 |
| ENV-04 | R03、R06 | 目标已存在、HEAD 错误、越界、源=目标或非法分支 | 拒绝且整个目标/源库存不变。 |
| ENV-05 | R03、R06 | 目标祖先 symlink 逃逸或检查 HEAD 过期 | 路径或身份错误，首个写入前拒绝。 |
| ENV-06 | R02 | 通过 alternates 共享对象的 clone | 标明共享对象，不能声称引用或 OS 隔离。 |
| ENV-07 | R04、R18 | 捕获有效真实部署状态 | 只读、确定性、可序列化；snapshot 内部格式不受用例限制。 |
| ENV-08 | R04、R06 | 输入摘要/文件/格式、缓存、生成角色或 Skill 链接无效 | 捕获拒绝，源文件/目录/链接库存不变。 |
| ENV-09 | R05、R06、R07 | 全部已批准平台中任选一个，目标尚无 ignored 文件 | 仅部署请求平台；规范 Skill 指向目标本地，外部 Skill 指向已验证源；重复操作无变化。 |
| ENV-10 | R06 | snapshot 摘要/格式、目标 HEAD、批准平台、源=目标、基目录或首次空目录错误 | 目标及外围库存保持不变，安全拒绝。 |
| ENV-11 | R05、R06 | 捕获后源输入/缓存/角色/资源/外部 Skill/HEAD 变化 | 旧捕获失效，不部分部署。 |
| ENV-12 | R06 | 目标所选平台目录链接到基目录外 | 写入前拒绝，链接目标和目标 checkout 均不变。 |
| ENV-13 | R07 | 源初始化曾 reset，派生目标已有无关 ignored 证据/角色 | 不重放 reset、不启动 GUI；无关文件保留。 |
| ENV-14 | R08 | 五种角色及按需 vendor/黑盒操作 | 读写/Git 基线正确；只加入所选服务，不强制其他厂商或 S32DS。 |
| ENV-15 | R08、R09、R10、R18 | 当前必需能力均可用且有授权，可选 S32DS 不可用 | 返回确定性 READY，输入不变；复核后调用者才写 dispatch 哨兵。 |
| ENV-16 | R09、R10 | 任一必需能力缺失、不可用、unknown 或未批准 | BLOCKED 且明确能力诊断；哨兵不能写入。 |
| ENV-17 | R10 | 逐一改变 task/G/W/K/root/HEAD/Candidate 或 request 摘要 | 过期报告不能授权 dispatch。 |
| ENV-18 | R10 | observation 的 task 身份与 request 不同 | 拒绝消费过期观测。 |
| ENV-19 | R09、R18 | 版本、角色、平台、隔离模式、重复或未知能力错误 | 结构化 INVALID_INPUT。 |
| ENV-20 | R02、R08、R09 | 要求 input 隔离，仅有 clone；随后提供显式可信适配观测 | clone 本身 BLOCKED；可消费独立适配观测，不把本 synthetic 输入当 OS 证明。 |
| ENV-21 | R12 | sandbox 失败，connector/host 的可用及授权组合不同 | 优先 connector，再已授权 host-cli；均不可用时 BLOCKED，模式不混淆。 |
| ENV-22 | R11、R18 | 真实命令读取关闭的 stdin，argv 含 shell 特殊字符并输出 canary | 字面 argv 安全传递；仅返回 stdout/stderr 摘要，不泄漏原文。 |
| ENV-23 | R11 | 真实非零退出和超时命令 | 返回真实 unavailable/exit/timed_out，命令结束有界。 |
| ENV-24 | R09、R11 | 探针未授权、argv/cwd/context/deadline 无效 | spawn 前拒绝，进程副作用哨兵不存在。 |
| ENV-25 | R13 | 三家当前平台各自单独可用，或显式改选另一已用平台 | 选当前平台；显式可用选择优先。 |
| ENV-26 | R13 | 贡献者未知/歧义、当前或显式 actor 不可用 | 明确报错，不静默换厂商。 |
| ENV-27 | R13、R14 | 当前平台与上一贡献者缓存不同 | harness 选当前平台并返回真实 current-platform 来源；显式 flag 保持优先。 |
| ENV-28 | R14 | 注册表及 CLI 的平台选择面 | 三家均可选择，保留 adapter 协议并暴露 --current-platform。 |
| ENV-29 | R10、R16、R18 | 源及被引用证据均未改变 | 不透明 snapshot 正常验证，验证本身只读。 |
| ENV-30 | R10、R16 | 证据改写/缺失，HEAD/暂存/未暂存/未追踪源或绑定变化 | 旧证据被判 stale。 |
| ENV-31 | R16 | 脏源的状态名称不变，但实际字节变化 | 仍判 stale，不能仅比较 dirty 布尔值。 |
| ENV-32 | R16 | 同证据范围新增 ignored 文件，以及改写原绑定文件 | 仅明确 allowlist 新文件可接受；allowlist 不能豁免旧绑定字节改变。 |
| ENV-33 | R16、R17 | allowlist 指向源、.git、路径逃逸或根 | 不得借证据 allowlist 授权源/越界路径。 |
| ENV-34 | R17 | 只命名当前临时目录，先计划后执行 | 默认 PLANNED 不删除；显式执行仅删目标，保留无关证据、源和 HEAD。 |
| ENV-35 | R17 | 有效清理项后跟根、.git、源文件或逃逸项 | 整个请求预验证失败，前面的有效项也不能先删。 |
| ENV-36 | R17 | 被保护子证据与指向外部的允许链接 | 保护子证据；仅解除允许的链接本身，不删除目标；拒绝经链接删子项。 |
| ENV-37 | R09、R10、R18 | API 和 JSON CLI 的 preflight、verify、inspect 正常链 | CLI/API 一致，成功退出 0，输入文件不被写入。 |
| ENV-38 | R09、R18 | CLI BLOCKED、非法 JSON、缺失输入 | 分别退出 1、2、2；安全结构化诊断，无 traceback。 |
| ENV-39 | R04、R05、R06 | CLI capture→hydrate 正常链 | 读源无变化；仅调用者发布 snapshot；hydrate 返回真实结果。 |
| ENV-40 | R01、R08、R18、R19、R22 | 公开参考与可移植入口 | 文档覆盖公开 API/平台/证据限度，入口保持标准库优先和统一 MIT 头。 |
| ENV-41 | R19、R20、R21、R23 | 独立需求、用例、索引与脚本审阅面 | R01–R23 和全部 case ID 可追溯；过程独立性由交接/源证据保留，不伪造 OS 隔离。 |
| ENV-42 | R04、R05、R09、R10、R11、R16 | 创建→hydration→真实探针→READY→调用者哨兵→证据绑定/失效 | 整条所选链实际运行；过期身份不能再 dispatch，改写绑定证据被拒绝。 |
| ENV-43 | R01、R15、R19、R22、R23 | 既有 workflow 权威与实际 vendor/黑盒纪律 | 固定 W/注册表/schema/纯转换/evidence verifier 不变；保留独立 CLI 黑盒及退出 0+零 SEVERE 规则。 |

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-09-10 | 0.1.0 | 从公开 K0 独立推导首次 Gate 1 用例；执行方法及预验证证据另存脚本/报告。 |
