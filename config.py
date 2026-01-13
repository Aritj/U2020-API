import os
import json

from dotenv import load_dotenv
        
# Load .env variables
load_dotenv()

class Config:
    # Connector variables
    ip = os.getenv("MAE_IP")
    port = int(os.getenv("MAE_PORT"))
    username = os.getenv("MAE_USERNAME")
    password = os.getenv("MAE_PASSWORD")
    timeout = int(os.getenv("MAE_TIMEOUT"))

    # Query variables
    ugw_dict = json.loads(os.getenv("UGW_DICT"))
    
    # Flask variables
    flask_debug = bool(os.getenv("FLASK_DEBUG"))
    flask_port = int(os.getenv("FLASK_PORT"))
    flask_host = os.getenv("FLASK_HOST")