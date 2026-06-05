# Harness Engineering 设计决策

## 设计哲学

open-agent 基于 Harness Engineering 原则：**模型能力强 ≠ 执行可靠**。框架的目标不是让模型变聪明，而是为模型建立一套闭环的工作系统。

核心参考：
- OpenAI: "Harness engineering: leveraging Codex in an agent-first world"
- Anthropic: "Effective harnesses for long-running agents"
- Anthropic: "Harness design for long-running application development"

## Harness 五大子系统对照

| 子系统 | 课程要求 | 当前实现状态 | 差距 |
|--------|---------|-------------|------|
| **指令** | AGENTS.md 路由 + topic docs | CLAUDE.md 支持（ClaudemdSegment） | 缺少路由架构和 SNR 优化 |
| **工具** | 最小权限 + 不过度限制 | Tool ABC + 12 内置工具 + MCP 扩展 | 基本完善 |
| **环境** | 自描述环境 | DynamicEnvSegment（date/platform/cwd） | 缺少项目级环境检测 |
| **状态** | PROGRESS.md + feature list | Checkpoint（执行级） | 缺少项目级状态和 WIP=1 |
| **反馈** | 验证命令 + 三层终止检查 | QualityScorer（后置评分） | 缺少前置验证门控 |

## 已实现的 Harness 机制

### 1. 确定性执行控制
- ReAct 循环的 6 种停止条件
- 工具健康追踪和降级
- 异常检测（tool loop、重复错误、超时）

### 2. 分层安全防护
- 命令安全检查（黑名单 + 正则）
- SSRF 防护（私有 IP + 云元数据 + DNS rebinding）
- 路径限制（工作空间边界 + 敏感文件保护）
- HITL 审批（3 级：Read 自动 / Write 确认 / Dangerous 阻断）
- 权限守卫（4 阶段管道：deny → mode → allow → ask）

### 3. 错误容忍
- 4 种恢复策略（参数/检索/服务/解析）
- 策略链模式（首个成功终止）
- 自定义策略注册
- Provider 降级链（FallbackChain）

### 4. 状态持久化
- 步级检查点（JSON/SQLite 存储）
- 恢复支持（从检查点继续执行）
- 4 层记忆（运行时/配置文件/检索/归档）

### 5. 可观测性
- OTel-like 追踪（Trace + Span）
- 结构化 JSON 日志
- 生命周期 Hook 系统
- 质量评分和反馈循环

## 尚未实现的 Harness 机制

详细差距分析见 [harness.md](../harness.md)。

### P0 关键缺口

1. **验证门控**：agent 可以在不运行测试的情况下声称任务完成
2. **项目级状态**：没有跨会话的进度跟踪和特性列表
3. **WIP=1 约束**：没有"一次只做一件事"和"必须证明完成"的机制

### P1 重要缺口

4. **指令路由架构**：没有任务感知的文档选择和 SNR 优化
5. **上下文焦虑管理**：没有检测和应对 agent "抢跑"行为
6. **初始化阶段**：没有独立的启动就绪检查

### P2 中等缺口

7. **双层可观测性**：缺少流程可观测（决策记录、Sprint 契约）
8. **质量漂移检测**：没有代码库质量趋势追踪
9. **Harness 简化**：没有定期测试组件必要性的机制

## 实现路线图

```
Phase 1: 反馈子系统 (verification/)
  → VerificationRegistry + VerificationGate + TerminationChecker

Phase 2: 状态子系统 (state/)
  → ProgressTracker + FeatureListManager + WIPLimiter

Phase 3: 指令 + 上下文
  → InstructionRouter + SNROptimizer + ContextAnxietyDetector

Phase 4: 初始化 + 可观测性
  → StartupReadinessChecker + DecisionLogger + QualityDocument
```
