# 自定义工作流

在 `.trae/skills/ralpha-loop-workflow/workflows/` 目录下创建 `.yaml` 文件即可定义自己的工作流。

---

## 快速示例

```yaml
description: 两步开发工作流

steps:
  - id: analyze
    desc: 需求分析
    do: 分析用户需求并输出设计文档
    input: 用户需求描述
    output: design.md
    check: 验证设计文档是否完整、技术方案是否合理
    on_pass: execute
    on_fail: analyze
    max_fail_count: 3

  - id: execute
    desc: 代码开发
    do: 根据设计文档实现代码
    input: design.md
    output: 可工作的代码
    check: 运行测试并验证实现
    on_pass: done
    on_fail: execute
    max_fail_count: 5
```

---

## 步骤字段参考

| 字段 | 必填 | 说明 |
|------|------|------|
| `id` | ✅ | 步骤唯一标识 |
| `desc` | ✅ | 步骤描述 |
| `do` | ✅ | 任务执行提示词 |
| `input` | ✅ | 预期输入说明 |
| `output` | ✅ | 预期输出说明 |
| `check` | ✅ | 验证标准 |
| `on_pass` | ✅ | 通过后的下一步（步骤 id 或 `"done"` 表示完成） |
| `on_fail` | ✅ | 失败后的下一步（步骤 id） |
| `max_fail_count` | ✅ | 最大失败次数（每个步骤独立） |

---

## 工作流级选项

### `description`

工作流描述，会在 `rf-list` 输出中显示：

```yaml
description: 这是一个自定义工作流
```

---

## 完成标记

AI 通过 XML 风格的标记来标识完成状态：

| 阶段 | 标记 | 说明 |
|------|------|------|
| DO 执行阶段 | `<promise>done</promise>` | 任务完成 |
| CHECK 检查阶段 | `<promise-check>true</promise-check>` | 验证通过 |
| CHECK 检查阶段 | `<promise-check>false</promise-check>` | 验证未通过 |

> 标记**不区分大小写**，允许空格。`<promise>DONE</promise>` 同样有效。

---

## 多步骤流转设计

### 线性流转

最简单的模式 —— 步骤按顺序执行：

```yaml
steps:
  - id: design
    desc: 设计阶段
    do: 创建技术设计文档
    input: 用户需求
    output: 设计文档
    check: 验证设计完整性
    on_pass: implement
    on_fail: design
    max_fail_count: 3

  - id: implement
    desc: 实现阶段
    do: 根据设计编写代码
    input: 设计文档
    output: 可工作的代码
    check: 运行测试
    on_pass: done
    on_fail: implement
    max_fail_count: 5
```

### 分支流转

步骤可以根据检查结果跳转到不同步骤：

```yaml
steps:
  - id: analyze
    desc: 分析问题
    do: 判断是 bug 修复还是新功能
    input: 用户描述
    output: 分析报告
    check: 分析是否正确？
    on_pass: implement
    on_fail: clarify
    max_fail_count: 2

  - id: clarify
    desc: 请求澄清
    do: 向用户询问更多细节
    input: 分析报告
    output: 详细需求
    check: 用户是否提供了足够信息？
    on_pass: analyze
    on_fail: clarify
    max_fail_count: 3

  - id: implement
    desc: 实现修复
    do: 编写代码
    input: 详细需求
    output: 可工作的代码
    check: 是否正常工作？
    on_pass: done
    on_fail: implement
    max_fail_count: 5
```

### 恢复流转

使用 `on_fail` 路由到专门的恢复步骤：

```yaml
steps:
  - id: build
    desc: 构建项目
    do: 执行构建流程
    input: 源代码
    output: 构建产物
    check: 构建是否成功？
    on_pass: test
    on_fail: fix-build
    max_fail_count: 2

  - id: fix-build
    desc: 修复构建错误
    do: 读取错误输出并修复问题
    input: 构建错误日志
    output: 修复后的代码
    check: 构建是否通过？
    on_pass: test
    on_fail: fix-build
    max_fail_count: 5

  - id: test
    desc: 运行测试
    do: 执行测试套件
    input: 构建产物
    output: 测试报告
    check: 所有测试是否通过？
    on_pass: done
    on_fail: fix-tests
    max_fail_count: 3

  - id: fix-tests
    desc: 修复失败的测试
    do: 分析测试失败原因并修复
    input: 测试失败日志
    output: 修复后的代码
    check: 测试是否通过？
    on_pass: done
    on_fail: fix-tests
    max_fail_count: 5
```

### 循环流转（回退）

使用 `on_fail` 回退到前面的步骤，形成循环：

```yaml
steps:
  - id: design
    desc: 设计
    do: 创建技术设计
    input: 用户需求
    output: 设计文档
    check: 设计是否完整合理？
    on_pass: implement
    on_fail: design
    max_fail_count: 3

  - id: implement
    desc: 实现
    do: 根据设计编写代码
    input: 设计文档
    output: 可工作的代码
    check: 代码能否通过编译和 lint？
    on_pass: test
    on_fail: design          # 实现发现问题时回退到设计
    max_fail_count: 3

  - id: test
    desc: 测试
    do: 运行完整测试套件
    input: 可工作的代码
    output: 测试报告
    check: 所有测试是否通过？
    on_pass: done
    on_fail: implement       # 测试失败时回退到实现
    max_fail_count: 5
```

形成循环：`design → implement → test → implement → test → ...`

如果实现发现设计有问题，回退到 `design`；如果测试失败，回退到 `implement`。工作流自然收敛到可工作的解决方案。

---

## 验证配置

CHECK 阶段使用独立会话进行验证。你可以通过 SKILL.md 中的说明配置验证方式。

### 独立验证原则

1. **无自我审查偏差** — 检查者没有实现过程的记忆
2. **严格验证** — 仅根据检查标准判断，不受 AI "意图" 影响
3. **干净的上下文** — 没有可能影响判断的累积上下文

### 使用 Task 工具创建验证会话

在 CHECK 阶段，使用 Task 工具创建一个独立的子 agent 进行验证：

```
1. 使用 Task 工具创建子 agent
2. 子 agent 没有执行过程的记忆
3. 子 agent 根据检查标准验证
4. 子 agent 输出验证结果和标记
5. 使用 rf-detect 检测结果
```

---

## 使用建议

- **保持步骤聚焦** — 每个步骤只做一件事
- **使用描述性的 `desc`** — 会显示在状态输出中
- **设置合理的 `max_fail_count`** — 太低会频繁暂停，太高浪费资源
- **编写清晰的 `check` 提示词** — 验证质量取决于你对"完成"的描述
- **使用分支流转** — 将失败路由到专门的修复步骤，而不是盲目重试
