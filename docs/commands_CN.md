# 命令参考

## 工具列表

| 工具 | 功能 |
|------|------|
| `rf-start` | 启动工作流 |
| `rf-status` | 查看当前工作流状态 |
| `rf-continue` | 恢复暂停的工作流 |
| `rf-cancel` | 取消工作流并生成报告 |
| `rf-list` | 列出可用工作流 |
| `rf-detect` | 检测工作流标记 |

---

## rf-start

启动工作流。

### 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `workflow` | string | 是 | 工作流名称 |
| `task` | string | 是 | 任务描述 |

### 使用示例

```json
// 启动 loop 工作流
{"workflow": "loop", "task": "实现用户认证模块"}

// 启动 spec 工作流
{"workflow": "spec", "task": "添加 OAuth2 用户认证功能"}
```

### 返回值

```json
{
  "success": true,
  "message": "Workflow 'loop' started.",
  "task": "实现用户认证模块",
  "first_step": {
    "id": "loop",
    "desc": "自动循环执行任务"
  },
  "do_instruction": "Execute the task and output <promise>done</promise> when complete."
}
```

---

## rf-status

查看当前工作流状态。

### 参数

无参数。

### 返回值

```json
{
  "status": "active",
  "workflow_name": "loop",
  "current_step": "loop",
  "current_phase": "do",
  "fail_count": 0,
  "user_task": "实现用户认证模块",
  "paused": false,
  "step_details": {
    "desc": "自动循环执行任务",
    "do": "执行用户指定的任务...",
    "check": "按以下步骤精确验证..."
  }
}
```

---

## rf-continue

恢复已暂停的工作流。

### 参数

无参数。

### 使用场景

- 工作流因达到最大失败次数而暂停
- 用户修复问题后想继续执行

### 返回值

```json
{
  "success": true,
  "message": "Workflow 'loop' resumed.",
  "current_step": {
    "id": "loop",
    "desc": "自动循环执行任务"
  },
  "previous_failure_reason": "检查失败：代码有 bug",
  "do_instruction": "Execute the task and output <promise>done</promise> when complete."
}
```

---

## rf-cancel

取消当前工作流。

### 参数

无参数。

### 返回值

```json
{
  "success": true,
  "message": "Workflow 'loop' cancelled.",
  "report": ".trae/skills/ralpha-loop-workflow/logs/cancellation-20260617-231036.json"
}
```

---

## rf-list

列出所有可用工作流。

### 参数

无参数。

### 返回值

```json
{
  "workflows": [
    {
      "name": "loop",
      "description": "单步骤循环执行，适合简单任务的持续迭代直到完成"
    },
    {
      "name": "spec",
      "description": "完整的需求分析、规格定义、技术设计、代码实现工作流"
    }
  ]
}
```

---

## rf-detect

检测工作流标记。

### 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `text` | string | 是 | 要检测的文本内容 |

### 使用示例

```json
// 检测 DO 阶段完成标记
{"text": "任务已完成\n<promise>done</promise>"}

// 检测 CHECK 阶段结果标记
{"text": "检查通过\n<promise-check>true</promise-check>"}
```

### 返回值

```json
{
  "done_detected": true,
  "check_result": {
    "found": false,
    "passed": null,
    "reason": ""
  }
}
```

或

```json
{
  "done_detected": false,
  "check_result": {
    "found": true,
    "passed": true,
    "reason": "所有检查点通过"
  },
  "suggestion": "Check passed. Consider advancing to next step."
}
```

---

## 日志事件

事件以 JSON 格式记录到 `.trae/skills/ralpha-loop-workflow/logs/` 目录。

### 工作流事件

| 事件 | 说明 |
|------|------|
| `workflow_start` | 工作流开始 |
| `workflow_end` | 工作流结束 |
| `workflow_paused` | 工作流暂停（达到最大失败次数） |
| `workflow_resumed` | 工作流被用户恢复 |
| `workflow_cancelled` | 工作流被用户取消 |

### 步骤事件

| 事件 | 说明 |
|------|------|
| `step_start` | 步骤阶段开始 |
| `done_detected` | 检测到完成标记 |
| `check_result` | 检查结果 |
| `fail_count_increment` | 失败计数增加 |

---

## 状态文件

工作流状态保存在 `.trae/skills/ralpha-loop-workflow/state.json`：

```json
{
  "active": true,
  "workflow_name": "loop",
  "current_step": "loop",
  "current_phase": "do",
  "fail_count": 0,
  "user_task": "用户任务描述",
  "paused": false,
  "last_failure_reason": null,
  "start_time": "2026-06-17T10:30:00"
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `active` | boolean | 工作流是否激活 |
| `workflow_name` | string | 工作流名称 |
| `current_step` | string | 当前步骤 ID |
| `current_phase` | string | 当前阶段（do/check） |
| `fail_count` | number | 当前失败次数 |
| `user_task` | string | 用户任务描述 |
| `paused` | boolean | 是否暂停 |
| `last_failure_reason` | string | 上次失败原因 |
