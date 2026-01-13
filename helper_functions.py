import re
import json

from typing import Any, Dict, List, Tuple, Optional

# Regexes
MSISDN_RE = re.compile(r"^298\d{6}$")
RETCODE_RE = re.compile(r"RETCODE\s*=\s*(\d+)\s*(.*)")
RESULT_COUNT_RE = re.compile(r"\(Number of results\s*=\s*\d+\)")
PDP_CONTEXT_HEADER_RE = re.compile(
    r'^PDP context on\s+'
    r'(?P<node>.+?)\s+'        # <- allow spaces in node, non-greedy
    r'SGID\s+(?P<sgid>\S+)\s+'
    r'ContextIndex\s+(?P<context_index>\S+)\s+'
    r'GtpuIndex\s+(?P<gtpu_index>\S+)\s+'
    r'FilterIndex\s+(?P<filter_index>\S+)\s+'
    r'SessionIndex\s+(?P<session_index>\S+)\s+'
    r'BearerIndex\s+(?P<bearer_index>\S+)',
    re.IGNORECASE,
)

# Named indexes
RETCODE_LINE = 5

def validate_msisdn(text: str) -> bool:
    return bool(MSISDN_RE.match(text))

def extract_retcode(line: str) -> (int, str):
        """
        Extract RETCODE and its message, if present.

        Example:
            'RETCODE = 0  Operation Success.'
        """
        match = RETCODE_RE.search(line)
        code = int(match.group(1))
        message = match.group(2).strip()

        return code, message

def pdp_query_parser(text: str) -> Dict[str, Any]:
    text_lines = text.splitlines()
    code, message = extract_retcode(text_lines[RETCODE_LINE])

    # Exit early if query is unsuccessful or RETCODE missing
    if code != 0:
        return None
    
    contexts: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None

    for line in text_lines:
        # Stop parsing when we hit result count or END marker
        if RESULT_COUNT_RE.search(line):
            break

        # Detect start of a new PDP context
        header_match = PDP_CONTEXT_HEADER_RE.match(line.strip())
        if header_match:
            # If we already had one open, store it
            if current is not None:
                contexts.append(current)

            # Start new context dict with header fields
            current = header_match.groupdict()
            continue

        # Ignore everything until the first PDP context header
        if current is None:
            continue

        s = line.strip()
        if not s or "=" not in s:
            # Skip blank lines, separators, etc.
            continue

        key, val = s.split("=", 1)
        key = key.strip()
        val = val.strip()         

        # Handle duplicate keys by turning value into a list
        if key in current:
            existing = current[key]
            if isinstance(existing, list):
                existing.append(val)
            else:
                current[key] = [existing, val]
        else:
            current[key] = val

    if current is None:
        return contexts

    contexts.append(current)

    return contexts
