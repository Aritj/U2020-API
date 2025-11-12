import re
from typing import Any, Dict, List, Tuple, Optional

MSISDN_RE = re.compile(r"^\d{6,9}$")
IMSI_RE = re.compile(r"^\d{10,20}$")

def validate_msisdn(text: str) -> bool:
    return bool(MSISDN_RE.match(text))

def validate_imsi(text: str) -> bool:
    return bool(IMSI_RE.match(text))


def pdp_query_parser(text: str) -> Dict[str, Any]:
    """
    Parse Huawei UGW 'DSP PDPCTXT' CLI output for a *single* query into structured data.

    Assumptions:
    - Input corresponds to one executed query.
    - The query may return:
        * 0 PDP contexts ("No matching result is found")
        * 1 PDP context
        * N PDP contexts (each starting with 'PDP context on ...')
    - MSISDN is intentionally ignored.

    Returns:
        {
            "retcode": int | None,
            "retmsg": str | None,
            "count": int,            # number of parsed PDP contexts
            "has_active_pdp": bool,  # True if count > 0
            "contexts": [
                {
                    "header": { ... },  # parsed from 'PDP context on ...'
                    "fields": {
                        "IMSI": "2740...",
                        "APN name": "gprs.fo",
                        ...
                        # Repeated keys (e.g. "User Location Information")
                        # are represented as lists in insertion order.
                    }
                },
                ...
            ],
        }
    """

    # ---------- Configuration & Patterns ----------

    # Header line describing a single PDP context.
    header_pattern = re.compile(
        r'^PDP context on\s+'
        r'(?P<node>\S+)\s+'
        r'SGID\s+(?P<sgid>\S+)\s+'
        r'ContextIndex\s+(?P<context_index>\S+)\s+'
        r'GtpuIndex\s+(?P<gtpu_index>\S+)\s+'
        r'FilterIndex\s+(?P<filter_index>\S+)\s+'
        r'SessionIndex\s+(?P<session_index>\S+)\s+'
        r'BearerIndex\s+(?P<bearer_index>\S+)',
        re.IGNORECASE,
    )

    # Standard end marker; if present, only the first block is considered.
    end_marker_pattern = re.compile(r'-{3}\s+END', re.IGNORECASE)

    # ---------- Helper Functions ----------

    def normalize_value(raw: str) -> Any:
        """
        Normalize a raw value string into a more useful Python type:
        - Strip whitespace.
        - Map 'NULL'-like tokens to None.
        - Convert plain integers and floats.
        - Leave everything else as a string.
        """
        value = raw.strip()

        if value in {"NULL", "Null", "null", ""}:
            return None

        if re.fullmatch(r"-?\d+", value):
            try:
                return int(value)
            except ValueError:
                return value

        if re.fullmatch(r"-?\d+\.\d+", value):
            try:
                return float(value)
            except ValueError:
                return value

        return value

    def parse_context_block(lines: List[str], start_index: int) -> Tuple[Dict[str, Any], int]:
        """
        Parse a single PDP context starting at a 'PDP context on ...' line.

        Returns:
            (context_dict, next_index)

        context_dict:
            {
                "header": {...},
                "fields": {...}
            }
        """
        header_line = lines[start_index].strip()
        context: Dict[str, Any] = {"header": {}, "fields": {}}

        # Parse structured header if it matches the expected pattern
        header_match = header_pattern.match(header_line)
        if header_match:
            for key, val in header_match.groupdict().items():
                context["header"][key] = normalize_value(val)
        else:
            # Keep raw header for diagnostics if the pattern changes.
            context["header"]["raw"] = header_line

        i = start_index + 1

        # Skip separator line (e.g. "-------------------------------")
        if i < len(lines) and re.match(r'-{5,}', lines[i].strip()):
            i += 1

        fields: Dict[str, Any] = {}

        # Read key/value lines until we hit:
        # - Another "PDP context on" (next context)
        # - A known section/summary marker
        while i < len(lines):
            line = lines[i].rstrip("\n")
            stripped = line.strip()

            if (
                stripped.startswith("PDP context on")
                or stripped.startswith("Pdpcontext info")
                or stripped.startswith("PDP Context Info")
                or stripped.startswith("+++")
                or stripped.startswith("RETCODE")
                or stripped.startswith("(Number of results")
            ):
                break

            if "=" in line:
                key_part, value_part = line.split("=", 1)

                # Normalize key: collapse internal spaces, keep label readable.
                key = " ".join(key_part.strip().split())
                value = normalize_value(value_part)

                # Handle duplicate keys by turning the value into a list.
                if key in fields:
                    existing = fields[key]
                    if isinstance(existing, list):
                        existing.append(value)
                    else:
                        fields[key] = [existing, value]
                else:
                    fields[key] = value

            i += 1

        context["fields"] = fields
        return context, i

    def extract_retcode(chunk: str) -> Tuple[Optional[int], Optional[str]]:
        """
        Extract RETCODE and its message, if present.

        Example:
            'RETCODE = 0  Operation Success.'
        """
        match = re.search(r'RETCODE\s*=\s*(\d+)\s*(.*)', chunk)
        if not match:
            return None, None

        code = int(match.group(1))
        msg = match.group(2).strip() or None
        if msg:
            msg = msg.rstrip(".")
        return code, msg

    def has_no_matching_result(chunk: str) -> bool:
        """Return True if the output explicitly indicates no matching PDP context."""
        return "No matching result is found" in chunk

    # ---------- Main Parsing Logic ----------

    if not text or not text.strip():
        return {
            "retcode": None,
            "retmsg": None,
            "count": 0,
            "has_active_pdp": False,
            "contexts": [],
        }

    # If multiple END markers exist, we only consider the first logical query block.
    first_chunk = end_marker_pattern.split(text, maxsplit=1)[0].strip()

    retcode, retmsg = extract_retcode(first_chunk)

    result: Dict[str, Any] = {
        "retcode": retcode,
        "retmsg": retmsg,
        "count": 0,
        "has_active_pdp": False,
        "contexts": [],
    }

    # Short-circuit when we explicitly know there is no data.
    if has_no_matching_result(first_chunk):
        return result

    lines = first_chunk.splitlines()
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith("PDP context on"):
            context, i = parse_context_block(lines, i)
            result["contexts"].append(context)
        else:
            i += 1

    result["count"] = len(result["contexts"])
    result["has_active_pdp"] = result["count"] > 0

    return result

def mm_query_parser(text: str) -> Dict[str, str]:
    """
    Parse MMCTX output (USN) as a flat key/value dict.
    """
    out: Dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.rstrip("\r\n")
        if "(Number of results" in line:
            break

        s = line.strip()
        if not s:
            continue
        if s.startswith(("+++", "O&M", "%%/*", "---")):
            continue
        if s.startswith(("The result is as follows", "Pdpcontext info", "PDP Context Info")):
            continue

        if "=" not in s:
            continue

        k, v = s.split("=", 1)
        out[k.strip()] = v.strip()
    return out