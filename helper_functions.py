import re

from typing import Any, Dict, List, Optional, Tuple

# Compiled regexes (module-level)
MSISDN_RE = re.compile(r"298\d{6}\Z")

RETCODE_RE = re.compile(r"RETCODE\s*=\s*(\d+)\s*(.*)")
RESULT_COUNT_RE = re.compile(r"\(Number of results\s*=\s*\d+\)")
PDP_CONTEXT_HEADER_RE = re.compile(
    r"^PDP context on\s+"
    r"(?P<node>.+?)\s+"
    r"SGID\s+(?P<sgid>\S+)\s+"
    r"ContextIndex\s+(?P<context_index>\S+)\s+"
    r"GtpuIndex\s+(?P<gtpu_index>\S+)\s+"
    r"FilterIndex\s+(?P<filter_index>\S+)\s+"
    r"SessionIndex\s+(?P<session_index>\S+)\s+"
    r"BearerIndex\s+(?P<bearer_index>\S+)",
    re.IGNORECASE,
)

Context = Dict[str, Any]


def validate_msisdn(text: str) -> bool:
    return MSISDN_RE.fullmatch(text) is not None


def extract_retcode(line: str) -> Optional[Tuple[int, str]]:
    """
    Extract RETCODE and its message, if present.

    Example:
        'RETCODE = 0  Operation Success.'
    """
    m = RETCODE_RE.search(line)
    if not m:
        return None
    return int(m.group(1)), m.group(2).strip()


def pdp_query_parser(text: str) -> Optional[List[Context]]:
    """
    Parse PDP query output.

    Returns:
        - list of context dicts on success (RETCODE == 0)
        - None on non-zero RETCODE or missing RETCODE
    """
    lines = text.splitlines()

    # Find RETCODE anywhere (instead of brittle fixed line index)
    ret: Optional[Tuple[int, str]] = None
    for line in lines:
        ret = extract_retcode(line)
        if ret is not None:
            break

    if ret is None:
        return None

    code, _message = ret
    if code != 0:
        return None

    contexts: List[Context] = []
    current: Optional[Context] = None

    for raw in lines:
        if RESULT_COUNT_RE.search(raw):
            break

        line = raw.strip()

        header = PDP_CONTEXT_HEADER_RE.match(line)
        if header:
            if current is not None:
                contexts.append(current)
            current = header.groupdict()
            continue

        if current is None:
            continue

        if not line or "=" not in line:
            continue

        key, val = (part.strip() for part in line.split("=", 1))

        # Store duplicates as list
        prev = current.get(key)
        if prev is None:
            current[key] = val
        elif isinstance(prev, list):
            prev.append(val)
        else:
            current[key] = [prev, val]

    if current is not None:
        contexts.append(current)

    return contexts