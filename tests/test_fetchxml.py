import unittest
import xml.etree.ElementTree as ET

from .context import edynam
from edynam.fetchxml import FetchXML


class TestFetchXML(unittest.TestCase):
    def _comp_elms(self, elm1, elm2):
        self.assertEqual(elm1.tag, elm2.tag)
        for k, v in elm1.items():
            self.assertEqual(elm2.get(k), v)

    def test_create_default_fetch(self):
        fetch = FetchXML.create_fetch()
        parsed = ET.fromstring('<fetch distinct="false" mapping="logical" />')
        self._comp_elms(fetch, parsed)

    def test_create_distinct_fetch(self):
        fetch = FetchXML.create_fetch(True)
        parsed = ET.fromstring('<fetch distinct="true" mapping="logical" />')
        self._comp_elms(fetch, parsed)

    def test_create_entity(self):
        entity = FetchXML.create_entity(FetchXML.create_fetch(), 'test_entity')
        self.assertEqual(entity.get('name'), 'test_entity')

    def test_create_link(self):
        expand = FetchXML.create_link(FetchXML.create_fetch(), 'link', 'from', 'to')
        self.assertEqual(expand.get('from'), 'from')
        self.assertEqual(expand.get('to'), 'to')
        self.assertFalse(hasattr(expand, 'link-type'))

    def test_create_link_with_extra(self):
        extra = {'k1': 'v1', 'k2': 'v2'}
        expand = FetchXML.create_link(FetchXML.create_fetch(), 'link', 'from', 'to', extra=extra)
        self.assertEqual(expand.get('from'), 'from')
        self.assertEqual(expand.get('to'), 'to')
        self.assertFalse(hasattr(expand, 'link-type'))
        for k, v in extra.items():
            self.assertEqual(expand.get(k), v)

    def test_create_sub_elm(self):
        fetch = FetchXML.create_fetch()
        FetchXML.create_sub_elm(fetch, 'test')
        x = fetch.find('test')
        self.assertIsNotNone(x)
        self.assertEqual(len(x.keys()), 0)

    def test_create_sub_elm_with_attribs(self):
        fetch = FetchXML.create_fetch()
        FetchXML.create_sub_elm(fetch, 'test', {'k1': 'k1', 'k2': 'k2'})
        x = fetch.find('test')
        self.assertIsNotNone(x)
        self.assertEqual(len(x.keys()), 2)
        for k, v in x.items():
            self.assertEqual(k, v)

    def test_create_entity_with_links_filters(self):
        entity = FetchXML.create_entity(FetchXML.create_fetch(), 'salesorder')
        FetchXML.create_sub_elm(entity, 'attribute', {'name': 'name'})
        link_elm = FetchXML.create_link(entity, 'salesorderdetail', 'salesorderid', 'salesorderid')
        FetchXML.create_alias(link_elm, 'quantity', 'quantity')
        FetchXML.create_alias(link_elm, 'priceperunit', 'unitPrice')
        filternode = FetchXML.create_sub_elm(link_elm, 'filter', {'type': 'and'})
        FetchXML.create_condition(filternode, 'productid', 'eq', 'productid_value')
        link_node = entity.find('link-entity')
        self.assertIsNotNone(link_node)
        attribute_nodes = link_node.findall('attribute')
        self.assertEqual(len(attribute_nodes), 2)
        self.assertEqual(len(link_node.find('filter')), 1)

    def test_alias_check(self):
        entity = FetchXML.create_entity(FetchXML.create_fetch(), 'salesorder')
        with self.assertRaises(AssertionError):
            FetchXML.create_alias(entity, 'quantity', 'with space')
        with self.assertRaises(AssertionError):
            FetchXML.create_alias(entity, 'quantity', '9 start')
        with self.assertRaises(AssertionError):
            FetchXML.create_alias(entity, 'quantity', '_ start')
