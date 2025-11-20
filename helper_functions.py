import re
import pandas as pd
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

# Load external files as dataframes
file_directory_path = "files"

mnc_mcc_df = pd.read_csv(f'{file_directory_path}/mcc-mnc.csv', sep=';')
ran_df = pd.read_excel(f'{file_directory_path}/ran.xlsx')
tac_df = pd.read_csv(f'{file_directory_path}/tacdb.csv', sep=",")

# Coerce to numeric
ran_df["cellId"] = pd.to_numeric(ran_df["cellId"], errors="coerce")
ran_df["PCI"] = pd.to_numeric(ran_df["PCI"], errors="coerce")
ran_df["Azimuth"] = pd.to_numeric(ran_df["Azimuth"], errors="coerce")

# Drop rows where either key column is NaN
ran_df = ran_df.dropna(subset=["cellId", "PCI", "Azimuth"])

# Now safe to cast to plain int
ran_df["cellId"] = ran_df["cellId"].astype(int)
ran_df["PCI"] = ran_df["PCI"].astype(int)
ran_df["freqBand"] = ran_df["freqBand"].astype(int)
ran_df["earfcndl"] = ran_df["earfcndl"].astype(int)
ran_df["Azimuth"] = ran_df["Azimuth"].astype(int)

# Named indexes
RETCODE_LINE = 5

def validate_msisdn(text: str) -> bool:
    return bool(MSISDN_RE.match(text))

def _normalize_keys(obj):
    """
    Recursively normalize keys in dictionaries:
    - lowercase
    - replace spaces with underscores
    Works for nested dicts and lists.
    """
    if isinstance(obj, dict):
        new_dict = {}
        for k, v in obj.items():
            new_key = k.lower().replace(" ", "_")
            new_dict[new_key] = _normalize_keys(v)
        return new_dict

    elif isinstance(obj, list):
        return [_normalize_keys(item) for item in obj]

    else:
        return obj

def _df_query(df, mask):
    rows = df[mask]

    if rows.empty:
        return None

    return json.loads(rows.iloc[0].to_json())

def _get_cell(site_id: int, cell_id: int):
    dataframe = ran_df

    # NET (RAN) use concatenated site IDs in the site name, e.g. 1251 -> "HALSUR_TORSHAVN_125" (we query for "*_125").
    mask = (
        (dataframe["cellId"] == cell_id) &
        (dataframe["Site Name"].str.endswith(f"_{site_id//10}"))
    )

    return _df_query(dataframe, mask)

def _get_operator(mcc, mnc):
    dataframe = mnc_mcc_df 

    mask = (
        (dataframe["MCC"] == mcc) &
        (dataframe["MNC"] == mnc)
    )

    return _df_query(dataframe, mask)

def _get_handset(tac):
    dataframe = tac_df

    mask = (dataframe["tac"] == tac)

    return _df_query(dataframe, mask)


def parse_imei(context):
    imei = context.pop("IMEI")

    dataframe = tac_df
    tac = imei[:8]
    handset_info = _get_handset(tac)

    output = {
        "imei": int(imei),
        "handset_info": handset_info,
    }

    return output

def parse_user_location_information(context):
    """Return (eNB_ID, sector_ID) from LTE E-UTRAN Cell Identifier (ECI)."""
    uli: [str] = context.pop("User Location Information") # ['Type:ECGI;MCC:288;MNC:01;ECI:320276', 'Type:TAI;MCC:288;MNC:02;TAC:2000']
    
    # Named indexes
    ecgi_index = 0
    tai_index = 1
    type_index = 0
    mcc_index = 1
    mnc_index = 2
    eci_tac_index = 3

    # Identify each record and split it into parts
    ecgi_parts = uli[ecgi_index].split(";") # ['Type:ECGI', 'MCC:288', 'MNC:01', 'ECI:320276']
    tai_parts = uli[tai_index].split(";")   # ['Type:TAI', 'MCC:288', 'MNC:02', 'TAC:2000']

    # ECGI
    _, ecgi_type_value = ecgi_parts[type_index].split(":")              # ('Type', 'ECGI')
    ecgi_mcc_key, ecgi_mcc_value = ecgi_parts[mcc_index].split(":")     # ('MCC', '288')
    ecgi_mnc_key, ecgi_mnc_value = ecgi_parts[mnc_index].split(":")     # ('MNC', '01')
    ecgi_eci_key, ecgi_eci_value = ecgi_parts[eci_tac_index].split(":") # ('ECI', '320276')

    # TAI
    _, tai_type_value = tai_parts[type_index].split(":")                # ('Type', 'TAI')
    tai_mcc_key, tai_mcc_value = tai_parts[mcc_index].split(":")        # ('MCC', '288')
    tai_mnc_key, tai_mnc_value = tai_parts[mnc_index].split(":")        # ('MNC', '02')
    tai_tac_key, tai_tac_value = tai_parts[eci_tac_index].split(":")    # ('TAC', '2000')

    # Convert MCC/MNC strings to integers
    ecgi_mcc_value = int(ecgi_mcc_value)    # 288
    ecgi_mnc_value = int(ecgi_mnc_value)    # 1
    tai_mcc_value = int(tai_mcc_value)      # 288
    tai_mnc_value = int(tai_mnc_value)      # 2
    tai_tac_value = int(tai_tac_value)      # 2000

    # Get operator info
    ecgi_operator_info: pd.DataFrame = _get_operator(ecgi_mcc_value, ecgi_mnc_value)
    tai_operator_info: pd.DataFrame = _get_operator(tai_mcc_value, tai_mnc_value)

    # Get RAN information. LTE ECI split: 20-bit eNB ID, 8-bit sector ID.
    ecgi_eci_value = int(ecgi_eci_value)  # 320276
    site_id = ecgi_eci_value >> 8        # bit-shifting
    cell_id = ecgi_eci_value & 0xff

    # RAN-D Cell Map concatenates the last ID digit in the site name, e.g. 1251 -> "HALSUR_TORSHAVN_125".
    ran_info = _get_cell(site_id, cell_id)

    # Format output
    output = {
        ecgi_type_value.lower(): {
            ecgi_mcc_key.lower(): ecgi_mcc_value,
            ecgi_mnc_key.lower(): ecgi_mnc_value,
            ecgi_eci_key.lower(): ecgi_eci_value,
            "operator_info": ecgi_operator_info,
            "ran_info": ran_info,
        },
        tai_type_value.lower(): {
            tai_mcc_key.lower(): tai_mcc_value,
            tai_mnc_key.lower(): tai_mnc_value,
            tai_tac_key.lower(): tai_tac_value,
            "operator_info": tai_operator_info,
        }
    }

    return output

def parse_dscp(context):
    return  {
        "downlink": int(context.pop("DOWN DSCP")),
        "uplink": int(context.pop("UP DSCP")),
    }

def parse_apn_ambr(context):
    suffix_to_remove = -(len("Kbps"))
    return {
        "downlink": int(context.pop("APN AmbrDown")[:suffix_to_remove]),
        "uplink": int(context.pop("APN AmbrUp")[:suffix_to_remove]),
    }

def parse_arp(context):
    return {
        "priority_level": int(context.pop("Allocation/Retention PRI")),
        "preemption_capability": bool(context.pop("Allocation/Retention PRI PCI")),
        "preemption_vulnerability": bool(context.pop("Allocation/Retention PRI PVI")),
    }

def parse_requested_arp(context):
    return {
        "priority_level": int(context.pop("Request Allocation/Retention PRI")),
        "preemption_capability": bool(context.pop("Request Allocation/Retention PRI PCI")),
        "preemption_vulnerability": bool(context.pop("Request Allocation/Retention PRI PVI")),
    }

def parse_gbr(context):
    downlink = context.pop("Gua Bit Rate for Downlink")
    uplink = context.pop("Gua Bit Rate for Uplink")

    return {
        "downlink": None if downlink == "NULL" else downlink,
        "uplink": None if uplink == "NULL" else uplink,
    }

def parse_requested_gbr(context):
    downlink = context.pop("Request Gua Bit Rate for Downlink")
    uplink = context.pop("Request Gua Bit Rate for Uplink")

    return {
        "downlink": None if downlink == "NULL" else downlink,
        "uplink": None if uplink == "NULL" else uplink,
    }

def parse_mbr(context):
    downlink = context.pop("Max Bit Rate for Downlink")
    uplink = context.pop("Max Bit Rate for Uplink")

    return {
        "downlink": None if downlink == "NULL" else downlink,   # "NULL" to None
        "uplink": None if uplink == "NULL" else uplink,         # "NULL" to None
    }

def parse_requested_mbr(context):
    downlink = context.pop("Request Max Bit Rate for Downlink")
    uplink = context.pop("Request Max Bit Rate for Uplink")

    return {
        "downlink": None if downlink == "NULL" else downlink,   # "NULL" to None
        "uplink": None if uplink == "NULL" else uplink,         # "NULL" to None
    }

def parse_qos(context):
    qci = int(context.pop("Qos Class Identifier"))
    arp = parse_arp(context)
    dscp = parse_dscp(context)
    gbr = parse_gbr(context)
    mbr = parse_mbr(context)

    return {
        "qci": qci,
        "arp": arp,
        "dscp": dscp,
        "gbr": gbr,
        "mbr_kbps": mbr,
    }

def parse_requested_qos(context):
    requested_qci = int(context.pop("Request Qos Class Identifier"))
    requested_arp = parse_requested_arp(context)
    requested_gbr = parse_requested_gbr(context)
    requested_mbr = parse_requested_mbr(context)

    return {
        "qci": requested_qci,
        "arp": requested_arp,
        "gbr_kbps": requested_gbr,
        "mbr_kbps": requested_mbr,
    }

def parse_charging_information(context):
    prefix_to_remove = len("0x")

    charging_id = int(context.pop("Charging ID"))
    charging_rule_name = context.pop("Charge Rule Base Name")
    requested_charging_characteristic_hex = context.pop("Requested Charging Characteristic")[prefix_to_remove:]
    requested_charging_characteristic = int(requested_charging_characteristic_hex, 16)
    negotiated_charging_characteristic_hex = context.pop("Negotiated Charging Characteristic")[prefix_to_remove:]
    negotiated_charging_characteristic = int(requested_charging_characteristic_hex, 16)

    # "Yes" / "No" to bool
    content_charging_flag = (context.pop("Content Charging Flag") == "Yes")
    offline_charging = (context.pop("Offline Charging Flag") == "Yes")
    online_charging = (context.pop("Online Charging Flag") == "Yes")
    sgw_offline_charging = (context.pop("SGW Offline Charging Flag") == "Yes")

    return {
        "id": charging_id,
        "rule_name": charging_rule_name,
        "requested_charging_characteristic": requested_charging_characteristic,
        "negotiated_charging_characteristic": negotiated_charging_characteristic,
        "content_charging_flag": content_charging_flag,
        "offline_charging": offline_charging,
        "online_charging": online_charging,
        "sgw_offline_charging": sgw_offline_charging,
    }

def parse_metadata(context):
    return {
        "node": context.pop("node"),
        "sgid": context.pop("sgid"),
        "session_index": context.pop("session_index"),
        "context_index": context.pop("context_index"),
        "filter_index": context.pop("filter_index"),
        "bearer_index": context.pop("bearer_index"),
        "gptu_index": context.pop("gtpu_index"),
    }

def parse_overview(context):
    return None

def reformat(context):
    context["bearer_id"] = int(context.pop("EPS Bearer ID"))
    context["default_bearer"] = (context.pop("Default Bearer") == "Yes")
    context["location"] = parse_user_location_information(context)
    context["imei"] = parse_imei(context)
    context["qos"] = parse_qos(context)
    context["requested_qos"] = parse_requested_qos(context)
    context["apn_ambr (kbps)"] = parse_apn_ambr(context)
    context["charging"] = parse_charging_information(context)
    context["metadata"] = parse_metadata(context)
    context["overview"] = parse_overview(context)

    return context

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

    for context in contexts:
        context = reformat(context)

    contexts = _normalize_keys(contexts)

    return contexts

def mm_query_parser(text: str) -> Dict[str, str]:
    """
    Parse MMCTX output (USN) as a flat key/value dict.
    """
    text_lines = text.splitlines()
    code, message = extract_retcode(text_lines[RETCODE_LINE])

    # Exit early if query is unsuccessful
    if code != 0:
        return None

    # Named indexes
    MM_DATA_START_LINE = 9
    MM_DATA_END_LINE = -2

    # Skip header information, only parse data
    out = {}

    for line in text_lines[MM_DATA_START_LINE:MM_DATA_END_LINE]:
        k, v = line.strip().split("=", 1)
        out[k.strip()] = v.strip()

    return out