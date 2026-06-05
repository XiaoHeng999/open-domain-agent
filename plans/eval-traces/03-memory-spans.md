# Issue 03: Memory 子系统可观测（MEMORY_OP spans）

## What to build

让 memory 子系统的核心操作被 trace 覆盖，使其可观测。

端到端行为：当 agent 执行任务时，每次 memory 读写操作（添加消息、压缩上下文、检索记忆、写入档案、加载/保存用户画像）都会在当前 trace 中创建一个 `MEMORY_OP` 类型的 span，记录操作类型、关键属性和耗时。通过 `agent trace <id>` 查看时，能看到 memory 操作的完整链路。

注入方式：Runtime 在每次 `run()` 开始时向各 memory 实例注入 `_trace_manager` 和 `_current_trace_id` 属性，`run()` 结束时清除。Memory 子系统通过这两个属性定位当前 trace，按需创建 span。不修改 MemoryManager ABC 接口。

需要覆盖的 memory 操作：
- RuntimeMemory: add_message（写）、_maybe_compress（压缩）
- ProfileMemory: load（读）、save（写）
- RetrievalMemory: query（检索）、write_episodic（写入情景记忆）
- ArchiveMemory: write_record（写入档案）

## Acceptance criteria

- [ ] RuntimeMemory.add_message 创建 MEMORY_OP span，属性包含 operation=write、role、content_length
- [ ] RuntimeMemory._maybe_compress 创建 MEMORY_OP span，属性包含 operation=compress、messages_compressed
- [ ] ProfileMemory.load 创建 MEMORY_OP span，属性包含 operation=profile_read
- [ ] ProfileMemory.save 创建 MEMORY_OP span，属性包含 operation=profile_write
- [ ] RetrievalMemory.query 创建 MEMORY_OP span，属性包含 operation=retrieval_query、top_k、results_count
- [ ] RetrievalMemory.write_episodic 创建 MEMORY_OP span，属性包含 operation=episodic_write
- [ ] ArchiveMemory.write_record 创建 MEMORY_OP span，属性包含 operation=archive_write
- [ ] 所有 span 在操作完成后调用 finish()
- [ ] tracing 关闭时（无 _trace_manager 或 _current_trace_id）零开销，不创建 span
- [ ] 运行一次任务后，持久化的 trace JSON 中包含 `"kind": "memory_op"` 类型的 span

## Blocked by

- Issue 01: Trace 持久化（需要 trace 能写入磁盘才能验证）

## User stories

- #6 memory 子系统的读写操作被 trace 覆盖
