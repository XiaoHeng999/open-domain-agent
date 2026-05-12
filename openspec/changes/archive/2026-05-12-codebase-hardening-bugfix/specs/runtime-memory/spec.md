## MODIFIED Requirements

### Requirement: RuntimeMemory 执行状态管理
`RuntimeMemory._task_state` SHALL 通过公开的 `task_state` property 访问，外部代码 SHALL NOT 直接赋值 `_task_state` 私有属性。AgentRuntime 等外部组件 SHALL 通过 `reset_task_state()` 等公开方法操作 task state。

#### Scenario: ReAct loop 重置 task state
- **WHEN** ReAct loop 开始新一轮执行，需要重置 task state
- **THEN** SHALL 调用 `runtime_memory.reset_task_state()` 而非 `runtime_memory._task_state = TaskState()`

### Requirement: RuntimeMemory 工具调用结果缓存
`BaseComponent` 基类的 `_registered` 和 `_started` SHALL 为实例变量而非类变量，每个组件实例 SHALL 拥有独立的生命周期状态。

#### Scenario: 两个组件独立启停
- **WHEN** 创建两个 BaseComponent 子类实例 A 和 B，调用 A.on_start()
- **THEN** A._started SHALL 为 True，B._started SHALL 为 False（互不影响）
