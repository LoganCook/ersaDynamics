import logging

from edynam import connect
from edynam.models import Order, Product, Contact

logging.basicConfig(level=logging.DEBUG,
                    format='%(levelname)s %(asctime)s %(filename)s %(module)s.%(funcName)s +%(lineno)d: %(message)s')

# # edynam's logger level can be controlled
# logging.getLogger("edynam").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# One way of connecting to Dynamics instance
# conf = 'conf.json'
# with open(conf, 'r') as jf:
#     parameters = json.load(jf)

# conn = ADALConnection(parameters)
# conn.retrieve('saved_tokens.json')

# reader = Dynamics(conn)

# Another way of connecting to Dynamics instance
reader = connect('conf.json', 'saved_tokens.json')
assert reader is not None

# project_handler = Project(reader)
# project_handler.list()

product_handler = Product(reader)
# product_handler.list()
# product_handler.list_names()
product_handler.get_id_of('RDS ALLOCATION')
rds = product_handler.get_property_definitions('RDS ALLOCATION')

# service_handler = Service(reader)
# service_handler.get_top()
# service_handler.list()
# service_handler.search('f026e3808f914a458fbbf1143a1a28d1')
# service_handler.search('fusa-med-fcicembl-80')
# service_handler.get_services_of('4a5d5a78-c962-e611-80e3-c4346bc516e8', ('5963ddb8-a783-e611-80e7-c4346bc4beac', ))

contact_handler = Contact(reader)
# contact_handler.list()
logger.debug(contact_handler.get_usernames())
logger.debug(contact_handler.get_usernames_of('a779d575-c162-e611-80e3-c4346bc43f98'))

# account_handler = Account(reader)
# account_handler.get_ancestors('e929372b-5063-e611-80e3-c4346bc4de3c')
# # account_handler.list()
# account_handler.get_top()
# uni_1 = account_handler.get_id_of('University of Adelaide')
# account_handler.get_child_of(uni_1)
# service_handler.get_services_of(uni_1)
