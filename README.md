# Huawei U2020 / iMaster MAE NBI – Simple REST API PoC

This project is a **minimal REST API** that shows how to integrate with the **Huawei U2020 / iMaster MAE northbound interface (NBI)** over the MAE CLI.

It is not a full-featured product.
It is a small, readable proof-of-concept intended to be copied, modified, and extended for your own purposes (additional commands, endpoints, auth, TLS, etc.). 

---

## What it does

The API opens a TCP/Telnet session to the MAE NBI, runs Huawei CLI commands, parses the output, and returns JSON.

Current endpoints:

* `GET /pdp`

  * Runs `DSP PDPCTXT` on one or more UGWs
  * Returns parsed PDP context(s)
* `GET /mm`

  * Runs `DSP MMCTX` on one or more USNs
  * Returns parsed MM context

The MAE connection and per-NE queries are handled by `HuaweiMaeClient` in `connector.py`. 
Parsing logic and simple validators live in `helper_functions.py`. 

---

## Project structure

* `app.py`
  Flask application, HTTP endpoints, loading configuration from `.env`, and wiring everything together. 

* `connector.py`
  Thin Huawei MAE connector using `telnetlib`, with helpers to:

  * log in (`LGI`)
  * register NE (`REG NE`)
  * register VNFC (`REG VNFC`)
  * run a query for each NE in a dict and parse the result via a callback. 

* `helper_functions.py`

  * `pdp_query_parser(text)` – parses `DSP PDPCTXT` output into structured data (multiple PDP contexts per subscriber supported).
  * `mm_query_parser(text)` – parses `DSP MMCTX` output into a flat key/value dict.
  * `validate_msisdn`, `validate_imsi` – basic regex validators (currently not fully wired into the API). 

---

## Configuration (.env)

All runtime configuration lives in a `.env` file loaded by `python-dotenv` in `app.py`. 

Example:

```env
# MAE connector
MAE_IP=10.10.10.10
MAE_PORT=31114
MAE_USERNAME=my_username
MAE_PASSWORD=secret-password

# UGW / USN inventory (JSON objects: name -> IP)
UGW_DICT={"UGW01":"1.2.3.4","UGW02":"5.6.7.8","UGW03":"9.10.11.12"}
USN_DICT={"USN01":"8.7.6.5","USN02":"4.3.2.1"}

# Flask
FLASK_HOST=0.0.0.0
FLASK_PORT=8000
FLASK_DEBUG=1
```

> Note: `UGW_DICT` and `USN_DICT` are parsed as JSON in `app.py`, so they must be valid JSON objects, *not* Python dict literals. 

---

## Running the API

1. Make sure you have Python 3.10+.

2. Install dependencies (minimal set):

   ```bash
   pip install flask python-dotenv
   ```

3. Create a `.env` file in the project root (see example above).

4. Start the API:

   ```bash
   python app.py
   ```

5. The API will listen on `http://FLASK_HOST:FLASK_PORT` from your `.env` (for example `http://0.0.0.0:8000`).

---

## Endpoints

### `/pdp` – PDP context on UGW(s)

Runs the Huawei command:

```text
DSP PDPCTXT:QUERYTYPE=<QUERY_TYPE>,<QUERY_TYPE>="<VALUE>";
```

for each configured UGW NE and returns parsed output.

**Request**

* Method: `GET`
* Query parameters:

  * `query_type`: `MSISDN` or `IMSI`
  * `value`: subscriber MSISDN or IMSI (string)

Example:

```bash
curl "http://localhost:8000/pdp?query_type=MSISDN&value=123456789"
```

**Response (simplified shape)**

```json
{
  "UGW01 (1.2.3.4)": {
    "retcode": 0,
    "retmsg": "Operation Success",
    "count": 2,
    "has_active_pdp": true,
    "contexts": [
      {
        "header": {
          "node": "UGW_SP_RU_0064",
          "sgid": 10,
          "context_index": 36603,
          "...": "..."
        },
        "fields": {
          "APN name": "APN",
          "IPv4 PDP address": "10.1.2.3",
          "IMSI": "1234...",
          "User Location Information": [
            "Type:ECGI;...",
            "Type:TAI;..."
          ],
          "...": "..."
        }
      },
      {
        "header": { "...": "..." },
        "fields": {
          "APN name": "ims",
          "...": "..."
        }
      }
    ]
  },
  "UGW02 (5.6.7.8)": {
    "retcode": 20111,
    "retmsg": "There is no data in the table",
    "count": 0,
    "has_active_pdp": false,
    "contexts": []
  }
}
```

The heavy lifting is done by `pdp_query_parser()` which splits multiple `PDP context on ...` blocks and parses key/value pairs per context. 

### `/mm` – MM context on USN(s)

Runs the Huawei command:

```text
DSP MMCTX:QUERYOPT=BY<QUERY_TYPE>,<QUERY_TYPE>="<VALUE>";
```

for each configured USN and returns a flat dict of parsed MM context fields.

**Request**

* Method: `GET`
* Query parameters:

  * `query_type`: `MSISDN` or `IMSI`
  * `value`: subscriber MSISDN or IMSI

Example:

```bash
curl "http://localhost:8000/mm?query_type=MSISDN&value=123456789"
```

**Response (simplified shape)**

```json
{
  "USN01 (8.7.6.5)": {
    "IMSI": "1234...",
    "MSISDN": "123456789",
    "ME identity": "1122334455667788",
    "MM state": "ECM-CONNECTED",
    "User Location Information": "Type:SAI;MCC...",
    "...": "..."
  },
  "USN02 (4.3.2.1)": { "...": "..." }
}
```

---

## Extending the PoC

This codebase is deliberately small and straightforward:

* To add new MAE commands, create new parsers in `helper_functions.py` and new endpoints in `app.py`.
* To support SSL/TLS towards MAE, you can wrap the telnet socket with `ssl` or swap out `telnetlib` for an SSL-capable client in `HuaweiMaeClient`.
* To validate input strictly, use `validate_msisdn` and `validate_imsi` (already imported in `app.py`) inside `validate_request_params()`.

Use this project as a starting point to build whatever higher-level features you need (subscriber lookup tools, dashboards, alarms, etc.) on top of the Huawei U2020 / iMaster MAE NBI.
