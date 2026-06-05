# 架构概览

## 整体架构

open-agent 采用分层、插件化的架构，核心是一条从用户输入到任务完成的管道：

```
用户请求
  → AgentRuntime（总编排器）
    → RoutingPipeline（复杂度 → 领域 → 意图）
      → PlanGenerator（可选规划）
        → ReActLoop（Thought → Action → Observation 循环）
          → ToolRegistry（工具注册 + 中间件管道）
            → Safety → Permission → Execute → Validate → Truncate
          → Checkpoint（步级状态持久化）
          → Recovery（错误恢复策略链）
        → Memory（4 层记忆更新）
      → Monitoring（异常检测 + 质量评分）
    → Response
```

## 核心组件关系

```
AgentRuntime
  ├── ModelProvider (OpenAI/Anthropic/DeepSeek/Local)
  ├── RoutingPipeline
  │   ├── ComplexityJudge (rule/llm)
  │   ├── DomainRouter (keyword matching)
  │   ├── IntentParser (rule/llm)
  │   └── UnifiedLLMRouter (optional single-call)
  ├── PlanGenerator
  ├── ReActLoop
  │   ├── ToolRegistry
  │   │   └── MiddlewareChain (5 layers)
  │   ├── CheckpointManager (JSON/SQLite)
  │   ├── RecoveryChain (4 strategies)
  │   └── HookManager (3 events)
  ├── MemoryFactory
  │   ├── RuntimeMemory (session context + compression)
  │   ├── ProfileMemory (SQLite user profile)
  │   ├── RetrievalMemory (vector episodic + semantic)
  │   └── ArchiveMemory (JSONL cold storage)
  ├── SafetyManager
  │   ├── CommandSafetyChecker
  │   ├── SSRFProtector
  │   ├── PathRestrictor
  │   └── HITLApprovalManager
  ├── PermissionGuard
  ├── SandboxFactory (subprocess/docker/daytona)
  ├── PromptBuilder (6 segments)
  ├── SkillRegistry + SkillMatcher
  ├── MCPServerManager (stdio/SSE/HTTP)
  ├── SubagentManager
  ├── Monitoring (AnomalyDetector + QualityScorer + FeedbackLoop)
  └── TraceManager (OTel-like)
```

## 关键设计决策

| ID | 决策 | 理由 |
|----|------|------|
| D1 | ReAct 循环 + 可选规划 | 平衡灵活性和可控性 |
| D2 | 4 层记忆架构 | 分离不同生命周期的上下文 |
| D3 | 3 级路由管道 | 渐进式任务理解和分级处理 |
| D4 | 场景化评估 | 可重现的质量验证 |
| D5 | 步级检查点 | 最小粒度的状态恢复 |
| D6 | 策略链恢复 | 可扩展的错误容忍 |
| D7 | OTel-like 追踪 | 标准化的可观测性 |
| D8 | MCP 集成 | 外部工具生态扩展 |
| D9 | Skill 系统 | 领域知识的动态注入 |

## 数据流

1. **用户输入** → RoutingPipeline → RoutingDecision
2. **RoutingDecision** → PromptBuilder → 系统 prompt
3. **系统 prompt + 对话历史** → ModelProvider.complete_with_tools() → LLM 响应
4. **LLM 响应** → ToolCalls → ToolRegistry.execute() → 中间件链 → 工具结果
5. **工具结果** → 追加到对话历史 → 回到步骤 3（ReAct 循环）
6. **循环结束** → 更新 Memory + Monitoring → 返回 AgentResponse

## 确定性停止条件

ReActLoop 在以下任一条件满足时停止：
- LLM 未返回工具调用（直接回答）
- 连续 3 次相同的 action batch
- 同一工具连续调用 4+ 次（tool loop）
- 同一错误连续出现 3+ 次
- 所有工具降级（各工具连续 3+ 次失败）
- 达到最大迭代次数（默认 10）

## 错误类型层级

```
AgentError
├── ToolError
│   ├── ParameterError    → ParameterRecoveryStrategy
│   ├── RetrievalError    → RetrievalRecoveryStrategy
│   ├── ServiceError      → ServiceRecoveryStrategy
│   └── ParseError        → ParseRecoveryStrategy
├── MemoryError
├── RoutingError
├── EvalError
├── DangerousOperationError
├── SSRFError
└── SecurityError
```
