import json
import logging

from edynam.connection import ADALConnection
from edynam.dynamics import Dynamics


logging.getLogger("requests").setLevel(logging.WARNING)

web_api_client = None

def connect(parameter_json, saved_tokens_json):
    """Connect to Dynamics and returns a HTTP request handler for Web API calls"""
    # returned web_api_client is only useful when no model has been defined for
    # a Dynamics entity, you want to do raw http request but don't want to deal
    # with authentication.
    global web_api_client
    with open(parameter_json, 'r') as jf:
        parameters = json.load(jf)

    conn = ADALConnection(parameters)
    conn.retrieve(saved_tokens_json)

    web_api_client = Dynamics(conn)
    return web_api_client
