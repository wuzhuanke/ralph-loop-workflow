"""Structured logging for ralpha-loop-workflow tools."""
import json
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime


def _ensure_log_dir(logs_dir: Path) -> None:
    """Ensure the logs directory exists."""
    logs_dir.mkdir(parents=True, exist_ok=True)


def log_event(
    skill_dir: Path,
    level: str,
    event: str,
    extra: Optional[Dict[str, Any]] = None
) -> None:
    """Write a structured log entry to execution.log."""
    from rf_lib.paths import get_logs_dir
    logs_dir = get_logs_dir(skill_dir)
    try:
        _ensure_log_dir(logs_dir)
        entry: Dict[str, Any] = {
            'ts': datetime.now().isoformat(),
            'level': level,
            'event': event,
        }
        if extra:
            entry.update(extra)
        log_file = logs_dir / 'execution.log'
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    except Exception:
        pass  # Silently fail to avoid recursive errors


def log_step_event(
    skill_dir: Path,
    step_id: str,
    phase: str,
    level: str,
    event: str,
    extra: Optional[Dict[str, Any]] = None
) -> None:
    """Write a structured log entry to both step log and execution.log."""
    from rf_lib.paths import get_logs_dir
    logs_dir = get_logs_dir(skill_dir)
    try:
        _ensure_log_dir(logs_dir)
        entry: Dict[str, Any] = {
            'ts': datetime.now().isoformat(),
            'level': level,
            'event': event,
            'step': step_id,
            'phase': phase,
        }
        if extra:
            entry.update(extra)

        # Write to step-specific log
        step_log = logs_dir / f'step-{step_id}-{phase}.log'
        with open(step_log, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')

        # Also write to main execution log
        log_file = logs_dir / 'execution.log'
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    except Exception:
        pass


# --- Convenience functions ---

def log_workflow_start(skill_dir: Path, workflow_name: str) -> None:
    log_event(skill_dir, 'info', 'workflow_start', {'workflow': workflow_name})


def log_workflow_end(skill_dir: Path, workflow_name: str) -> None:
    log_event(skill_dir, 'info', 'workflow_end', {'workflow': workflow_name})


def log_step_start(skill_dir: Path, step_id: str, phase: str) -> None:
    log_step_event(skill_dir, step_id, phase, 'info', 'step_start')


def log_done_detected(skill_dir: Path, step_id: str) -> None:
    log_step_event(skill_dir, step_id, 'do', 'info', 'done_detected')


def log_check_result(skill_dir: Path, step_id: str, passed: bool) -> None:
    log_step_event(skill_dir, step_id, 'check', 'info', 'check_result', {'passed': passed})


def log_fail_count_increment(skill_dir: Path, step_id: str, fail_count: int) -> None:
    log_step_event(skill_dir, step_id, 'check', 'warn', 'fail_count_increment', {'fail_count': fail_count})


def log_workflow_paused(skill_dir: Path, workflow_name: str, step_id: str, fail_count: int) -> None:
    log_event(skill_dir, 'warn', 'workflow_paused', {'workflow': workflow_name, 'step': step_id, 'fail_count': fail_count})


def log_workflow_resumed(skill_dir: Path, workflow_name: str, step_id: str) -> None:
    log_event(skill_dir, 'info', 'workflow_resumed', {'workflow': workflow_name, 'step': step_id})


def log_workflow_cancelled(skill_dir: Path, workflow_name: str, reason: str = '') -> None:
    extra: Dict[str, Any] = {'workflow': workflow_name}
    if reason:
        extra['reason'] = reason
    log_event(skill_dir, 'info', 'workflow_cancelled', extra)


def log_error(skill_dir: Path, event: str, error: Any) -> None:
    error_msg = str(error) if not isinstance(error, Exception) else str(error)
    log_event(skill_dir, 'error', event, {'error': error_msg})


def log_warn(skill_dir: Path, event: str, details: Optional[Dict[str, Any]] = None) -> None:
    log_event(skill_dir, 'warn', event, details)


def log_info(skill_dir: Path, event: str, details: Optional[Dict[str, Any]] = None) -> None:
    log_event(skill_dir, 'info', event, details)


def log_debug(skill_dir: Path, event: str, details: Optional[Dict[str, Any]] = None) -> None:
    log_event(skill_dir, 'debug', event, details)
