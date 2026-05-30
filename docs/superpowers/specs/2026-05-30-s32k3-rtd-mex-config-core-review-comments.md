# Review Comments Archive

This file preserves the user's review comments for
`2026-05-30-s32k3-rtd-mex-config-core-design.md`. These comments are design
input and should remain available for future spec, roadmap, reference, and test
document updates.

## Preserved Comments

<!-- REVIEW: 人机合作指的是是这个工具开发过程中我会和你一起，而不是这个工具是用于人机合作的，这个工具的目标是让AI Agent可以直接使用并自主完成RTD配置，具备快速、高效、准确性和稳定性。 -->

<!-- REVIEW: 你在Purpose中提第一阶段的、限制功能的内容，不利于后续扩展新模块、新芯片平台。目标要写清除，第一阶段可以的限制、可以在计划、路线图中说明。 -->

<!-- REVIEW: 目标要说明完整的计划，即要支持RTD的全部模块（不仅仅是driver模块，还应包括官方的RTD RTOS、Stacks、外围芯片的driver），要支持.mex（S32 ConfigTools）和（xmd（EB Tresos），要支持扩展跟多芯片（K1、K5等），要支持扩展新版的RTD。 -->

<!-- REVIEW: 同样，在Spec中不要提及第一阶段、限制等 -->

<!-- REVIEW: 不太明白这里提到的AI Agent workflow platform是什么，我希望在这个项目开发过程中你可以实现可以闭环的开发、测试工作流，这很重要。但这套流程可能需要更多的支撑（例如skills），当前不太完善，需要逐步添加更多支撑。所以我说我会以人机合作的方式辅助你，但辅助你的核心方向是让你实现闭环的开发、测试工作流。此外这个部分并不属于项目的spec内容，它应该是一种独立于项目的开发模式，你需要知道清楚，把这部分内容单独放到一个文件里。 -->

<!-- REVIEW: 关于第一阶段的计划和限制，放到实施计划和路线图中说明 -->

<!-- REVIEW: .mex文件可能会非常庞大，这里解析和构建index要考虑效率问题，我觉得runtime时解析可能不可靠，但我们可以先验证看看效果如何，再分析最优方案。 -->

<!-- REVIEW: Module providers需要考虑不太模块之间的依赖和关联，例如FlexIO Uart依赖Mcl，中断模式依赖Platform使能ISR和设置优先级 -->

<!-- REVIEW: Module providers还需要考虑配置项的限制约束条件，比如不同型号芯片的可用引脚数量不同，可用外设数量也不同。RTD安装目录下，每个模块内有相应的文件描述模块配置依赖和约束，例如Uart："C:\NXP\S32DS.3.6.7\S32DS\software\PlatformSDK_S32K3\RTD\Uart_TS_T40D34M70I1R0\config\Uart.xdm" -->

<!-- REVIEW: 开发过程中引用的材料、文件（例如我给你excel文件、driver模块的约束限制文件等），一定不能出现再代码中，也不能在runtime时引用，这个工具的作用就是提前将所需的一切准备好，以实现高效、快速、准确的自主配置。 -->

<!-- REVIEW: 这是一个Spec，写怎么做就行了，不要提什么PoC的问题。 -->

<!-- REVIEW: 上面这些Module Responsibilities，单独写一张表，并且支持支持维护更新，支持后续添加新模块 -->

<!-- REVIEW: 同样，不要在Spec中提phase1，在实施计划和路线图中说明 -->

<!-- REVIEW: 在实施计划和路线图中说明Port第一阶段就要实现完整、通用的功能 -->

<!-- REVIEW: 不要在Spec中把参考引用资料写死，可用新增一个Reference的文档，spec中只说明需要引用什么，在哪里找即可 -->

<!-- REVIEW: 同样，mex文件编写一定要考虑效率问题，后续的.xdm文件的编辑可用放一个简略版 -->

<!-- REVIEW: Spec中不要指定特定的工程，描述fixtures通用结构即可 -->

<!-- REVIEW: 开发过程中，所有模块的验证都是这样的，今后的验证方式也是这样的，不仅仅是phase1，不要在Spec中提phase1 -->

<!-- REVIEW: 需要单独的测试文档来说明不同模块的测试过程，测试文档中需要详细写测试案例（test case），不要在Spec中描述特定模块的测试要求，Spec要说明完成测试文档要求的测试内容 -->

<!-- REVIEW: 这部分放到测试文档中说明，属于测试流程 -->

<!-- REVIEW: 这个KPI是所有模块配置的KPI，需要单列小结中描述 -->

<!-- REVIEW: 同样的，不要在Spec中提Phase1 -->

<!-- REVIEW: 验收应该以测试文档和测试结果为标准，简单来说就两个：1）满足KPI；2）测试案例通过 -->

<!-- REVIEW: 测试文档也需要不同阶段设置，支持可维护、可更新、可扩展 -->

<!-- REVIEW: 下面是总结，很重要！！ -->

<!-- REVIEW: 总的来说，Spec一开始要尽可能的完整、详尽，Spec需要可维护、可更新、可迭代，我们讨论的第一阶段的有限功能开发在制定计划的时候说明清楚，而不是在Spec中。 -->

<!-- REVIEW: 当前Spec需要新增一些文件来增强可维护性，包括参考文件、测试文件等，详见上面的comments -->

<!-- REVIEW: 要区分开发模式和Spec，开发模式可能会因为不可预测的问题改变路线，而Spec是描述项目本身的目标、功能、技术栈等信息，是我们开发的指南针 -->

<!-- REVIEW: 要注意开发过程中的工具资源引用和runtime时的资源调度和依赖，不能把开发过程中调用、依赖的一些文件带到runtime时使用，因为runtime环境是不确定的。例如pin映射表，开发过程中你会引用我给你的excel表，在工具内构建映射、查找关系，runtime时就不再需要这个excel表了。 -->
