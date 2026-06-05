## Parent

PRD-04: 存储层碎片化治理 — JSON 散落文件整合为 JSONL / SQLite

## What to build

为 eval 和 trace 子系统新增 retention（保留条数）配置。在 `AgentConfig` 中新增 `EvalConfig` 子模型（含 `results_retention` 和 `trajectories_retention`），在 `TraceConfig` 中新增 `trace_retention` 字段。这些配置将作为后续 JSONL 追加写入时自动清理的依据。

完成后效果：开发者可通过配置文件或环境变量自定义各存储的保留条数（如 CI 环境设为 500，开发环境保持默认 100）。

## Acceptance criteria

- [ ] 新增 `EvalConfig(BaseModel)` 类，含 `results_retention: int = Field(default=100, ge=1)` 和 `trajectories_retention: int = Field(default=200, ge=1)`
- [ ] `AgentConfig` 新增 `eval: EvalConfig = Field(default_factory=EvalConfig)` 字段
- [ ] `TraceConfig` 新增 `trace_retention: int = Field(default=100, ge=1)` 字段
- [ ] 环境变量覆盖：`OPEN_AGENT_EVAL_RESULTS_RETENTION`、`OPEN_AGENT_EVAL_TRAJECTORIES_RETENTION`、`OPEN_AGENT_TRACE_RETENTION` 映射到对应字段
- [ ] 配置可通过 YAML 文件正常加载
- [ ] 现有测试全部通过（新字段有合理默认值，不影响现有行为）
- [ ] 新增测试：验证默认值、环境变量覆盖、YAML 加载

## Blocked by

None — can start immediately.

## User Stories

US 10, 13
