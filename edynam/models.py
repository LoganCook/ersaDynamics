import re
import logging

from .fetchxml import FetchXML
from .dynamics import FORMATTED_VALUE_SUF

logger = logging.getLogger(__name__)


class Handler(object):
    """Base class for all Dynamics models

    It contains common methods for building queries.
    """

    # all date type fields have value in UTC which need to be converted into local time
    END_POINT = ''
    FIELDS = ()
    LOOKUPS = ()
    MAPS = {}

    def __init__(self, backend=None):
        """Refresh an expired access token

        :param Dynamics backend: Dynamics instance to handle requests. Default is None
        """
        if backend is None:
            from . import web_api_client
            assert web_api_client is not None
            self._backend = web_api_client
        else:
            self._backend = backend
        self.instance = None

    def _build_list(self, key, attr, extra):
        # construct a dictionary with
        fields = list(getattr(self, attr, []))
        fields.extend(extra)
        if len(fields):
            return {key: ','.join(fields)}
        else:
            return None

    @staticmethod
    def _extract_key(key):
        """Extract a key for mapping if it is the key of a formated value

        :returns tuple: first is extracted value,
                        second is boolean to represent if it in raw-formatted value pair
        """
        # the primary key is not expanded when retrieved with prefer header formatted value
        # in map, they are just key_of_formatted: map_to_string
        pformatted = re.compile(r'(.*)@' + FORMATTED_VALUE_SUF + '$')
        formatted = pformatted.match(key)
        if formatted:
            return formatted.group(1), True
            # plookup = re.compile(r'^_(.*)_value$')
            # lookup = plookup.match(formatted.group(1))
            # if lookup:
            #     logger.debug('Formatted, is a lookup')
            #     return lookup.group(1), True
            # else:
            #     logger.debug('Formatted, not a lookup')
            #     return formatted.group(1), False
        else:
            return key, False

    def _select_expands(self, lookups=None):
        """Convert expand items into select

        This makes the query result has id of expanded item:
        EXPAND --> _EXPAND_value (see MS Dynamics Lookup properties)

        :param iterator lookups: field names to be expanded
        """
        plookups = re.compile(r'^(\S+)\(\$.+\=.+\)$')
        if lookups is None:
            lookups = getattr(self, 'LOOKUPS', ())

        # Skip adding customerid when they are in expand lookups
        pcustomerid = re.compile('.*customerid_(account|contact)$')
        exp_selects = []
        for exp in lookups:
            exp_match = plookups.match(exp)
            if exp_match:
                if not pcustomerid.match(exp_match.group(1)):
                    exp_selects.append('_' + exp_match.group(1) + '_value')
        return exp_selects

    def select(self, extra=None):
        """Construct $select list for what to return

        $select includes _xx_values of those in $expand
        """
        selects = self._select_expands()
        if extra:
            selects.extend(extra)
        return self._build_list('$select', 'FIELDS', selects)

    def expand(self):
        return self._build_list('$expand', 'LOOKUPS', [])

    @staticmethod
    def create_select(fields):
        assert isinstance(fields, tuple) or isinstance(fields, list)
        return {'$select': ','.join(fields)}

    @staticmethod
    def create_filter(filters):
        # TODO: this looks too simple, see below comment
        # Using Filter Expressions in OData URIs
        # https://msdn.microsoft.com/en-us/library/hh169248(v=nav.90).aspx
        # especially, string need single quotation marks, date needs datetime:'blar'
        # id's are treated as number
        return {'$filter': filters}

    def map(self, item):
        """Map field names to desired names

        Simple key mapping is done by field-to-field map.
        For formatted pair:
            xxx: value,
            xxx@FORMATTED_VALUE_SUF: value
        mapping can be defined by a dict with either keys of 'raw' or 'formatted' or both.
        Mapping for expanded properties are in a nested dict. For _xxx_value:
        xxx: {raw_key_name: new_key_name}
        Currently, $expand only has one level.

        If no mapping is defined, return original values.

        :param dict item: whose keys will be mapped to other keys and in a flat structure
        """
        # item = self._exclude_raw(item)
        if not hasattr(self, 'MAPS'):
            return item

        flatted = {}
        for k, v in item.items():
            extracted_key, is_formatted = self._extract_key(k)
            if extracted_key in self.MAPS:
                if isinstance(self.MAPS[extracted_key], dict):
                    if 'formatted' in self.MAPS[extracted_key] or 'raw' in self.MAPS[extracted_key]:
                        mapping_key = 'formatted' if is_formatted else 'raw'
                        if mapping_key in self.MAPS[extracted_key]:
                            flatted[self.MAPS[extracted_key][mapping_key]] = v
                    elif v:
                        # for expanded values
                        for maping_from, mapping_to in self.MAPS[extracted_key].items():
                            flatted[mapping_to] = v[maping_from]
                    else:
                        flatted[k] = v
                else:
                    # simple name mapping
                    flatted[self.MAPS[extracted_key]] = v
            else:
                flatted[k] = v
        return flatted

    def map_list(self, items):
        mapped = []
        for item in items:
            mapped.append(self.map(item))
        return mapped

    @staticmethod
    def _exclude_raw(item):
        """Exclude unformatted raw values"""
        excluded = {}
        if not isinstance(item, dict):
            raise ValueError('Wrong type for excluding raw value: has to be a dict')

        for k in item.keys():
            if FORMATTED_VALUE_SUF in k:
                continue
            key_of_formatted = k + '@' + FORMATTED_VALUE_SUF
            if key_of_formatted in item:
                excluded[k] = item[key_of_formatted]
            else:
                excluded[k] = item[k]
        return excluded

    def _build_params(self, selects, expands, extra):
        params = {}
        if selects is None:
            selects = self.select()
        if expands is None:
            expands = self.expand()

        if selects:
            params.update(selects)
        if expands:
            params.update(expands)
        if extra:
            params.update(extra)
        return params

    def list(self, selects=None, expands=None, extra=None):
        try:
            data = self._backend.get(self.END_POINT,
                                     self._build_params(selects, expands, extra))
        except LookupError as err:
            logger.error("Query failed, %s", str(err))
            return []
        else:
            # logger.debug(data)
            for item in data:
                # logger.debug(item)
                logger.debug(self.map(item))
                # break
            return data

    def get(self, entity_id, selects=None, expands=None, extra=None):
        """Get entity by its id"""
        return self.map(self._backend.get('%s(%s)' % (self.END_POINT, entity_id),
                                          self._build_params(selects, expands, extra)))

    def load(self, entity_id):
        """Load an entity instance by its id"""
        self.instance = self.get(entity_id)

    def get_id_of(self, name):
        """Get ID of an entity

        Only works for entities which has name property and its value is unique
        """
        # Does not work for entities like Contact, Project which does not have name
        # or the entities whose names are not unique
        if hasattr(self, 'ENTITY'):
            entity_id = self.ENTITY + 'id'
        else:
            entity_id = self.END_POINT[:-1] + 'id'
        data = self._backend.get(self.END_POINT, {'$select': entity_id, '$filter': "name eq '%s'" % name})
        assert len(data) < 2
        return data[0][entity_id]


class Project(Handler):
    # FIXME: Project probably is not needed for reporting
    END_POINT = 'msdyn_projects'
    FIELDS = ('msdyn_comments', 'msdyn_subject', 'new_project_type', 'msdyn_stagename',
              'msdyn_description', 'msdyn_progress', 'msdyn_scheduledstart', 'msdyn_scheduledend',
              'msdyn_totalplannedcost', 'msdyn_plannedhours', 'msdyn_wbsduration')
    LOOKUPS = ('msdyn_customer($select=name)', )
    MAPS = {'msdyn_customer': {'name': 'billing_org'}}


class Product(Handler):
    """Chargeable items

    Each item can have unit (defaultuomid), unit group (defaultuomscheduleid),
    parent product (parentproductid). hierarchypath is a string representation of relationship
    between related products.
    """
    ENTITY = 'product'  # used in fetchXml, avoid guessing singular or plural
    END_POINT = 'products'
    FIELDS = ('name', 'description', 'hierarchypath', 'price', 'productnumber', 'validtodate', 'validfromdate', 'producturl', 'productstructure')
    LOOKUPS = ('parentproductid($select=name)', 'defaultuomid($select=name)', 'defaultuomscheduleid($select=name)')

    @classmethod
    def _active_product_filter(cls):
        """Filter of published products not product families"""
        return cls.create_filter('statecode eq 0 and productstructure eq 1')

    def get_property_definitions(self, name, return_list=None):
        # :param tuple return_list: selected list of properties to be returned.
        # Dynamics fetchXml only allows maximum of 10 link-entities
        prop_service = DynamicProperty(self._backend)
        if return_list:
            properties = prop_service.get_properties_of(name)
            selected = []
            for prop in properties:
                if prop['alias'] in return_list:
                    selected.append(prop)
            return selected
        else:
            return prop_service.get_properties_of(name)

    def list(self):
        # Only list user defined product not imported samples
        filter_option = self._active_product_filter()
        return super().list(extra=filter_option)

    def list_names(self):
        selects = self.create_select(('name', ))
        filter_option = self._active_product_filter()
        return super().list(selects=selects, extra=filter_option)


class Account(Handler):
    END_POINT = 'accounts'
    ENTITY = 'account'
    FIELDS = ('name', 'websiteurl', )
    LOOKUPS = ('parentaccountid($select=name)',
               'primarycontactid($select=fullname,emailaddress1)')
    MAPS = {'parentaccountid': {'name': 'parent_account'},
            'primarycontactid': {'fullname': 'manager', 'emailaddress1': 'email'},
            '_parentaccountid_value': {'raw': 'parentaccountid', 'formatted': 'parent_account'}}

    def get_top(self, unselective=False):
        """Get Accounts which do not have parent

        eRSA's implementation of Dynamics always has top Account as customer in Order.
        So the customers listed in Order is a subset of these Accounts.
        :param bool unselective: all top accounts, default = False
        """
        # <fetch distinct='true' mapping='logical'>
        #     <entity name='salesorder'>
        #         <attribute name='customerid' alias='id' />
        #         <link-entity name="account" link-type="outer" to="customerid" from="accountid">
        #             <attribute name="name" alias="name" />
        #         </link-entity>
        #     </entity>
        # </fetch>
        if unselective:
            return self.get_child_of('null')
        else:
            fetch = FetchXML.create_fetch(distinct=True)
            entity = FetchXML.create_entity(fetch, 'salesorder')
            FetchXML.create_alias(entity, 'customerid', 'id')
            link = FetchXML.create_link(entity, 'account', 'accountid', 'customerid')
            FetchXML.create_alias(link, 'name', 'name')
            logger.debug(FetchXML.to_string(fetch))
            return self._backend.get(self.END_POINT, {'fetchXml': FetchXML.to_string(fetch)})

    def get_child_of(self, parent_id):
        selects = self.create_select(('name', ))
        filter_option = self.create_filter('_parentaccountid_value eq %s' % parent_id)
        return super().list(selects=selects, extra=filter_option)

    def get_ancestors(self, account_id):
        """Get all ancestors of an account"""
        # <fetch distinct='false' mapping='logical'>
        #     <entity name='account'>
        #         <attribute name='name' />
        #         <attribute name='parentaccountid'/>
        #         <filter type='and'>
        #             <condition attribute='accountid' operator='above' value='e929372b-5063-e611-80e3-c4346bc4de3c' />
        #         </filter>
        #     </entity>
        # </fetch>
        fetch = FetchXML.create_fetch()
        entity = FetchXML.create_entity(fetch, self.ENTITY)
        FetchXML.create_sub_elm(entity, 'attribute', {'name': 'name'})
        FetchXML.create_sub_elm(entity, 'attribute', {'name': 'parentaccountid'})
        filter_op = FetchXML.create_sub_elm(entity, 'filter', {'type': 'and'})
        FetchXML.create_sub_elm(filter_op, 'condition', {'attribute': 'accountid', 'operator': 'above', 'value': account_id})
        logger.debug(FetchXML.to_string(fetch))
        ancestors = self._backend.get(self.END_POINT, {'fetchXml': FetchXML.to_string(fetch)})
        for item in self.map_list(ancestors):
            logger.debug(item)

    def get_all_products(self):
        """Get all products belong to this Account"""
        assert self.instance is not None
        if hasattr(self.instance, 'accountid'):
            order_service = Order(self._backend)
            return order_service.get_account_products(self.instance['accountid'])
        else:
            return []

    def get_usernames(self, account_id):
        """Get contacts which have username with essential information

        A shortcut for eRSA Account product.
        """
        contact_service = Contact(self._backend)
        return contact_service.get_usernames_of(account_id)


class Contact(Handler):
    """Dynamics Contact"""
    # https://msdn.microsoft.com/en-us/library/mt593097.aspx
    END_POINT = 'contacts'
    ENTITY = 'contact'
    FIELDS = ('fullname', 'emailaddress1', 'new_username', 'department', 'managername', 'statecode', 'jobtitle', '_parentcustomerid_value')
    # Customer
    # Customer data type is used when a field can hold one account or one contact record.
    # Contact and Lead entities use this data type (ParentCustomerId and CustomerId respectively).
    # http://www.crmanswers.net/2014/08/dynamics-crm-special-data-types.html
    # http://www.inogic.com/blog/2016/06/commencement-of-customer-type-field-in-dynamics-crm-2016-update-1/
    # When one is set, it will be mapped to parentcustomer, and another will be None
    # if item['parentcustomerid_contact'] is None: parentcustomer_type = 'Account'
    # elif item['parentcustomerid_account'] is None: parentcustomer_type = 'Contact'
    LOOKUPS = ('parentcustomerid_account($select=name)', 'parentcustomerid_contact($select=fullname)')
    MAPS = {
        'emailaddress1': 'email',
        'new_username': 'username',
        'statecode': {'formatted': 'status'},
        '_parentcustomerid_value': {'raw': 'parentcustomerid'},
        'parentcustomerid_account': {'name': 'parentcustomer'},
        'parentcustomerid_contact': {'fullname': 'parentcustomer'}
    }

    # def _select_expands(self, lookups=None):
    #     """Override super class' method"""

    #     # The reason is parentcustomerid and so far there is only one such thing known to me
    #     plookups = re.compile(r'^(\S+)\(\$.+\=.+\)$')
    #     if lookups is None:
    #         lookups = getattr(self, 'LOOKUPS', ())

    #     SKIPS = ('parentcustomerid_account', 'parentcustomerid_contact')
    #     exp_selects = []
    #     for exp in lookups:
    #         exp_match = plookups.match(exp)
    #         if exp_match:
    #             if not exp_match.group(1) in SKIPS:
    #                 exp_selects.append('_' + exp_match.group(1) + '_value')
    #     return exp_selects

    def get_contacts_of(self, account_id):
        filter_option = self.create_filter('_accountid_value eq %s' % account_id)
        return self.list(extra=filter_option)

    def map(self, item):
        """Override super method to identify what type of customer is"""
        flatted = super().map(item)
        if flatted['parentcustomerid_contact'] is None:
            flatted['parentcustomer_type'] = 'Account'
        elif item['parentcustomerid_account'] is None:
            flatted['parentcustomer_type'] = 'Contact'
        return flatted

    def get_usernames(self):
        """Get contacts which have username with essential information

        A shortcut for eRSA Account product.
        """
        # <fetch distinct="false" mapping="logical">
        #     <entity name="contact">
        #         <attribute name="new_username" alias='username'/>
        #         <attribute name="fullname" alias='manager'/>
        #         <attribute name="emailaddress1" alias='email'/>
        #         <filter type="and">
        #             <condition attribute="new_username" operator="not-null" />
        #             <condition attribute="new_username" operator="ne" value="NULL" />
        #         </filter>
        #         <link-entity from="accountid" link-type="outer" name="account" to="parentcustomerid">
        #             <attribute alias="unit" name="name" />
        #             <link-entity from="accountid" link-type="outer" name="account" to="parentaccountid">
        #                 <attribute alias="biller" name="name" />
        #             </link-entity>
        #         </link-entity>
        #     </entity>
        # </fetch>
        fetch = FetchXML.create_fetch(False)
        entity = FetchXML.create_entity(fetch, self.ENTITY)
        FetchXML.create_alias(entity, 'new_username', 'username')
        FetchXML.create_alias(entity, 'fullname', 'manager')
        FetchXML.create_alias(entity, 'emailaddress1', 'email')

        filter_op = FetchXML.create_sub_elm(entity, 'filter', {'type': 'and'})
        FetchXML.create_condition(filter_op, 'new_username', 'not-null')
        FetchXML.create_condition(filter_op, 'new_username', 'ne', 'NULL')

        unit_link = FetchXML.create_link(entity, 'account', 'accountid', 'parentcustomerid')
        FetchXML.create_alias(unit_link, 'name', 'unit')
        account_link = FetchXML.create_link(unit_link, 'account', 'accountid', 'parentaccountid')
        FetchXML.create_alias(account_link, 'name', 'biller')
        logger.debug(FetchXML.to_string(fetch))
        return self._backend.get(self.END_POINT, {'fetchXml': FetchXML.to_string(fetch)})

    def get_usernames_of(self, account_id):
        """Get contacts which have username with essential information

        A shortcut for eRSA Account product.
        """
        # <fetch distinct="false" mapping="logical">
        #     <entity name="contact">
        #         <attribute name="new_username" alias='username'/>
        #         <attribute name="fullname" alias='manager'/>
        #         <attribute name="emailaddress1" alias='email'/>
        #         <filter type="and">
        #             <condition attribute="new_username" operator="not-null" />
        #             <condition attribute="new_username" operator="ne" value="NULL" />
        #         </filter>
        #         <link-entity from="accountid" name="account" to="parentcustomerid">
        #             <attribute alias="unit" name="name" />
        #             <filter type="and">
        #                 <filter type="or">
        #                     <condition attribute="accountid" operator="eq" value="account_id" />
        #                     <condition attribute="parentaccountid" operator="eq" value="account_id" />
        #                 </filter>
        #             </filter>
        #         </link-entity>
        #     </entity>
        # </fetch>
        fetch = FetchXML.create_fetch(False)
        entity = FetchXML.create_entity(fetch, self.ENTITY)
        FetchXML.create_alias(entity, 'new_username', 'username')
        FetchXML.create_alias(entity, 'fullname', 'manager')
        FetchXML.create_alias(entity, 'emailaddress1', 'email')

        filter_op = FetchXML.create_sub_elm(entity, 'filter', {'type': 'and'})
        FetchXML.create_condition(filter_op, 'new_username', 'not-null')
        FetchXML.create_condition(filter_op, 'new_username', 'ne', 'NULL')

        link = FetchXML.create_link(entity, 'account', 'accountid', 'parentcustomerid')
        FetchXML.create_alias(link, 'name', 'unit')
        ac_filter = FetchXML.create_sub_elm(FetchXML.create_sub_elm(link, 'filter', {'type': 'and'}), 'filter', {'type': 'or'})
        FetchXML.create_condition(ac_filter, 'accountid', 'eq', account_id)
        FetchXML.create_condition(ac_filter, 'parentaccountid', 'eq', account_id)
        return self._backend.get(self.END_POINT, {'fetchXml': FetchXML.to_string(fetch)})


class Opportunity(Handler):
    """Rich description of a sale or project"""

    END_POINT = 'opportunities'
    FIELDS = ('name', 'description', 'currentsituation', 'customerneed')
    LOOKUPS = ('parentcontactid($select=fullname)', 'parentaccountid($select=name)')


# this for seeding up interpretation optionset from product properties
Optionsetitems = None


class Order(Handler):
    """Sales order

    customer is one of top Account, second level Account is represented by
    the unit (Account) of Project Leader
    """

    END_POINT = 'salesorders'
    ENTITY = 'salesorder'
    FIELDS = ('name', 'description', 'new_orderid', '_customerid_value')
    LOOKUPS = ('opportunityid($select=name)', )
    MAPS = {'_customerid_value': {'raw': 'customerid', 'formatted': 'customer'}}
    STATES = {'Active': '0',
              'Submitted': '1',
              'Canceled': '2',
              'Fulfilled': '3',
              'Invoiced': '4'}

    STATUS = {'New': '1',
              'Pending': '2',
              'In Progress': '3',
              'No Money': '4',
              'Complete': '100001',
              'Partial': '100002',
              'Invoiced': '100003'}

    OPTIONSET_PATTERN = re.compile("^(.+)optionsetpropertyid$")

    @classmethod
    def _create_order_entity(cls, id_only=False, extra=None):
        """Create FetchXml Order(salesorder) entity

        :param id_only bool: switch to control if only return salesorderid, default False
        :param extra list of dict: extra attributes to be returned. Each dict at least has name, can have optional alias
        :return tuple: fetchXml and entity elements
        """
        # <fetch mapping="logical">
        #     <entity name="salesorder">
        #         <attribute name="name" />
        #         <attribute name="new_orderid" alias="orderID" />
        #     </entity>
        # </fetch>

        fetch = FetchXML.create_fetch()
        entity = FetchXML.create_entity(fetch, cls.ENTITY)
        if id_only:
            FetchXML.create_sub_elm(entity, 'attribute', {'name': 'salesorderid'})
        else:
            FetchXML.create_sub_elm(entity, 'attribute', {'name': 'name'})
            FetchXML.create_alias(entity, 'new_orderid', 'orderID')
            if extra:
                for attr in extra:
                    if 'alias' in attr:
                        FetchXML.create_alias(entity, attr['name'], attr['name'])
                    else:
                        FetchXML.create_sub_elm(entity, 'attribute', {'name': attr['name']})
        return fetch, entity

    @classmethod
    def _add_state_condition(cls, filter_elm, state='Fulfilled'):
        """Create a condition to filter orders by state"""
        # Mainly used to filter fulfilled Orders
        state_code = cls.STATES[state]
        FetchXML.create_sub_elm(filter_elm, 'condition', {'attribute': 'statecode', 'operator': 'eq', 'value': state_code})

    @classmethod
    def _add_status_condition(cls, filter_elm, status='Complete'):
        """Create a condition to filter orders by status"""
        # Mainly used to filter partially fulfilled Orders
        status_code = cls.STATUS[status]
        FetchXML.create_sub_elm(filter_elm, 'condition', {'attribute': 'statuscode', 'operator': 'eq', 'value': status_code})

    @staticmethod
    def _add_detail_link(entity):
        """Add a link-entity of Order Line (salesorderdetail) to Order entity element in fetchXml

        It retrieves quantity as allocated, priceperunit as unitPrice.
        """
        detail_link_elm = FetchXML.create_link(entity, 'salesorderdetail', 'salesorderid', 'salesorderid')
        FetchXML.create_alias(detail_link_elm, 'quantity', 'allocated')
        FetchXML.create_alias(detail_link_elm, 'priceperunit', 'unitPrice')
        return detail_link_elm

    @staticmethod
    def _add_product_filter(detail_link_elm, product_id):
        prod_filter = FetchXML.create_sub_elm(detail_link_elm, 'filter', {'type': 'and'})
        FetchXML.create_sub_elm(prod_filter, 'condition', {'attribute': 'productid', 'operator': 'eq', 'value': product_id})

    @staticmethod
    def _add_connection_role_link(order_node, role_id, display_name, extra_fields=None):
        """Create node to get detail of a connection role

        It retrieves fullname as display_name (provided by caller);
                     emailaddress1 as email
                     parentcustomerid.name as unit
        If extra_field is given, either a list or tuple of tuples,
        each of element of it has to have only two elements for mapping internal name to label:
        [0]: internal name and [1] label, e.g. new_username --> display_name + 'username'.
        Note: extra_field is intend to be used as a low level argument: caller has to know
        the internal name required.
        """
        link_elm = FetchXML.create_link(order_node, 'connection', 'record1id', 'salesorderid', 'outer')
        FetchXML.create_alias(link_elm, 'record2id', display_name + 'contactid')

        filter_op = FetchXML.create_sub_elm(link_elm, 'filter', {'type': 'and'})
        # hard coded for 1088: Order, 2: Contact
        FetchXML.create_condition(filter_op, 'record1objecttypecode', 'eq', '1088')
        FetchXML.create_condition(filter_op, 'record2objecttypecode', 'eq', '2')
        FetchXML.create_condition(filter_op, 'record2roleid', 'eq', role_id)

        contact_link_elm = FetchXML.create_link(link_elm, 'contact', 'contactid', 'record2id', 'outer')
        FetchXML.create_alias(contact_link_elm, 'jobtitle', display_name + 'title')
        FetchXML.create_alias(contact_link_elm, 'fullname', display_name)
        FetchXML.create_alias(contact_link_elm, 'emailaddress1', display_name + 'email')
        if extra_fields and type(extra_fields) in (list, tuple):
            for extra in extra_fields:
                assert len(extra) == 2
                FetchXML.create_alias(contact_link_elm, extra[0], display_name + extra[1])

        account_link_elm = FetchXML.create_link(contact_link_elm, 'account', 'accountid', 'parentcustomerid', 'outer')
        FetchXML.create_alias(account_link_elm, 'name', display_name + 'unit')

    @staticmethod
    def _add_role_link(entity, roles):
        for role in roles:
            assert 'id' in role and 'name' in role
            if 'extra' in role:
                Order._add_connection_role_link(entity, role['id'], role['name'], role['extra'])
            else:
                Order._add_connection_role_link(entity, role['id'], role['name'])

    @staticmethod
    def _add_prod_prop_link(entity, props):
        for prop in props:
            required = prop['required'] if 'required' in prop else True
            Order._add_product_property(entity, prop['id'], prop['type'], prop['alias'], required)

    @staticmethod
    def _add_product_property(detail_elm, property_id, property_type, alias, required=True):
        """Create a link-entity for retriving property instances of a product in salesorderdetails

        :param str property_id: UUID of a DynamicProperty
        :param str property_type: type to be returned: one of valueXXXX
        :param str alias: name of a DynamicProperty, used to set the alias attribute
        :param bool required: control either to be an inner or outer join. Default = True. may be redundant
        """
        prod_link_elm = FetchXML.create_link(detail_elm, 'dynamicpropertyinstance', 'regardingobjectid', 'salesorderdetailid')
        if not required:
            prod_link_elm.set('link-type', 'outer')
        if property_type == 'optionset':
            # To interpret this value it needs to get dynamicpropertyname whose dynamicpropertyvalue is this valueinteger
            FetchXML.create_alias(prod_link_elm, 'valueinteger', alias)
            FetchXML.create_alias(prod_link_elm, 'dynamicpropertyid', alias + 'optionsetpropertyid')
        else:
            FetchXML.create_alias(prod_link_elm, property_type, alias)
        filter_op = FetchXML.create_sub_elm(prod_link_elm, 'filter', {'type': 'and'})
        FetchXML.create_sub_elm(filter_op, 'condition', {'attribute': 'dynamicpropertyid', 'operator': 'eq', 'value': property_id})

    @staticmethod
    def _add_for_link(entity):
        """Add link-entity to Order entity element in fetchXml to get ANZSRC FOR codes"""
        intersect_link_elm = FetchXML.create_link(entity, 'new_new_c_for_new_salesorder', 'salesorderid', 'salesorderid', extra={'visible': 'false', 'intersect': 'true'})
        for_link_elm = FetchXML.create_link(intersect_link_elm, 'new_c_for_new', 'new_c_for_newid', 'new_c_for_newid')
        FetchXML.create_alias(for_link_elm, 'new_name', 'code')
        FetchXML.create_alias(for_link_elm, 'new_code_name', 'label')
        return intersect_link_elm

    def get_product(self, product_id, roles=None, prod_props=None, account_id=None, order_extra=None):
        """Get a list of a product in Fulfilled Orders

        Customer has to be an Account in Orders. Orders are in Fulfilled state.

        :param list of dict roles: Connection Roles of Order to be retrieved, default None
        :param list prod_props: list of dicts for retrieving product properties, default None.
                                It has keys: id, type, e.g. valueinteger, alias, required, true/false
        :param str account_id: Account id of customer, default None
        :param list of dict order_extra:
        :returns list: each element is a dict with fields at least:
                       salesorderid
                       name: order name
                       orderID: order ID
                       allocated: quantity
                       unitPrice: price per unit
                       biller: Account responses to cost
                       roles: Contacts of connected to order. Default None. Each role has fullname, email, unit and role's display name
        """
        fetch, entity = self._create_order_entity(extra=order_extra)
        filter_op = FetchXML.create_sub_elm(entity, 'filter', {'type': 'and'})
        # only return fulfilled orders, this is commonly used
        # TODO: partially fulfilled to be included?
        # FIXME: temporarily removed fulfilled condition check. Need to turn it back on once done tests.
        # self._add_state_condition(filter_op)

        if account_id:
            FetchXML.create_sub_elm(filter_op, 'condition', {'attribute': 'accountid', 'operator': 'eq', 'value': account_id})
        else:
            account_link_elm = FetchXML.create_link(entity, 'account', 'accountid', 'accountid')
            FetchXML.create_alias(account_link_elm, 'name', 'biller')

        detail_link_elm = self._add_detail_link(entity)
        Order._add_product_filter(detail_link_elm, product_id)

        if prod_props:
            self._add_prod_prop_link(detail_link_elm, prod_props)

        if roles:
            self._add_role_link(entity, roles)

        logger.debug(FetchXML.to_string(fetch))
        results = self._backend.get(self.END_POINT, {'fetchXml': FetchXML.to_string(fetch)})

        global Optionsetitems
        if not Optionsetitems:
            Optionsetitems = DynamicPropertyOptionsetItem(self._backend)
            Optionsetitems.construct_indexer()

        for result in results:
            properties = result.keys()
            for prop in properties:
                checker = self.OPTIONSET_PATTERN.match(prop)
                if checker:
                    prop_name = checker.group(1)
                    if prop_name in result:
                        result[prop_name] = Optionsetitems.get_option_value(result[prop], result[prop_name])
        return results

    def get_account_products(self, account_id, role=None):
        """Get a list of Products sold to an Account

        This Account maps to customer in Order. Orders are in Fulfilled state.

        :param dict role: a Connection Role of Order to be retrieved, default None.
                          If role is set, the ruturn has a key of role['name'] with fullname as value, email and unit
        :returns list: each element is a dict with fields at least:
                       salesorderid
                       name: order name
                       orderID: order ID
                       allocated: quantity
                       unitPrice: price per unit
                       product: name of product
                       role: key-value pairs of role['name'] with fullname as value, email and unit
        """
        # Stop at salesorderdetail line: no dynamic properties because it returns mixed products
        fetch, entity = self._create_order_entity()
        filter_op = FetchXML.create_sub_elm(entity, 'filter', {'type': 'and'})
        # only return fulfilled orders, this is commonly used
        self._add_state_condition(filter_op)
        FetchXML.create_sub_elm(filter_op, 'condition', {'attribute': 'accountid', 'operator': 'eq', 'value': account_id})

        detail_link_elm = self._add_detail_link(entity)
        prod_link_elm = FetchXML.create_link(detail_link_elm, 'product', 'productid', 'productid')
        FetchXML.create_alias(prod_link_elm, 'name', 'product')

        if role:
            assert 'id' in role and 'name' in role
            self._add_connection_role_link(entity, role['id'], role['name'])

        logger.debug(FetchXML.to_string(fetch))
        return self._backend.get(self.END_POINT, {'fetchXml': FetchXML.to_string(fetch)})

    def get_for_codes(self, product_id=None, account_id=None, order_id=None):
        """Get ANZSRC FOR codes and labels of an order or orders

        :param str product_id: filter order by product id. Default = None
        :param str account_id: filter order by customer id. Default = None
        :param str order_id: filter order by its id. Default = None
        :return dict: keys are order ids (salesorderid), values are list of strings of 'code: label'
        """
        # <fetch mapping="logical">
        #     <entity name="salesorder">
        #         <attribute name="salesorderid" />
        #         <filter type="and">
        #             <condition attribute="customerid" operator="eq" value="4a5d5a78-c962-e611-80e3-c4346bc516e8" />
        #             <condition attribute="salesorderid" operator="eq" value="7e15d73f-acfc-e611-8114-70106fa3d971" />
        #         </filter>
        #         <link-entity name="salesorderdetail" to="salesorderid" from="salesorderid">
        #             <filter type="and">
        #                 <condition attribute="productid" operator="eq" value="4923623f-47fd-e611-810b-e0071b6685b1" />
        #             </filter>
        #         </link-entity>
        #         <link-entity name="new_new_c_for_new_salesorder" from="salesorderid" to="salesorderid" visible="false" intersect="true">
        #             <link-entity name="new_c_for_new" from="new_c_for_newid" to="new_c_for_newid">
        #                 <attribute name="new_name" alias="code" />
        #                 <attribute name="new_code_name" alias="label" />
        #             </link-entity>
        #         </link-entity>
        #     </entity>
        # </fetch>
        fetch, entity = self._create_order_entity(id_only=True)

        Order._add_for_link(entity)

        if order_id:
            filter_op = FetchXML.create_sub_elm(entity, 'filter', {'type': 'and'})
            FetchXML.create_condition(filter_op, 'salesorderid', 'eq', order_id)
        elif account_id:
            filter_op = FetchXML.create_sub_elm(entity, 'filter', {'type': 'and'})
            FetchXML.create_condition(filter_op, 'customerid', 'eq', account_id)

        if product_id:
            detail_link_elm = FetchXML.create_link(entity, 'salesorderdetail', 'salesorderid', 'salesorderid')
            Order._add_product_filter(detail_link_elm, product_id)

        logger.debug(FetchXML.to_string(fetch))
        code_list = self._backend.get(self.END_POINT, {'fetchXml': FetchXML.to_string(fetch)})
        codes = {}
        for code in code_list:
            if code['salesorderid'] not in codes:
                codes[code['salesorderid']] = []
            codes[code['salesorderid']].append(code['code'] + ': ' + code['label'])
        return codes


class OrderDetail(Handler):
    """A product line in a sales order"""

    END_POINT = 'salesorderdetails'
    FIELDS = ('quantity', 'manualdiscountamount', 'volumediscountamount', 'priceperunit')
    LOOKUPS = ('salesorderid($select=name)', 'productid($select=name)', 'uomid($select=name)')

    # VALUE_TYPES = {
    #     1: 'valuedecimal',
    #     2: 'valuedouble',
    #     3: 'valuestring',
    #     4: 'valueinteger'
    # }

    def get_products_of(self, order_id):
        """Get order details, aka product items of an order

        Retrun includes salesorderdetailids which are used for check/get product properties
        """
        filter_option = self.create_filter("_salesorderid_value eq %s" % order_id)
        return self.list(extra=filter_option)

    def get_property_definitions(self, orderdetail_id):
        definitions = self._backend.get('%s(%s)/Microsoft.Dynamics.CRM.RetrieveProductProperties()' % (self.END_POINT, orderdetail_id))
        # need to return a dict with dynamicpropertyid as key, at least datatype as value
        def_dict = {}
        for definition in definitions:
            def_dict[definition['dynamicpropertyid']] = {
                'name': definition['name'],
                'type': DynamicProperty.VALUE_TYPES[definition['datatype']]}
        return def_dict

    def get_property_values(self, orderdetail_id):
        # filter PropertyInstace through _regardingobjectid_value
        filter_option = self.create_filter("_regardingobjectid_value eq %s" % orderdetail_id)
        property_instance_service = PropertyInstance(self._backend)
        properties = property_instance_service.list(extra=filter_option)
        logger.debug(properties)

        definitions = self.get_property_definitions(orderdetail_id)
        logger.debug(definitions)

        optionsetitems_service = DynamicPropertyOptionsetItem(self._backend)
        value_dict = {}
        for prop in properties:
            prop_id = prop['_dynamicpropertyid_value']
            prop_name = definitions[prop_id]['name']
            prop_type = definitions[prop_id]['type']
            if prop_type == 'optionset':
                value_dict[prop_name] = optionsetitems_service.get_option_value(prop_id, prop['valueinteger'])
            else:
                value_dict[prop_name] = prop[prop_type]
        logger.debug(value_dict)
        return value_dict


class PropertyInstance(Handler):
    """Product property instance"""
    # There are four value holders for four basic types: integer, double, decimal, string.
    # Depends on property's type, pick up correct value.
    # For optionset, it needs valueinteger from propertyinstance to represents dynamicpropertyoptionvalue
    # in propertyoptionsetitems to get dynamicpropertyoptionname which is a human understandable string.
    # That is to say if there are properties is optionset list() is not enough as it misses the second step.
    # See OrderDetail.get_property_values
    END_POINT = 'dynamicpropertyinstances'
    FIELDS = ('valueinteger', 'valuedouble', 'valuedecimal', 'valuestring', '_regardingobjectid_value', '_dynamicpropertyid_value')
    # LOOKUPS = ('dynamicpropertyid($select=name)', )
    MAPS = {
        '_dynamicpropertyid_value@OData.Community.Display.V1.FormattedValue': 'property'
    }

    # def get_value(self, property_id, property_type):
    #     filter_option = self.create_filter("_salesorderid_value eq %s" % order_id)
    #     return self.list(extra=filter_option)

    #     property_service = DynamicProperty(self._backend)
    #     return property_service.get(property_id)


class DynamicProperty(Handler):
    """Product property definition"""

    # DynamicPropertyAssociation is more useful
    # seems does not need this:  Microsoft.Dynamics.CRM.RetrieveProductProperties() on orderdetail is a filtered version of this generic version
    END_POINT = 'dynamicproperties'
    FIELDS = ('name', 'description', 'datatype')
    VALUE_TYPES = {
        0: 'optionset',
        1: 'valuedecimal',
        2: 'valuedouble',
        3: 'valuestring',
        4: 'valueinteger'
    }

    @staticmethod
    def _normalise(prop):
        """Convert type (ntype) from number to type used in DynamicPropertyInstance
           and remove space and / in property name (alias) bacause alias can only
           have [A-Z], [a-z] or [0-9] or _
        """
        assert 'ntype' in prop
        prop['type'] = DynamicProperty.VALUE_TYPES[prop['ntype']]
        assert 'alias' in prop
        prop['alias'] = prop['alias'].replace(' ', '').replace('/','')

    def get_properties_of(self, name):
        """Get product properties of a product

        :param str name: name of product
        """
        # <fetch mapping='logical'>
        #     <entity name='dynamicpropertyassociation'>
        #         <attribute name='dynamicpropertyid' alias='id' />
        #         <filter type='and'>
        #             <condition attribute='associationstatus' operator='eq' value='0' />
        #         </filter>
        #         <link-entity name='dynamicproperty' from='dynamicpropertyid' to='dynamicpropertyid'>
        #             <attribute name='name' alias='alias' />
        #             <attribute name='datatype' alias='ntype' />
        #         </link-entity>
        #         <link-entity name='product' from='productid' to='regardingobjectid'>
        #             <filter type='and'>
        #                 <condition attribute='name' operator='eq' value='RDS Allocation' />
        #             </filter>
        #         </link-entity>
        #     </entity>
        # </fetch>
        fetch = FetchXML.create_fetch()
        entity = FetchXML.create_entity(fetch, 'dynamicpropertyassociation')
        FetchXML.create_alias(entity, 'dynamicpropertyid', 'id')
        status_filter = FetchXML.create_sub_elm(entity, 'filter', {'type': 'and'})
        FetchXML.create_sub_elm(status_filter, 'condition', {'attribute': 'associationstatus', 'operator': 'eq', 'value': '0'})

        prop_link = FetchXML.create_link(entity, 'dynamicproperty', 'dynamicpropertyid', 'dynamicpropertyid')
        FetchXML.create_alias(prop_link, 'name', 'alias')
        FetchXML.create_alias(prop_link, 'datatype', 'ntype')

        prod_link = FetchXML.create_link(entity, 'product', 'productid', 'regardingobjectid')
        prod_filter = FetchXML.create_sub_elm(prod_link, 'filter', {'type': 'and'})
        FetchXML.create_condition(prod_filter, 'name', 'eq', name)

        logger.debug(FetchXML.to_string(fetch))
        properties = self._backend.get('dynamicpropertyassociations', {'fetchXml': FetchXML.to_string(fetch)})
        for prop in properties:
            self._normalise(prop)
        return properties


class DynamicPropertyOptionsetItem(Handler):
    """Product Optionset property definitions: Use as a dictionary"""

    END_POINT = 'dynamicpropertyoptionsetitems'
    FIELDS = ('dynamicpropertyoptionname', 'dynamicpropertyoptionvalue', 'dynamicpropertyoptiondescription', '_dynamicpropertyid_value')

    def construct_indexer(self):
        def _make_dict(defintions):
            indexer = {}
            for defintion in defintions:
                prop_id = defintion['_dynamicpropertyid_value']
                if not prop_id in indexer:
                    indexer[prop_id] = {}
                indexer[prop_id][defintion['dynamicpropertyoptionvalue']] = defintion['dynamicpropertyoptionname']
            return indexer

        self._local_indexer = _make_dict(self.list())

    def get_option_value(self, property_id, option_value=None):
        # if option value (has to be valueinteger) is null, do not call this
        # dynamicpropertyoptionsetitems?$select=dynamicpropertyoptionname&$filter=_dynamicpropertyid_value eq 449f2880-9eb3-e711-8156-e0071b684991 and dynamicpropertyoptionvalue eq 1
        try:
            option_value = int(option_value)
        except (ValueError, TypeError):
            return ""

        if hasattr(self, '_local_indexer'):
            # if caller called DynamicPropertyOptionsetItem.construct_indexer()
            return self._local_indexer[property_id][option_value]
        else:
            selects = self.create_select(('dynamicpropertyoptionname',))
            optionitem_filter =  self.create_filter('_dynamicpropertyid_value eq %s and dynamicpropertyoptionvalue eq %s' % (property_id, option_value))
            result_list = self.list(selects=selects, extra=optionitem_filter)
            assert(len(result_list) == 1)
            return result_list[0]['dynamicpropertyoptionname']


class Optionset(Handler):
    """Global Optionset

    Only List method of base class works fine.
    """

    END_POINT = 'GlobalOptionSetDefinitions'
    FIELDS = ('Name', 'OptionSetType')

    @staticmethod
    def _get_localized_label(label):
        """Get a field's relevent label"""
        # label (a complex type) should have two keys: LocalizedLabels and UserLocalizedLabel
        assert len(label) == 2
        if label['UserLocalizedLabel'] is None:
            return ''
        if 'Label' in label['UserLocalizedLabel']:
            return label['UserLocalizedLabel']['Label']
        else:
            raise KeyError("No Label key found in UserLocalizedLabel object.")

    @staticmethod
    def _map(optionset):
        simple_attrs = ('MetadataId', 'Name', 'OptionSetType')
        root_attrs = ('Description', 'DisplayName')
        option_attrs = ('Description', 'Label')
        simplified = {'Options': []}

        for attr in simple_attrs:
            simplified[attr] = optionset[attr]

        for attr in root_attrs:
            simplified[attr] = Optionset._get_localized_label(optionset[attr])

        for option in optionset['Options']:
            op = {'Value': option['Value']}
            for attr in option_attrs:
                op[attr] = Optionset._get_localized_label(option[attr])
            simplified['Options'].append(op)

        return simplified

    def get_by_id(self, optionset_id):
        """Get an optionset by its metadataId"""
        # /GlobalOptionSetDefinitions(optionset_id)
        return Optionset._map(self._backend.get("%s(%s)" % (self.END_POINT, optionset_id)))

    def get_by_name(self, optionset_name):
        """Get an optionset by its Name"""
        # /GlobalOptionSetDefinitions(Name='connectionrole_category')
        try:
            return Optionset._map(self._backend.get("%s(Name='%s')" % (self.END_POINT, optionset_name)))
        except Exception:
            raise KeyError('Failed to get optionset %s' % optionset_name)

    @staticmethod
    def get_option_dict(options):
        """Return a dict with Labels as keys of Labels in options"""
        label_dict = {}
        for op in options:
            label_dict[op['Label']] = op['Value']
        return label_dict

    def get_option_from(self, optionset_name, label):
        """A shortcut for getting one value from its label in an optionset

        Raise KeyError if optionset or label does not exist.
        """
        opset = self.get_by_name(optionset_name)
        if opset is None:
            raise KeyError('%s does not exists' % optionset_name)

        options = self.get_option_dict(opset['Options'])
        if label in options:
            return options[label]
        else:
            raise KeyError('%s does not exists' % label)


class Connection(Handler):
    """Connection between two entities"""

    END_POINT = 'connections'
    FIELDS = ('name', 'description', 'record1objecttypecode', 'record2objecttypecode', 'statecode')
    # this has to be flexible: each recordid can point to any entity: record?id_salesorder, record?id_contact
    # some of connections have role, some do not not
    LOOKUPS = ('record2id_salesorder($select=name)', 'record1roleid($select=name)', 'record2roleid($select=name)', )


class ConnectionRole(Handler):
    """Definitions of Connection Roles"""

    END_POINT = 'connectionroles'
    FIELDS = ('name', 'description', 'category')

    def get_roleid_of(self, name, category):
        """Get role id by its name and category value (not name)"""
        data = self._backend.get(self.END_POINT, {'$select': 'connectionroleid', '$filter': "name eq '%s' and category eq %s" % (name, category)})
        assert len(data) == 1
        return data[0]['connectionroleid']
