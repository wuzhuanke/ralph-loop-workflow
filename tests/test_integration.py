#!/usr/bin/env python3
"""Integration tests for ralph-flow tools (rf-start, rf-check, rf-detect, rf-advance, rf-status, rf-cancel, rf-continue)."""
import json
import sys
import os
import tempfile
import shutil
import io
from pathlib import Path
from unittest.mock import patch

# Add project root and tools dir to path
_project_root = str(Path(__file__).parent.parent)
sys.path.insert(0, _project_root)
sys.path.insert(0, str(Path(__file__).parent.parent / 'tools'))

PASS = 0
FAIL = 0


def test(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name} {detail}")


def run_tool_func(tool_name, input_data, skill_dir):
    """Run a tool by importing its module and calling main with mocked stdin."""
    # Import the tool module
    module_path = f'tools.{tool_name}.run'
    # We need to reload each time since state changes
    if module_path in sys.modules:
        del sys.modules[module_path]

    # Patch get_skill_dir to return our test skill_dir
    with patch('rf_lib.paths.get_skill_dir', return_value=skill_dir):
        # Also patch __file__ based get_skill_dir calls in the tool module
        tool_module = __import__(f'tools.{tool_name}.run', fromlist=['run'])

        # Mock stdin
        stdin_data = json.dumps(input_data)
        old_stdin = sys.stdin
        old_stdout = sys.stdout

        sys.stdin = io.StringIO(stdin_data)
        captured = io.StringIO()
        sys.stdout = captured

        try:
            tool_module.main()
        except SystemExit:
            pass
        finally:
            sys.stdin = old_stdin
            sys.stdout = old_stdout

        output = captured.getvalue()
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return {'_raw': output}


def setup_test_env():
    """Create a temporary skill directory with workflows."""
    tmp = Path(tempfile.mkdtemp(prefix='rf_integration_'))

    # Create workflows dir
    workflows_dir = tmp / 'workflows'
    workflows_dir.mkdir()

    # Create a simple test workflow
    (workflows_dir / 'test-wf.yaml').write_text(
        "description: test workflow\n"
        "adversarial_check:\n  enabled: true\n  timeout_ms: 60000\n"
        "steps:\n"
        "  - id: step1\n    desc: first step\n    do: do step1 task\n"
        "    input: none\n    output: step1 result\n    check: verify step1\n"
        "    on_pass: step2\n    on_fail: step1\n    max_fail_count: 3\n"
        "  - id: step2\n    desc: final step\n    do: do step2 task\n"
        "    input: step1 output\n    output: done\n    check: verify step2\n"
        "    on_pass: done\n    on_fail: step2\n    max_fail_count: 5\n",
        encoding='utf-8'
    )

    # Create a loop workflow
    (workflows_dir / 'loop-wf.yaml').write_text(
        "description: loop workflow\n"
        "steps:\n"
        "  - id: loop\n    desc: loop step\n    do: do loop task\n"
        "    input: none\n    output: loop result\n    check: verify loop\n"
        "    on_pass: done\n    on_fail: loop\n    max_fail_count: 3\n",
        encoding='utf-8'
    )

    return tmp


def teardown_test_env(tmp):
    shutil.rmtree(tmp, ignore_errors=True)


def read_state(tmp):
    state_file = tmp / 'state.json'
    if not state_file.exists():
        return None
    return json.loads(state_file.read_text(encoding='utf-8'))


def write_state(tmp, state):
    (tmp / 'state.json').write_text(json.dumps(state, ensure_ascii=False, indent=2))


def test_rf_start():
    print("\n--- rf-start ---")
    tmp = setup_test_env()
    try:
        # Start workflow
        result = run_tool_func('rf-start', {
            'workflow': 'test-wf',
            'task': 'test task description',
        }, tmp)
        test("rf-start returns success", result.get('success') is True, str(result)[:200])
        test("rf-start returns do_prompt", 'do_prompt' in result, str(result)[:200])
        test("rf-start sets first step", result.get('first_step', {}).get('id') == 'step1', str(result)[:200])
        test("rf-start do_prompt contains task", 'test task description' in result.get('do_prompt', ''))
        test("rf-start do_prompt contains done tag instruction", '<promise>done</promise>' in result.get('do_prompt', ''))

        # Verify state file
        state = read_state(tmp)
        test("rf-start creates state.json", state is not None)
        if state:
            test("state has active=True", state.get('active') is True)
            test("state has workflow_name", state.get('workflow_name') == 'test-wf')
            test("state has current_step=step1", state.get('current_step') == 'step1')
            test("state has current_phase=do", state.get('current_phase') == 'do')
            test("state has user_task", state.get('user_task') == 'test task description')

        # Start when already active should fail
        result2 = run_tool_func('rf-start', {
            'workflow': 'test-wf',
            'task': 'another task',
        }, tmp)
        test("rf-start rejects when already active", 'error' in result2, str(result2)[:200])

        # Start non-existent workflow
        (tmp / 'state.json').unlink(missing_ok=True)
        result3 = run_tool_func('rf-start', {
            'workflow': 'nonexistent',
            'task': 'test',
        }, tmp)
        test("rf-start rejects non-existent workflow", 'error' in result3, str(result3)[:200])
    finally:
        teardown_test_env(tmp)


def test_rf_status():
    print("\n--- rf-status ---")
    tmp = setup_test_env()
    try:
        # No state
        result = run_tool_func('rf-status', {}, tmp)
        test("rf-status returns active=False when no state", result.get('active') is False)

        # With active state
        write_state(tmp, {
            'active': True,
            'workflow_name': 'test-wf',
            'current_step': 'step1',
            'current_phase': 'do',
            'fail_count': 0,
            'user_task': 'test task',
            'paused': False,
        })
        result = run_tool_func('rf-status', {}, tmp)
        test("rf-status returns active=True", result.get('active') is True)
        test("rf-status returns workflow name", result.get('workflow') == 'test-wf')
        test("rf-status returns current_step", result.get('current_step') == 'step1')
        test("rf-status returns current_phase", result.get('current_phase') == 'do')
        test("rf-status returns step_detail", 'step_detail' in result and result['step_detail'] is not None)
        test("rf-status step_detail has do field", result.get('step_detail', {}).get('do') == 'do step1 task')
        test("rf-status returns guidance", 'guidance' in result)
    finally:
        teardown_test_env(tmp)


def test_rf_detect_do_to_check():
    print("\n--- rf-detect (DO -> CHECK) ---")
    tmp = setup_test_env()
    try:
        write_state(tmp, {
            'active': True,
            'workflow_name': 'test-wf',
            'current_step': 'step1',
            'current_phase': 'do',
            'fail_count': 0,
            'user_task': 'test task',
            'paused': False,
        })

        result = run_tool_func('rf-detect', {
            'text': 'I completed the task\n<promise>done</promise>'
        }, tmp)
        test("rf-detect detects done tag", result.get('done_detected') is True)
        test("rf-detect auto-transitions to CHECK", result.get('state_transition', {}).get('to_phase') == 'check')
        test("rf-detect suggests rf-check", 'rf-check' in result.get('suggestion', ''))

        state = read_state(tmp)
        test("state phase updated to check", state is not None and state.get('current_phase') == 'check')
    finally:
        teardown_test_env(tmp)


def test_rf_check():
    print("\n--- rf-check ---")
    tmp = setup_test_env()
    try:
        write_state(tmp, {
            'active': True,
            'workflow_name': 'test-wf',
            'current_step': 'step1',
            'current_phase': 'check',
            'fail_count': 0,
            'user_task': 'test task',
            'paused': False,
        })

        result = run_tool_func('rf-check', {}, tmp)
        test("rf-check returns success", result.get('success') is True, str(result)[:200])
        test("rf-check returns system_prompt", 'system_prompt' in result, str(result)[:200])
        test("rf-check returns check_prompt", 'check_prompt' in result, str(result)[:200])
        test("rf-check check_prompt contains step info", 'step1' in result.get('check_prompt', ''))
        test("rf-check check_prompt contains check criteria", 'verify step1' in result.get('check_prompt', ''))
        test("rf-check returns instruction", 'instruction' in result, str(result)[:200])
        test("rf-check system_prompt mentions promise-check", 'promise-check' in result.get('system_prompt', ''))
    finally:
        teardown_test_env(tmp)


def test_rf_detect_check_pass():
    print("\n--- rf-detect (CHECK pass -> next step) ---")
    tmp = setup_test_env()
    try:
        write_state(tmp, {
            'active': True,
            'workflow_name': 'test-wf',
            'current_step': 'step1',
            'current_phase': 'check',
            'fail_count': 0,
            'user_task': 'test task',
            'paused': False,
        })

        result = run_tool_func('rf-detect', {
            'text': 'All checks passed\n<promise-check>true</promise-check>'
        }, tmp)
        test("rf-detect detects check pass", result.get('check_result', {}).get('passed') is True)
        test("rf-detect transitions to next_step", result.get('state_transition', {}).get('action') == 'next_step')
        test("rf-detect next step is step2", result.get('state_transition', {}).get('step_id') == 'step2')
        test("rf-detect returns do_prompt for next step", 'do_prompt' in result.get('state_transition', {}))

        state = read_state(tmp)
        test("state step updated to step2", state is not None and state.get('current_step') == 'step2')
        test("state phase reset to do", state is not None and state.get('current_phase') == 'do')
        test("state fail_count reset", state is not None and state.get('fail_count') == 0)
    finally:
        teardown_test_env(tmp)


def test_rf_detect_check_fail():
    print("\n--- rf-detect (CHECK fail -> retry) ---")
    tmp = setup_test_env()
    try:
        write_state(tmp, {
            'active': True,
            'workflow_name': 'test-wf',
            'current_step': 'step1',
            'current_phase': 'check',
            'fail_count': 0,
            'user_task': 'test task',
            'paused': False,
        })

        result = run_tool_func('rf-detect', {
            'text': 'Some checks failed\n<promise-check>false</promise-check>'
        }, tmp)
        test("rf-detect detects check fail", result.get('check_result', {}).get('found') is True and not result.get('check_result', {}).get('passed'))
        test("rf-detect transitions to next_step (retry)", result.get('state_transition', {}).get('action') == 'next_step')
        test("rf-detect fail_count incremented", result.get('state_transition', {}).get('fail_count') == 1)

        state = read_state(tmp)
        test("state fail_count=1", state is not None and state.get('fail_count') == 1)
    finally:
        teardown_test_env(tmp)


def test_rf_detect_check_pause():
    print("\n--- rf-detect (CHECK fail -> pause) ---")
    tmp = setup_test_env()
    try:
        write_state(tmp, {
            'active': True,
            'workflow_name': 'test-wf',
            'current_step': 'step1',
            'current_phase': 'check',
            'fail_count': 2,
            'user_task': 'test task',
            'paused': False,
        })

        result = run_tool_func('rf-detect', {
            'text': 'Still failing\n<promise-check>false</promise-check>'
        }, tmp)
        test("rf-detect pauses on max fail", result.get('state_transition', {}).get('action') == 'paused')

        state = read_state(tmp)
        test("state paused=True", state is not None and state.get('paused') is True)
    finally:
        teardown_test_env(tmp)


def test_rf_detect_final_step_done():
    print("\n--- rf-detect (final step CHECK pass -> completed) ---")
    tmp = setup_test_env()
    try:
        write_state(tmp, {
            'active': True,
            'workflow_name': 'test-wf',
            'current_step': 'step2',
            'current_phase': 'check',
            'fail_count': 0,
            'user_task': 'test task',
            'paused': False,
        })

        result = run_tool_func('rf-detect', {
            'text': 'Final check passed\n<promise-check>true</promise-check>'
        }, tmp)
        test("rf-detect completes workflow", result.get('state_transition', {}).get('action') == 'completed')
        test("rf-detect returns report path", 'report' in result.get('state_transition', {}))

        state = read_state(tmp)
        test("state active=False after completion", state is not None and state.get('active') is False)
    finally:
        teardown_test_env(tmp)


def test_rf_advance():
    print("\n--- rf-advance ---")
    tmp = setup_test_env()
    try:
        write_state(tmp, {
            'active': True,
            'workflow_name': 'test-wf',
            'current_step': 'step1',
            'current_phase': 'check',
            'fail_count': 0,
            'user_task': 'test task',
            'paused': False,
        })

        result = run_tool_func('rf-advance', {
            'result': 'pass',
            'reason': 'all good'
        }, tmp)
        test("rf-advance pass transitions to next_step", result.get('action') == 'next_step', str(result)[:200])
        test("rf-advance next step is step2", result.get('step_id') == 'step2', str(result)[:200])
        test("rf-advance returns do_prompt", 'do_prompt' in result, str(result)[:200])

        # Advance with fail
        write_state(tmp, {
            'active': True,
            'workflow_name': 'test-wf',
            'current_step': 'step1',
            'current_phase': 'check',
            'fail_count': 0,
            'user_task': 'test task',
            'paused': False,
        })

        result2 = run_tool_func('rf-advance', {
            'result': 'fail',
            'reason': 'test failed'
        }, tmp)
        test("rf-advance fail returns next_step (retry)", result2.get('action') == 'next_step', str(result2)[:200])
        test("rf-advance fail increments count", result2.get('fail_count') == 1, str(result2)[:200])
    finally:
        teardown_test_env(tmp)


def test_rf_cancel():
    print("\n--- rf-cancel ---")
    tmp = setup_test_env()
    try:
        write_state(tmp, {
            'active': True,
            'workflow_name': 'test-wf',
            'current_step': 'step1',
            'current_phase': 'do',
            'fail_count': 1,
            'user_task': 'test task',
            'paused': False,
        })

        result = run_tool_func('rf-cancel', {
            'reason': 'user requested cancel'
        }, tmp)
        test("rf-cancel returns success", result.get('success') is True, str(result)[:200])
        test("rf-cancel returns report path", 'report' in result, str(result)[:200])
        test("rf-cancel includes reason", result.get('reason') == 'user requested cancel')

        test("rf-cancel clears state file", not (tmp / 'state.json').exists())
    finally:
        teardown_test_env(tmp)


def test_rf_continue():
    print("\n--- rf-continue ---")
    tmp = setup_test_env()
    try:
        write_state(tmp, {
            'active': True,
            'workflow_name': 'test-wf',
            'current_step': 'step1',
            'current_phase': 'check',
            'fail_count': 3,
            'user_task': 'test task',
            'paused': True,
            'last_failure_reason': 'test kept failing',
        })

        result = run_tool_func('rf-continue', {}, tmp)
        test("rf-continue returns success", result.get('success') is True, str(result)[:200])
        test("rf-continue returns do_prompt", 'do_prompt' in result, str(result)[:200])
        test("rf-continue includes previous failure", 'previous_failure_reason' in result, str(result)[:200])

        state = read_state(tmp)
        test("state paused=False after continue", state is not None and state.get('paused') is False)
        test("state fail_count reset to 0", state is not None and state.get('fail_count') == 0)
        test("state phase reset to do", state is not None and state.get('current_phase') == 'do')
    finally:
        teardown_test_env(tmp)


def test_full_workflow():
    print("\n--- Full workflow (start -> do -> check -> pass -> do -> check -> pass -> done) ---")
    tmp = setup_test_env()
    try:
        # 1. Start
        r = run_tool_func('rf-start', {'workflow': 'test-wf', 'task': 'full workflow test'}, tmp)
        test("full: start succeeds", r.get('success') is True)

        # 2. DO step1 -> detect done
        r = run_tool_func('rf-detect', {'text': 'Step1 done\n<promise>done</promise>'}, tmp)
        test("full: step1 done detected", r.get('done_detected') is True)
        test("full: transitions to check", r.get('state_transition', {}).get('to_phase') == 'check')

        # 3. CHECK step1 -> detect pass
        r = run_tool_func('rf-detect', {'text': 'Check passed\n<promise-check>true</promise-check>'}, tmp)
        test("full: step1 check pass", r.get('check_result', {}).get('passed') is True)
        test("full: transitions to step2", r.get('state_transition', {}).get('step_id') == 'step2')

        # 4. DO step2 -> detect done
        r = run_tool_func('rf-detect', {'text': 'Step2 done\n<promise>done</promise>'}, tmp)
        test("full: step2 done detected", r.get('done_detected') is True)

        # 5. CHECK step2 -> detect pass (final step, on_pass=done)
        r = run_tool_func('rf-detect', {'text': 'Final check passed\n<promise-check>true</promise-check>'}, tmp)
        test("full: workflow completed", r.get('state_transition', {}).get('action') == 'completed')
        test("full: report generated", 'report' in r.get('state_transition', {}))
    finally:
        teardown_test_env(tmp)


if __name__ == '__main__':
    print("=" * 60)
    print("ralph-flow Integration Tests")
    print("=" * 60)

    test_rf_start()
    test_rf_status()
    test_rf_detect_do_to_check()
    test_rf_check()
    test_rf_detect_check_pass()
    test_rf_detect_check_fail()
    test_rf_detect_check_pause()
    test_rf_detect_final_step_done()
    test_rf_advance()
    test_rf_cancel()
    test_rf_continue()
    test_full_workflow()

    print("\n" + "=" * 60)
    total = PASS + FAIL
    print(f"Results: {PASS}/{total} passed, {FAIL}/{total} failed")
    if FAIL > 0:
        print("SOME TESTS FAILED!")
        sys.exit(1)
    else:
        print("ALL TESTS PASSED!")
    print("=" * 60)
