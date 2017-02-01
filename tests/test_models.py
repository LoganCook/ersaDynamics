import re
import logging
import unittest
from unittest.mock import patch

from .context import edynam
from edynam.connection import ADALConnection
from edynam.dynamics import Dynamics
from edynam.models import (Handler, Project, Product, Order)


logging.basicConfig(level=logging.DEBUG,
                    format='%(levelname)s %(asctime)s %(filename)s %(module)s.%(funcName)s +%(lineno)d: %(message)s')

logging.getLogger("requests").setLevel(logging.WARNING)


class TestModelHandler(unittest.TestCase):
    def setUp(self):
        with patch.object(ADALConnection, '_validate_parameters', return_value=None) as mocked_validator:
            conn = ADALConnection({})
            conn.parameters['resource'] = 'mocked'
        self.assertTrue(mocked_validator.called)
        self.dynamics = Dynamics(conn)

    def test_defaults(self):
        handler = Handler(self.dynamics)
        self.assertIsNone(handler.select())
        self.assertIsNone(handler.expand())

    def test_projct_query_fields(self):
        handler = Project(self.dynamics)
        self.assertIsNotNone(handler.select())
        self.assertIsNotNone(handler.expand())

    def test_skip_select_customid(self):
        """Patterns to be skipped in $select after expanding customer fields"""
        customer_id_pat = re.compile('.*customerid_(account|contact)$')
        to_be_matched = (
            'customerid_account',
            'customerid_contact',
            'parentcustomerid_account',
            'parentcustomerid_contact')
        for tbm in to_be_matched:
            self.assertIsNotNone(customer_id_pat.match(tbm))

    def test_build_query_fields(self):
        handler = Product(self.dynamics)
        select = handler.select()['$select']
        expand = handler.expand()['$expand']

        items = re.findall(r'(\$select\=)', expand)
        self.assertEqual(len(items), len(handler.LOOKUPS))
        self.assertEqual(len(select.split(',')), len(items) + len(handler.FIELDS))

    def test_mapping(self):
        handler = Handler(self.dynamics)
        handler.MAPS = {
            'new_rds_fs_name': 'tech_id',
            '_new_requested_by_value': {'formatted': 'manager', 'raw': 'contactid'},
            '_new_new_project_name_value': {'raw': 'msdyn_projectid', 'formatted': 'project_number'},
            '_new_carried_out_at_value': {'raw': 'accountid', 'formatted': 'billing_org'},
            '_new_service_name_value': {'raw': 'productid', 'formatted': 'product'},
            'new_service_allocation': {'formatted': 'allocation'},
            'new_unit': {'formatted': 'unit'},
            'new_requested_by': {'emailaddress1': 'email'}
        }
        item = {
            "@odata.etag": "W/\"2013243\"",
            "new_customer_utilized_servicesid": "e523e9a0-6b96-e611-80e9-c4346bc516e8",
            "new_rds_fs_name": "f026e3808f914a458fbbf1143a1a28d1",
            "createdon": "2016-10-20T02:19:54Z",
            "createdon@OData.Community.Display.V1.FormattedValue": "20/10/2016 11:49 AM",
            "statuscode": 1,
            "statuscode@OData.Community.Display.V1.FormattedValue": "Active",
            "_new_new_project_name_value": "ac120dfb-1a91-e611-80e5-c4346bc56078",
            "_new_new_project_name_value@OData.Community.Display.V1.FormattedValue": "UOFA0170",
            "new_service_allocation": 2,
            "new_service_allocation@OData.Community.Display.V1.FormattedValue": "2.00",
            "_new_service_name_value": "c3724cbc-b183-e611-80e7-c4346bc4beac",
            "_new_service_name_value@OData.Community.Display.V1.FormattedValue": "NECTAR VM",
            "_new_carried_out_at_value": "84cc87f3-ad62-e611-80e3-c4346bc516e8",
            "_new_carried_out_at_value@OData.Community.Display.V1.FormattedValue": "University of Adelaide",
            "new_unit": 100000004,
            "new_unit@OData.Community.Display.V1.FormattedValue": "CORE",
            "_new_requested_by_value": "cb3eba7d-d965-e611-80e3-c4346bc516e8",
            "_new_requested_by_value@OData.Community.Display.V1.FormattedValue": "John Toubia",
            "new_requested_by": {
                "emailaddress1": "john.toubia@health.sa.gov.au"
            },
        }
        mapped = handler.map(item)
        # two no mapping, 1 simple mapping, 2 non-mapping formatted pairs (4),
        # 4 formatted pairs (8), two one formatted only formatted pairs,
        # 1 expanded mapping of one key. In total: 18
        self.assertEqual(len(mapped), 18)

    def test_contact_mapping(self):
        # Contact has customer field and only one of them will have value and be kept
        handler = Handler(self.dynamics)
        handler.MAPS = {
            'parentcustomerid_account': {'name': 'parentcustomer'},
            'parentcustomerid_contact': {'fullname': 'parentcustomer'}
        }
        item = {
            '_parentcustomerid_value': '9ecc87f3-ad62-e611-80e3-c4346bc516e8',
            'managername': 'Noune Melkoumian',
            'department': None,
            'contactid': '0a870511-b362-e611-80e3-c4346bc43f98',
            '@odata.etag': 'W/"1915264"',
            'fullname': 'Adam Schwartzkopff',
            'jobtitle': None,
            'statuscode@OData.Community.Display.V1.FormattedValue': 'Active',
            'emailaddress1': 'adam.schwartzkopff@adelaide.edu.au',
            'new_username': 'aschwartzkopff',
            'statuscode': 1,
            '_parentcustomerid_value@OData.Community.Display.V1.FormattedValue': 'UOFA, School of Civil, Environmental & Mining Engineering',
            'parentcustomerid_account': {'name': 'UOFA, School of Civil, Environmental & Mining Engineering'},
            'parentcustomerid_contact': None
        }

        mapped = handler.map(item)
        self.assertTrue('parentcustomer' in mapped)
        self.assertEqual(mapped['parentcustomer'], 'UOFA, School of Civil, Environmental & Mining Engineering')

    def test_create_order_entity(self):
        order_handler = Order(self.dynamics)
        fetchXml, entity = order_handler._create_order_entity()
        self.assertEqual(fetchXml.get('mapping'), 'logical')
        self.assertIsNotNone(fetchXml.find('entity'))
        self.assertEqual(len(entity.findall('attribute')), 2)
