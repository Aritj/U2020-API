#!/usr/bin/env python3
import os
import json

from dotenv import load_dotenv
from flask import Flask, request, jsonify, abort

from helper_functions import pdp_query_parser, mm_query_parser, validate_imsi, validate_msisdn
from connector import HuaweiMaeClient


app = Flask(__name__)

def validate_request_params() -> tuple[str, str]:
    """Validate and sanitize query_type/value from the request."""
    query_type = (request.args.get("query_type") or "").upper().strip()
    value = (request.args.get("value") or "").strip()

    # TODO: implement server side validation of input

    return query_type, value

@app.get("/pdp")
def get_ugw_pdp():
    """
    Query PDP context on UGW(s).

    Example:
        GET /pdp?query_type=MSISDN&value=298123456
        GET /pdp?query_type=IMSI&value=123456789012345
    """
    query_type, value = validate_request_params()
    query = f'DSP PDPCTXT:QUERYTYPE={query_type},{query_type}="{value}";'

    with HuaweiMaeClient(ip, port, username, password) as client:
        result = client.query_ne_dict(ugw_dict, "ugw", query, pdp_query_parser)

    return jsonify(result)


@app.get("/mm")
def get_usn_mm():
    """
    Query MM context on USN(s).

    Example:
        GET /mm?query_type=MSISDN&value=298123456
        GET /mm?query_type=IMSI&value=123456789012345
    """
    query_type, value = validate_request_params()
    query = f'DSP MMCTX:QUERYOPT=BY{query_type},{query_type}="{value}";'

    with HuaweiMaeClient(ip, port, username, password) as client:
        result = client.query_ne_dict(usn_dict, "omo", query, mm_query_parser)

    return jsonify(result)


if __name__ == "__main__":
    load_dotenv()

    # Connector variables
    ip = os.getenv("MAE_IP")
    port = int(os.getenv("MAE_PORT"))
    username = os.getenv("MAE_USERNAME")
    password = os.getenv("MAE_PASSWORD")

    # Query variables
    ugw_dict = json.loads(os.getenv("UGW_DICT"))
    usn_dict = json.loads(os.getenv("USN_DICT"))

    # Flask variables
    flask_debug = bool(os.getenv("FLASK_DEBUG"))
    flask_port = int(os.getenv("FLASK_PORT"))
    flask_host = os.getenv("FLASK_HOST")

    app.run(host=flask_host, port=flask_port, debug=flask_debug)
