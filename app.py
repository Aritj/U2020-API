#!/usr/bin/env python3
from flask import Flask, request, jsonify
from helper_functions import pdp_query_parser, validate_msisdn
from connector import HuaweiMaeClient
from config import Config

# Flask app
app = Flask(__name__)

@app.get("/health")
def health():
    return jsonify({"status": "ok"}), 200

@app.get("/GetPDP/<msisdn>")
def get_pdp(msisdn):
    """
    Query packet data protocol (PDP) context on UGW(s).

    Example:
        GET /GetPDP/298123456
    """
    if not validate_msisdn(msisdn):
        return jsonify({"Error": f"{msisdn} is an invalid MSISDN."}), 400
    
    query = f'DSP PDPCTXT:QUERYTYPE=MSISDN,MSISDN="{msisdn}";'
    vnfc = "ugw"

    try:
        with HuaweiMaeClient(Config.ip, Config.port, Config.username, Config.password, Config.timeout) as connector:
            result = connector.query_ne_dict(
                Config.ugw_dict,
                vnfc,
                query,
                pdp_query_parser
            )

        return jsonify(result), 200

    except Exception as e:
        return jsonify({"Error": f'{e}'}), 502

if __name__ == "__main__":
    app.run(host=Config.flask_host, port=Config.flask_port, debug=Config.flask_debug)
