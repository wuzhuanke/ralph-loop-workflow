"""Tag detection for ralph-flow tools."""
import re
from typing import Dict, Any, Optional


# Tag patterns (same as original opencode version)
DONE_TAG = re.compile(r'<promise>\s*done\s*</promise>', re.IGNORECASE)
CHECK_TAG = re.compile(r'<promise-check>\s*(true|false)\s*</promise-check>', re.IGNORECASE)


def detect_done_tag(text: str) -> bool:
    """Detect if done tag is present in text.
    Checks last line first (most reliable), then last 100 chars.
    """
    if not text:
        return False

    trimmed = text.strip()

    # Check if done tag is on the last line (most reliable)
    lines = trimmed.split("\n")
    last_line = lines[-1].strip()
    if DONE_TAG.search(last_line):
        return True

    # Also check if it's at the end of the text (within last 100 chars)
    last_part = trimmed[-100:] if len(trimmed) > 100 else trimmed
    return bool(DONE_TAG.search(last_part))


def detect_check_tag(text: str) -> Dict[str, Any]:
    """Detect check tag and return result with reason.

    Returns:
        {"found": bool, "passed": Optional[bool], "reason": str}
    """
    if not text:
        return {"found": False, "passed": None, "reason": ""}

    match = CHECK_TAG.search(text)
    if not match:
        return {"found": False, "passed": None, "reason": ""}

    passed = match.group(1).lower() == "true"

    # Extract reason (text before the tag)
    lines = text.strip().split("\n")
    reason_lines = []
    for line in lines:
        if CHECK_TAG.search(line):
            break
        reason_lines.append(line)

    reason = "\n".join(reason_lines).strip()
    # Truncate if too long
    if len(reason) > 5000:
        reason = reason[:5000] + "..."

    return {
        "found": True,
        "passed": passed,
        "reason": reason
    }
