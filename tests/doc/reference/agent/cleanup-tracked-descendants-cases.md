# Cleanup 受跟踪后代保护用例

| Field | Value |
| --- | --- |
| Version | 0.1.0 |
| Date | 2026-09-11 |
| Author | autoMBD <tkung.lqk@foxmail.com> (AI-assisted) |
| Description | #112 的简洁功能用例审阅表。 |

| 用例 ID | 需求 ID | 场景 | 预期结果 |
| --- | --- | --- | --- |
| CTD-01 | R01、R03 | 两个允许存储根下，受跟踪后代分别处于已提交、仅暂存、先跟踪后 ignore、assume-unchanged 状态，且工作树含未提交字节；两种 dry-run。 | 整批以 PATH_BOUNDARY 拒绝；原始文件、index、Git 对象与证据字节均保留。 |
| CTD-02 | R01、R02、R03 | 混合计划中的受跟踪目录位于首、中、尾位置，使用 index 拼写或 Windows 上指向同一对象的大小写别名；两种 dry-run。 | 合法临时目标也全部保留，首次删除不能早于整批验证。 |
| CTD-03 | R01、R03、R07 | 受跟踪路径含空格、方括号、标点、非 ASCII 和多级目录，并覆盖 Windows 上指向同一对象的大小写别名；两种 dry-run。 | 按实际目录边界发现源内容并拒绝，所有原始字节不变。 |
| CTD-04 | R04、R07 | 不同种子产生多组合法临时目录；相似前缀的兄弟目录含受跟踪内容。 | 只清理明确指定的合法临时目录；不误报兄弟前缀，不改其源或 Git index。 |
| CTD-05 | R03、R04 | 两个允许存储根下的普通临时文件/目录，旁边保留绑定证据；先使用默认参数，再显式执行。 | 公开签名、默认 dry-run 和结果格式保持；计划无修改，执行仅删除所列目标。 |
| CTD-06 | R04、R05 | 独立 leaf 与目录内的 file symlink、directory symlink、junction 指向目标树外的数据。 | 计划保留全部内容；执行删除指定链接/目录，不跟随或修改链接目的地。 |
| CTD-07 | R01、R02、R03、R05 | 目标目录内链接自身受跟踪，或链接被明确保护；混合计划含普通临时目标。 | 整批以 PATH_BOUNDARY 拒绝；链接、目的地和先前临时目标均保留。 |
| CTD-08 | R02、R03、R06 | 计划涉及源根、Git 存储、base 本身、base 外目标、逃逸、嵌套仓库、重叠目标或保护路径交集。 | 两种 dry-run 均拒绝整批且无任何字节变化。 |
| CTD-09 | R02、R03、R05、R06 | 文件目标的祖先是 directory symlink 或 junction，计划中另含合法临时目标。 | 拒绝遍历链接祖先，保留所有目标和目的地。 |
| CTD-10 | R02、R03、R07 | 真实 Git index 损坏使 Git 查询失败，计划含多个临时目标；两种 dry-run。 | 沿用既有 EnvironmentError 拒绝整批，不将查询失败当空 inventory，不改文件或损坏的 index；不限定查询顺序或唯一错误码。 |
| CTD-11 | R01、R02、R03 | 忽略父目录下的受跟踪 leaf 文件自身成为清理目标。 | 两种 dry-run 均以 PATH_BOUNDARY 拒绝整批，保留未提交字节。 |
| CTD-12 | R02、R04、R06 | dry_run 为 None、整数、字符串或列表。 | 保留 INVALID_INPUT 的布尔类型校验，拒绝且不修改目标。 |
| CTD-13 | R03、R04、R05 | 未跟踪合法 leaf symlink/junction 指向仓库内受跟踪且明确保护的文件或目录。 | 允许移除链接本身；受保护源与 index 保持原始字节。 |
| CTD-14 | R08 | 需求/用例交付、公开来源关联和相对 G 的改动范围。 | 完整保留 K0 的需求文字与来源，用例有自动化对应；改动限定已声明的源、文档和 Test/Worker generality 文件，生产变更伴随公开 cleanup 文档更新。 |

## Changelog

| Date | Version | Description |
| --- | --- | --- |
| 2026-09-11 | 0.1.0 | 建立 #112 独立功能用例表。 |
