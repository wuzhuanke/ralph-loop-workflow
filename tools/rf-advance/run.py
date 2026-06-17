#!/usr/bin/env python3
"""
rf-advance tool - Advance workflow state machine.
Routes to next step based on check result (pass/fail),
handles fail count, pause, completion, and sub-workflow resume.
"""
import json
import sys
from pathlib import Path
from datetime import datetime

# Add tools dir to path for rf_lib imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from rf_lib.paths import get_skill_dir
from rf_lib.state import (
    read_state, write_state, mark_completed, mark_paused,
    pop_state, get_stack_depth
)
from rf_lib.workflow import load_workflow, get_step, is_sub_workflow_step
from rf_lib.logging import (
    log_check_result, log_fail_count_increment, log_workflow_paused,
    log_workflow_end, log_step_start, log_error, log_info
)
from rf_lib.report import (
    create_step_record, append_step_record, read_step_records,
    generate_completion_report, generate_pause_report
)

MAX_NESTING_DEPTH = 5


def _build_do_prompt(step: dict, user_task: str = "", retry_context: str = "", retry_count: int = 0) -> str:
    """Build the DO phase prompt for a step (same logic as original)."""
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
    """Handle entering a sub-workflow. Returns result dict."""
    current_depth = get_stack_depth(skill_dir)

    if current_depth >= MAX_NESTING_DEPTH:
        return {
            'error': f"嵌套深度超过限制（{current_depth}/{MAX_NESTING_DEPTH}）。可能存在循环引用。",
            'action': 'fail_sub_workflow'
        }

    sub_workflow_name = step.get('workflow', '')
    sub_workflow = load_workflow(skill_dir, sub_workflow_name)
    if not sub_workflow:
        return {
            'error': f"子工作流 '{sub_workflow_name}' 未找到。",
            'action': 'fail_sub_workflow'
        }

    sub_steps = sub_workflow.get('steps', [])
    if not sub_steps:
        return {
            'error': f"子工作流 '{sub_workflow_name}' 没有步骤。",
            'action': 'fail_sub_workflow'
        }

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
    from rf_lib.state import push_state
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
        nested_result = _handle_sub_workflow_entry(skill_dir, sub_state, first_step)
        if 'error' in nested_result:
            return nested_result

    return {
        'action': 'enter_sub_workflow',
        'sub_workflow': sub_workflow_name,
        'first_step': first_step.get('id', 'unknown'),
        'do_prompt': _build_do_prompt(first_step, sub_user_task) if not is_sub_workflow_step(first_step) else None,
        'depth': current_depth + 1
    }


def _handle_resume_parent(skill_dir: Path, parent_state: dict, sub_passed: bool, failure_reason: str = "") -> dict:
    """Handle resuming parent workflow after sub-workflow completes."""
    parent_workflow_name = parent_state.get('workflow_name', '')
    parent_step_id = parent_state.get('current_step', '')

    parent_workflow = load_workflow(skill_dir, parent_workflow_name)
    if not parent_workflow:
        return {'error': f"父工作流 '{parent_workflow_name}' 未找到。"}

    parent_step = get_step(parent_workflow, parent_step_id)
    if not parent_step:
        return {'error': f"父步骤 '{parent_step_id}' 未找到。"}

    if sub_passed:
        if parent_step.get('on_pass') == 'done':
            mark_completed(skill_dir, parent_state)
            log_workflow_end(skill_dir, parent_workflow_name)
            report_path = generate_completion_report(skill_dir, parent_workflow_name)
            return {
                'action': 'completed',
                'workflow': parent_workflow_name,
                'report': str(report_path)
            }
        else:
            next_step = get_step(parent_workflow, parent_step.get('on_pass', ''))
            if next_step:
                updated_state = {
                    **parent_state,
                    'current_step': next_step.get('id'),
                    'current_phase': 'do',
                    'fail_count': 0,
                    'last_failure_reason': None,
                }
                write_state(skill_dir, updated_state)
                log_step_start(skill_dir, next_step.get('id'), 'do')

                if is_sub_workflow_step(next_step):
                    return _handle_sub_workflow_entry(skill_dir, updated_state, next_step)

                return {
                    'action': 'next_step',
                    'step_id': next_step.get('id'),
                    'do_prompt': _build_do_prompt(next_step, parent_state.get('user_task', ''))
                }
    else:
        new_fail_count = parent_state.get('fail_count', 0) + 1
        if new_fail_count >= parent_step.get('max_fail_count', 5):
            mark_paused(skill_dir, {**parent_state, 'fail_count': new_fail_count, 'last_failure_reason': failure_reason})
            log_workflow_paused(skill_dir, parent_workflow_name, parent_step_id, new_fail_count)
            generate_pause_report(skill_dir, parent_workflow_name)
            return {
                'action': 'paused',
                'step_id': parent_step_id,
                'fail_count': new_fail_count,
                'max_fail_count': parent_step.get('max_fail_count', 5),
                'reason': failure_reason
            }
        else:
            next_step = get_step(parent_workflow, parent_step.get('on_fail', parent_step_id))
            if next_step:
                updated_state = {
                    **parent_state,
                    'current_step': next_step.get('id'),
                    'current_phase': 'do',
                    'fail_count': new_fail_count,
                    'last_failure_reason': failure_reason,
                }
                write_state(skill_dir, updated_state)
                log_step_start(skill_dir, next_step.get('id'), 'do')

                if is_sub_workflow_step(next_step):
                    return _handle_sub_workflow_entry(skill_dir, updated_state, next_step)

                return {
                    'action': 'next_step',
                    'step_id': next_step.get('id'),
                    'do_prompt': _build_do_prompt(
                        next_step,
                        parent_state.get('user_task', ''),
                        failure_reason,
                        new_fail_count
                    )
                }

    return {'error': 'Unable to determine next action.'}


def main():
    skill_dir = get_skill_dir(__file__)

    # Read input
    try:
        input_data = json.load(sys.stdin)
    except Exception:
        input_data = {}

    result_str = input_data.get('result', '')
    reason = input_data.get('reason', '')

    if result_str not in ('pass', 'fail'):
        print(json.dumps({'error': "Parameter 'result' must be 'pass' or 'fail'."}, ensure_ascii=False))
        return

    passed = result_str == 'pass'

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
    fail_count = state.get('fail_count', 0)

    # Load workflow
    workflow = load_workflow(skill_dir, workflow_name)
    if not workflow:
        print(json.dumps({'error': f"Workflow '{workflow_name}' not found."}, ensure_ascii=False))
        return

    step = get_step(workflow, current_step_id)
    if not step:
        print(json.dumps({'error': f"Step '{current_step_id}' not found."}, ensure_ascii=False))
        return

    # Log check result
    log_check_result(skill_dir, current_step_id, passed)

    # Create step record
    check_fail_count = fail_count if passed else fail_count + 1
    record = create_step_record(
        current_step_id, 'check',
        'passed' if passed else 'failed',
        check_fail_count, reason
    )
    append_step_record(skill_dir, record)

    # Route based on result
    if passed:
        if step.get('on_pass') == 'done':
            # Check if we're in a sub-workflow
            parent_state = pop_state(skill_dir)
            if parent_state:
                resume_result = _handle_resume_parent(skill_dir, parent_state, True)
                print(json.dumps(resume_result, ensure_ascii=False, indent=2))
            else:
                mark_completed(skill_dir, state)
                log_workflow_end(skill_dir, workflow_name)
                report_path = generate_completion_report(skill_dir, workflow_name)
                print(json.dumps({
                    'action': 'completed',
                    'workflow': workflow_name,
                    'report': str(report_path)
                }, ensure_ascii=False, indent=2))
        else:
            next_step = get_step(workflow, step.get('on_pass', ''))
            if next_step:
                updated_state = {
                    **state,
                    'current_step': next_step.get('id'),
                    'current_phase': 'do',
                    'fail_count': 0,
                    'last_failure_reason': None,
                }
                write_state(skill_dir, updated_state)
                log_step_start(skill_dir, next_step.get('id'), 'do')

                if is_sub_workflow_step(next_step):
                    result = _handle_sub_workflow_entry(skill_dir, updated_state, next_step)
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                else:
                    do_prompt = _build_do_prompt(next_step, state.get('user_task', ''))
                    print(json.dumps({
                        'action': 'next_step',
                        'step_id': next_step.get('id'),
                        'do_prompt': do_prompt
                    }, ensure_ascii=False, indent=2))
            else:
                print(json.dumps({'error': f"Next step '{step.get('on_pass')}' not found."}, ensure_ascii=False))
    else:
        new_fail_count = fail_count + 1
        log_fail_count_increment(skill_dir, current_step_id, new_fail_count)

        if new_fail_count >= step.get('max_fail_count', 5):
            # Check if we're in a sub-workflow
            parent_state = pop_state(skill_dir)
            if parent_state:
                resume_result = _handle_resume_parent(skill_dir, parent_state, False, reason)
                print(json.dumps(resume_result, ensure_ascii=False, indent=2))
            else:
                mark_paused(skill_dir, {**state, 'fail_count': new_fail_count, 'last_failure_reason': reason})
                log_workflow_paused(skill_dir, workflow_name, current_step_id, new_fail_count)
                generate_pause_report(skill_dir, workflow_name)
                print(json.dumps({
                    'action': 'paused',
                    'step_id': current_step_id,
                    'fail_count': new_fail_count,
                    'max_fail_count': step.get('max_fail_count', 5),
                    'reason': reason,
                    'message': (
                        f"步骤 `{current_step_id}` 检查失败，已失败 {new_fail_count}/{step.get('max_fail_count', 5)} 次。\n\n"
                        f"### 失败原因\n{reason or '未知'}\n\n"
                        f"### 后续操作\n"
                        f"1. 查看上面的失败原因并修复问题\n"
                        f"2. 运行 `rf-continue` 从当前步骤重试\n"
                        f"3. 运行 `rf-cancel` 取消工作流"
                    )
                }, ensure_ascii=False, indent=2))
        else:
            next_step_id = step.get('on_fail', current_step_id)
            next_step = get_step(workflow, next_step_id)
            if next_step:
                updated_state = {
                    **state,
                    'current_step': next_step.get('id'),
                    'current_phase': 'do',
                    'fail_count': new_fail_count,
                    'last_failure_reason': reason,
                }
                write_state(skill_dir, updated_state)
                log_step_start(skill_dir, next_step.get('id'), 'do')

                if is_sub_workflow_step(next_step):
                    result = _handle_sub_workflow_entry(skill_dir, updated_state, next_step)
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                else:
                    do_prompt = _build_do_prompt(
                        next_step,
                        state.get('user_task', ''),
                        reason,
                        new_fail_count
                    )
                    print(json.dumps({
                        'action': 'next_step',
                        'step_id': next_step.get('id'),
                        'do_prompt': do_prompt,
                        'fail_count': new_fail_count
                    }, ensure_ascii=False, indent=2))
            else:
                print(json.dumps({'error': f"Next step '{next_step_id}' not found."}, ensure_ascii=False))


if __name__ == '__main__':
    main()
