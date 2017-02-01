import json
import logging

from edynam.connection import ADALConnection
from edynam.dynamics import Dynamics
from edynam.models import Optionset, ConnectionRole

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

# Connection Role Category is from Optionset -> Category (connectionrole_category)
optionsets = Optionset(reader)
opset = optionsets.get_by_name('connectionrole_category')
category_ops = optionsets.get_option_dict(opset['Options'])
logger.debug(category_ops)
category = optionsets.get_option_from('connectionrole_category', 'Sales')
logger.debug("value of %s = %s", 'Sales', category)

try:
    logger.debug(optionsets.get_option_from('connectionrole_category', 'NoSales'))
except KeyError as e:
    logger.warn(e)

try:
    # wrong name of optionset
    opset = optionsets.get_by_name('connectionrole_categoryx')
except Exception as e:
    logger.warn(e)

cr = ConnectionRole(reader)
logger.debug('role id of Territory Default Pricelist = %s', cr.get_roleid_of('Territory Default Pricelist', category))

try:
    category = optionsets.get_option_from('connectionrole_category', 'Team')
    logger.debug("value of %s = %s", 'Team', category)
    logger.debug('role id of Project Admin = %s', cr.get_roleid_of('Project Admin', category))
except KeyError as e:
    logger.error(e)
except AssertionError:
    logger.debug('The role is not defined in the category')
except Exception as e:
    logger.error('Unknow error: %s', str(e))

# I anticipate name and category values are correct
try:
    logger.debug(cr.get_roleid_of('Territory Default Pricelistx', category))
except AssertionError:
    logger.debug('Territory Default Pricelistx role is not defined in the category')
