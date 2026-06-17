#!/usr/bin/env python3
"""
rf-start tool - Start a workflow.
Supports sub-workflow, session tracking, auto-cleanup, logging.
"""
import json
import sys
from pathlib import Path
from datetime import datetime

# Add tools dir to path for rf_lib imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from rf_lib.paths import get_skill_dir
from rf_lib.state import read_state, write_state, clear_state, get_stack_depth
from rf_lib.workflow import load_workflow, get_step, is_sub_workflow_step, list_workflows
from rf_lib.logging import log_workflow_start, log_step_start, log_error, log_info
from rf_lib.report import clear_step_records


def _build_do_prompt(step: dict, user_task: str = "", retry_context: str = "", retry_count: int = 0) -> str:
    """Build the DO phase prompt for a step."""
    sections = []
    is_retry = bool(retry_context) or retry_count > 0

    if user_task:
        sections.append(f"## 用户需求\n\n{user_task}")

    if retry_context:
        sections.append(f"## 上次失败原因\n\n{retry_context}")

    if retry_count > 0:
        sections.append(f"## 重试信息\n\n这是第 **{retry_count}** 次重试，最大重试次数为 **{step.get('max_fail_count', 5)}** 次。")

    if sections:
        sections.append("---")

    sections.append(f"""## 当前任务

**步骤**：{step.get('id', 'unknown')}
**描述**：{step.get('desc', '')}

**任务**：{step.get('do', '')}

**输入说明**：{step.get('input', '')}

**输出要求**：{step.get('output', '')}""")

    if is_retry:
        sections.append("""---

## 执行指令

上次执行未通过，原因见上方。请执行以下操作：

1. **针对上述失败原因进行修复**，不要重复之前未通过的做法
2. 完成实际工作（修改代码、创建文件、执行命令等）
3. 所有任务要求和输出要求都满足后，在回复的**最后一行**单独输出 `<promise>done</promise>`

不要只描述你打算怎么做，直接去做。不要在工作未完成时输出 done 标记。""")
    else:
        sections.append("""---

## 执行指令

请执行上述任务。完成实际工作（修改代码、创建文件、执行命令等），不要只做分析或规划。

所有任务要求和输出要求都满足后，在回复的**最后一行**单独输出 `<promise>done</promise>`。

如果遇到无法解决的问题，说明具体问题，不要输出 done 标记。""")

    return "\n\n".join(sections)


def _handle_sub_workflow_entry(skill_dir: Path, state: dict, step: dict) -> dict:
    """Handle entering a sub-workflow at start."""
    from rf_lib.state import push_state
    MAX_NESTING_DEPTH = 5
    current_depth = get_stack_depth(skill_dir)

    if current_depth >= MAX_NESTING_DEPTH:
        return {'error': f"嵌套深度超过限制（{current_depth}/{MAX_NESTING_DEPTH}）。"}

    sub_workflow_name = step.get('workflow', '')
    sub_workflow = load_workflow(skill_dir, sub_workflow_name)
    if not sub_workflow:
        return {'error': f"子工作流 '{sub_workflow_name}' 未找到。"}

    sub_steps = sub_workflow.get('steps', [])
    if not sub_steps:
        return {'error': f"子工作流 '{sub_workflow_name}' 没有步骤。"}

    # Build sub-workflow user task
    sub_user_task_parts = []
    inputs = step.get('inputs', {})
    if inputs and isinstance(inputs, dict):
        for key, value in inputs.items():
            sub_user_task_parts.append(f"{key}: {value}")
    parent_task = state.get('user_task', '')
    if parent_task:
        if sub_user_task_parts:
            sub_user_task_parts.append("")
        sub_user_task_parts.append(f"原始需求：{parent_task}")
    sub_user_task = "\n".join(sub_user_task_parts)

    # Push parent state
    push_state(skill_dir, state)

    # Create sub-workflow state
    first_step = sub_steps[0]
    sub_state = {
        'active': True,
        'workflow_name': sub_workflow_name,
        'current_step': first_step.get('id', 'unknown'),
        'current_phase': 'do',
        'fail_count': 0,
        'user_task': sub_user_task,
        'paused': False,
        'last_failure_reason': None,
        'start_time': datetime.now().isoformat(),
        'parent': {
            'workflow_name': state.get('workflow_name'),
            'step_id': state.get('current_step'),
        }
    }
    write_state(skill_dir, sub_state)

    log_info(skill_dir, 'enter_sub_workflow', {
        'workflow': sub_workflow_name,
        'depth': current_depth + 1
    })

    # Check if first step is also a sub-workflow
    if is_sub_workflow_step(first_step):
        return _handle_sub_workflow_entry(skill_dir, sub_state, first_step)

    return {
        'sub_workflow': sub_workflow_name,
        'first_step': first_step.get('id', 'unknown'),
        'do_prompt': _build_do_prompt(first_step, sub_user_task),
        'depth': current_depth + 1
    }


def main():
    skill_dir = get_skill_dir(__file__)

    # Read input
    input_data = json.load(sys.stdin)
    workflow = input_data.get('workflow', '')
    task = input_data.get('task', '')
    session_id = input_data.get('session_id', '')

    # Check if there's an active workflow
    existing_state = read_state(skill_dir)
    if existing_state and existing_state.get('active', False):
        print(json.dumps({
            'error': (
                f"There is an active workflow '{existing_state.get('workflow_name')}' "
                f"(step: {existing_state.get('current_step')}, phase: {existing_state.get('current_phase')}). "
                f"Use rf-continue to resume or rf-cancel to cancel."
            )
        }, ensure_ascii=False))
        return

    # Auto-cleanup: clear old state and records
    clear_state(skill_dir)
    clear_step_records(skill_dir)

    # Load workflow
    workflow_def = load_workflow(skill_dir, workflow)
    if not workflow_def:
        available = list_workflows(skill_dir)
        if available:
            print(json.dumps({
                'error': f"Workflow '{workflow}' not found. Available workflows:",
                'workflows': available
            }, ensure_ascii=False, indent=2))
        else:
            print(json.dumps({
                'error': f"Workflow '{workflow}' not found. No workflows available."
            }, ensure_ascii=False))
        return

    # Get first step
    steps = workflow_def.get('steps', [])
    if not steps:
        print(json.dumps({'error': 'Workflow has no steps defined'}, ensure_ascii=False))
        return

    first_step = steps[0]

    # Create state
    new_state = {
        'active': True,
        'workflow_name': workflow,
        'current_step': first_step.get('id', 'unknown'),
        'current_phase': 'do',
        'fail_count': 0,
        'user_task': task,
        'paused': False,
        'last_failure_reason': None,
        'start_time': datetime.now().isoformat(),
    }
    if session_id:
        new_state['session_id'] = session_id

    write_state(skill_dir, new_state)

    # Log
    log_workflow_start(skill_dir, workflow)
    log_step_start(skill_dir, first_step.get('id', 'unknown'), 'do')

    # Handle sub-workflow step as first step
    if is_sub_workflow_step(first_step):
        sub_result = _handle_sub_workflow_entry(skill_dir, new_state, first_step)
        result = {
            'success': True,
            'message': f"Workflow '{workflow}' started with sub-workflow.",
            'task': task,
            'sub_workflow': sub_result,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # Build DO prompt for first step
    do_prompt = _build_do_prompt(first_step, task)

    # Return success
    result = {
        'success': True,
        'message': f"Workflow '{workflow}' started.",
        'task': task,
        'first_step': {
            'id': first_step.get('id', 'unknown'),
            'desc': first_step.get('desc', '')
        },
        'do_prompt': do_prompt,
        'instruction': '请按照 do_prompt 中的指令执行任务。完成后在回复最后一行输出 <promise>done</promise>，然后调用 rf-detect 检测标记。'
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
