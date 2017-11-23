import json
import logging

from edynam.connection import ADALConnection
from edynam.dynamics import Dynamics
from edynam.models import Order, OrderDetail, DynamicProperty, DynamicPropertyOptionsetItem

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

property_service = DynamicProperty(reader)
logger.debug(property_service.list())

propertyoptionset_service = DynamicPropertyOptionsetItem(reader)
logger.debug(propertyoptionset_service.list())

order_service = Order(reader)
order = order_service.get('9c07fafd-25cf-e711-812f-480fcff237d1')
logger.debug(order)

orderdetail_service = OrderDetail(reader)
products = orderdetail_service.get_products_of('9c07fafd-25cf-e711-812f-480fcff237d1')

for prod in products:
    logger.debug(prod)
    orderdetail_service.get_property_values(prod['salesorderdetailid'])
