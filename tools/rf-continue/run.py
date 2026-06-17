#!/usr/bin/env python3
"""
rf-continue tool - Resume a paused workflow.
Resets fail count, returns DO phase prompt with failure context.
"""
import json
import sys
from pathlib import Path
from datetime import datetime

# Add tools dir to path for rf_lib imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from rf_lib.paths import get_skill_dir
from rf_lib.state import read_state, write_state
from rf_lib.workflow import load_workflow, get_step, is_sub_workflow_step
from rf_lib.logging import log_workflow_resumed, log_step_start, log_error


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


def main():
    skill_dir = get_skill_dir(__file__)

    # Read optional input
    try:
        input_data = json.load(sys.stdin)
    except Exception:
        input_data = {}

    # Read state
    state = read_state(skill_dir)
    if not state:
        print(json.dumps({'error': 'No workflow state found.'}, ensure_ascii=False))
        return

    if not state.get('active', False):
        print(json.dumps({'error': 'No active workflow to continue.'}, ensure_ascii=False))
        return

    if not state.get('paused', False):
        print(json.dumps({
            'warning': f"Workflow is not paused. Current step: {state.get('current_step')}, phase: {state.get('current_phase')}"
        }, ensure_ascii=False))
        return

    workflow_name = state.get('workflow_name', 'unknown')
    current_step_id = state.get('current_step', 'unknown')
    user_task = state.get('user_task', '')
    last_failure = state.get('last_failure_reason', '')
    fail_count = state.get('fail_count', 0)

    # Load workflow
    workflow = load_workflow(skill_dir, workflow_name)
    step = None
    if workflow:
        step = get_step(workflow, current_step_id)

    # Update state - reset paused and fail_count
    new_state = {
        **state,
        'paused': False,
        'fail_count': 0,
        'current_phase': 'do',
        'last_failure_reason': None,
        'continue_time': datetime.now().isoformat(),
    }
    write_state(skill_dir, new_state)

    # Log
    log_workflow_resumed(skill_dir, workflow_name, current_step_id)
    log_step_start(skill_dir, current_step_id, 'do')

    # Build response
    result = {
        'success': True,
        'message': f"Workflow '{workflow_name}' resumed from step '{current_step_id}'.",
        'current_step': {
            'id': current_step_id,
            'desc': step.get('desc', '') if step else '',
        },
    }

    # Build DO prompt with failure context
    if step and not is_sub_workflow_step(step):
        do_prompt = _build_do_prompt(step, user_task, last_failure, fail_count)
        result['do_prompt'] = do_prompt
        result['instruction'] = '请按照 do_prompt 中的指令执行任务。完成后在回复最后一行输出 <promise>done</promise>，然后调用 rf-detect 检测标记。'

    if last_failure:
        result['previous_failure_reason'] = last_failure

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
