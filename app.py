#!/usr/bin/env python3
import os
import json

from dotenv import load_dotenv
from flask import Flask, request, jsonify

from helper_functions import pdp_query_parser, mm_query_parser, validate_msisdn
from connector import HuaweiMaeClient

# Load .env variables
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

# Flask app
app = Flask(__name__)


@app.get("/GetPDP/<msisdn>")
def get_pdp(msisdn):
    """
    Query packet data protocol (PDP) context on UGW(s).

    Example:
        GET /GetPDP/298123456
    """
    if not validate_msisdn(msisdn):
        return jsonify({"Error": f"{msisdn} is an invalid MSISDN."}), 401
    
    pdp_query = f'DSP PDPCTXT:QUERYTYPE=MSISDN,MSISDN="{msisdn}";'

    try:
        with HuaweiMaeClient(ip, port, username, password) as connector:
            result = connector.query_ne_dict(ugw_dict, "ugw", pdp_query, pdp_query_parser)

        return jsonify(result)

    except Exception as e:
        print(e)
        return jsonify({"Error": f'{e}'})


@app.get("/GetMM/<msisdn>")
def get_mm(msisdn):
    """
    Query mobility management (MM) context on USN(s).

    Example:
        GET /GetMM/298123456
    """
    if not validate_msisdn(msisdn):
        return jsonify({"Error": f"{msisdn} is an invalid MSISDN."}), 401

    mm_query = f'DSP MMCTX:QUERYOPT=BYMSISDN,MSISDN="{msisdn}";'

    try:
        with HuaweiMaeClient(ip, port, username, password) as connector:
            result = connector.query_ne_dict(usn_dict, "omo", mm_query, mm_query_parser)

        return jsonify(result)
    except Exception as e:
        return jsonify({"Error": e})


if __name__ == "__main__":
    app.run(host=flask_host, port=flask_port, debug=flask_debug)
