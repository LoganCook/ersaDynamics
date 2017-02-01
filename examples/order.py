import logging

from edynam import connect
from edynam.models import Order, Product, Account

logging.basicConfig(level=logging.DEBUG,
                    format='%(levelname)s %(asctime)s %(filename)s %(module)s.%(funcName)s +%(lineno)d: %(message)s')

logger = logging.getLogger(__name__)
reader = connect('conf.json', 'saved_tokens.json')
assert reader is not None


product_handler = Product(reader)
# product_handler.list()
# product_handler.list_names()
rds_allocation_id = product_handler.get_id_of('RDS Allocation')
rds = product_handler.get_property_definitions('RDS Allocation')

order_handler = Order()
manager_role = {'id': '99acba33-f3f7-e611-8112-70106fa3d971', 'name': 'leader'}
admin_role = {'id': '8355863e-85fc-e611-810b-e0071b6685b1', 'name': 'admin'}
logger.debug(order_handler.get_product(rds_allocation_id, prod_props=rds, roles=[manager_role, admin_role]))

account_handler = Account()
account_name = 'University of South Australia'
account_id = account_handler.get_id_of(account_name)
nectar_allocation_id = product_handler.get_id_of('Nectar Allocation')

order_handler.get_account_products(account_id, manager_role)
# you can select a subset of properties you want, use aliases you like not the names in definition
# nectar = ({'id': 'bfa8c910-e7e8-e611-80f4-c4346bc5b2d4', 'type': 'valuestring', 'alias': 'openstackId', 'required': True},
#           {'id': 'ac47befd-05e9-e611-80f4-c4346bc5b2d4', 'type': 'valueinteger', 'alias': 'instances', 'required': False},
#           {'id': 'd0f2df56-06e9-e611-80f4-c4346bc5b2d4', 'type': 'valueinteger', 'alias': 'VCPUS', 'required': False})
nectar = product_handler.get_property_definitions('Nectar Allocation', ('OpenstackID', ))
logger.debug(nectar)
logger.debug(order_handler.get_product(nectar_allocation_id, prod_props=nectar))
logger.debug(order_handler.get_product(nectar_allocation_id, prod_props=nectar, account_id=account_id))

# FOR codes
order_handler = Order()
logger.debug(order_handler.get_for_codes())
logger.debug('FOR codes of all RDS Allocation')
logger.debug(order_handler.get_for_codes(rds_allocation_id))

logger.debug('FOR codes of all RDS Allocation of %s' % account_name)
logger.debug(order_handler.get_for_codes(rds_allocation_id, account_id=account_id))
