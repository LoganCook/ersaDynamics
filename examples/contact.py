import logging

from edynam import connect
from edynam.models import Contact, Account

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

contact_handler = Contact(reader)
# contact_handler.list()
logger.debug(contact_handler.get_usernames())
logger.debug(contact_handler.get_usernames_of('a779d575-c162-e611-80e3-c4346bc43f98'))

account_handler = Account(reader)
account_handler.get_ancestors('e929372b-5063-e611-80e3-c4346bc4de3c')
# account_handler.list()
account_handler.get_top()
uni_1 = account_handler.get_id_of('University of Adelaide')
account_handler.get_child_of(uni_1)
