#!/usr/bin/env python3
"""
rf-check tool - Generate adversarial check prompt for independent sub-agent.
Reads current step's check criteria and builds a verification prompt
that should be passed to a Task sub-agent for independent validation.
"""
import json
import sys
from pathlib import Path

# Add tools dir to path for rf_lib imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from rf_lib.paths import get_skill_dir
from rf_lib.state import read_state
from rf_lib.workflow import load_workflow, get_step, is_sub_workflow_step
from rf_lib.logging import log_step_start, log_error

# Default adversarial check system prompt (same as original opencode version)
DEFAULT_ADVERSARIAL_SYSTEM_PROMPT = """
你是一个严格的检查者。你的职责是根据检查依据判断任务是否完成。

## 核心原则

1. 只审查，不修改
2. 严格按照"检查依据"判断，不要被其他因素干扰
3. 如果有任何疑问，判定为不通过

## 验证方法

你必须**自主探索**项目来验证任务是否完成：
- 根据任务类型，选择合适的验证方式
- 基于检查依据中的要求，逐一验证每一项
- 不要依赖任何外部提供的"实现总结"，只基于你自己的验证结果判断

## 判断逻辑

**通过条件**：检查依据中的每一项都满足
**不通过条件**：检查依据中任何一项不满足

## 输出格式

- 通过：先说明通过原因，最后一行输出 <promise-check>true</promise-check>
- 不通过：先说明失败原因，最后一行输出 <promise-check>false</promise-check>

标签必须独占最后一行。
"""


def build_check_prompt(step: dict, user_task: str = "") -> str:
    """Build the adversarial check prompt for a step."""
    sections = []

    if user_task:
        sections.append(f"""## 用户需求

{user_task}""")

    sections.append(f"""## Do 阶段任务

**步骤**：{step.get('id', 'unknown')}
**任务描述**：{step.get('do', '')}
**输入**：{step.get('input', '')}
**预期输出**：{step.get('output', '')}""")

    sections.append("---")

    sections.append(f"""## 检查依据

{step.get('check', '')}

---

请基于上述信息，自主探索项目验证任务完成情况。基于你自己的探索结果判断，不要依赖任何外部提供的"实现总结"。

检查完成后输出：
- 通过：先说明通过原因，最后一行输出 `<promise-check>true</promise-check>`
- 不通过：先说明失败原因，最后一行输出 `<promise-check>false</promise-check>`

标签必须独占最后一行。""")

    return "\n\n".join(sections)


def main():
    skill_dir = get_skill_dir(__file__)

    # Read optional input
    try:
        input_data = json.load(sys.stdin)
    except Exception:
        input_data = {}

    user_task_override = input_data.get('user_task', '')

    # Read state
    state = read_state(skill_dir)
    if not state:
        print(json.dumps({'error': 'No workflow state found.'}, ensure_ascii=False))
        return

    if not state.get('active', False):
        print(json.dumps({'error': 'No active workflow.'}, ensure_ascii=False))
        return

    workflow_name = state.get('workflow_name', '')
    current_step_id = state.get('current_step', '')
    user_task = user_task_override or state.get('user_task', '')

    # Load workflow
    workflow = load_workflow(skill_dir, workflow_name)
    if not workflow:
        print(json.dumps({'error': f"Workflow '{workflow_name}' not found."}, ensure_ascii=False))
        return

    step = get_step(workflow, current_step_id)
    if not step:
        print(json.dumps({'error': f"Step '{current_step_id}' not found in workflow."}, ensure_ascii=False))
        return

    # Sub-workflow steps don't have check prompts
    if is_sub_workflow_step(step):
        print(json.dumps({'error': f"Step '{current_step_id}' is a sub-workflow step, not a checkable step."}, ensure_ascii=False))
        return

    # Build check prompt
    check_prompt = build_check_prompt(step, user_task)

    # Get adversarial check config
    adv_config = workflow.get('adversarial_check') or {}
    system_prompt = adv_config.get('system_prompt') or DEFAULT_ADVERSARIAL_SYSTEM_PROMPT
    timeout_ms = adv_config.get('timeout_ms', 900000)  # 15 minutes default
    timeout_minutes = round(timeout_ms / 60000)

    # Log
    log_step_start(skill_dir, current_step_id, 'check')

    # Return result
    result = {
        'success': True,
        'step_id': current_step_id,
        'system_prompt': system_prompt,
        'check_prompt': check_prompt,
        'timeout_minutes': timeout_minutes,
        'instruction': (
            f"请使用 Task 工具创建一个独立的子 agent，将 system_prompt 作为系统提示，"
            f"将 check_prompt 作为用户消息发送给子 agent。"
            f"子 agent 的超时时间为 {timeout_minutes} 分钟。"
            f"子 agent 返回结果后，使用 rf-detect 检测结果中的 <promise-check> 标记。"
        )
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
