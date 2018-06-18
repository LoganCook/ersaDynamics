import logging

from edynam import connect
from edynam.models import Product, Substitute, ProductPricelist

logging.basicConfig(level=logging.DEBUG,
                    format='%(levelname)s %(asctime)s %(filename)s %(module)s.%(funcName)s +%(lineno)d: %(message)s')

# # edynam's logger level can be controlled
# logging.getLogger("edynam").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


# Another way of connecting to Dynamics instance
reader = connect('sandbox_conf.json', 'saved_tokens.json')

product_handler = Product(reader)
product_handler.list()
# product_handler.list_names()
try:
    product_handler.get_id_of('RDS ALLOCATION')
    rds = product_handler.get_property_definitions('RDS ALLOCATION')
except AssertionError:
    logger.warning('Wrong product name: RDS ALLOCATION')

# product substitutes
substitute_handler = Substitute(reader)
product_links = substitute_handler.list()
logger.debug(product_links)
substitute_handler.get_linked_from(product_links[0]['productid'])

# ProductPricelist
pricelist_handler = ProductPricelist(reader)
logger.debug(pricelist_handler.list())
result_json = pricelist_handler.get_prices('eRSA Account')
logger.debug(result_json)
