import json
import logging

from edynam.connection import ADALConnection
from edynam.dynamics import Dynamics
from edynam.models import Optionset

logging.basicConfig(level=logging.DEBUG,
                    format='%(levelname)s %(asctime)s %(filename)s %(module)s.%(funcName)s +%(lineno)d: %(message)s')

logging.getLogger("requests").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

conf = 'conf.json'
with open(conf, 'r') as jf:
    parameters = json.load(jf)

conn = ADALConnection(parameters)
conn.retrieve('saved_tokens.json')

reader = Dynamics(conn)

optionsets = Optionset(reader)
optionsets.list()
# get_by_id and get_by_name should return the same object
logger.debug(optionsets.get_by_id('3041d03c-4166-4814-a2d4-1e3d93caf2f1'))
opset = optionsets.get_by_name('connectionrole_category')
logger.debug(optionsets.get_option_dict(opset['Options']))
