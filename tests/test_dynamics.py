import unittest
from unittest.mock import patch

from .context import edynam
from edynam.connection import ADALConnection
from edynam.dynamics import Dynamics


class TestDynamicsMethods(unittest.TestCase):
    def setUp(self):
        with patch.object(ADALConnection, '_validate_parameters', return_value=None) as mocked_validator:
            conn = ADALConnection({})
            conn.parameters['resource'] = 'mocked'
        self.assertTrue(mocked_validator.called)
        self.conn = conn

    def test_construct_headers(self):
        dynamics = Dynamics(self.conn)
        default = dynamics.construct_headers()

        values = ('first', 'second', 'third')
        for i in range(len(values) + 1):
            other = dict(zip(values[0:i], values[0:i]))
            ex_headers = dynamics.construct_headers(other)
            self.assertEqual(len(ex_headers), len(default) + i)
            for j in range(i):
                self.assertTrue(values[j] in ex_headers)
                self.assertEqual(values[j], ex_headers[values[j]])

    def test_get_tried_twice(self):
        with patch.object(Dynamics, '_get_content', side_effect=ConnectionError('error_status_code')) as mocked_content:
            dynamics = Dynamics(self.conn)
            with patch.object(self.conn, 'refresh', return_value=None):
                with self.assertRaises(ConnectionError):
                    dynamics.get('some_end_point')
        self.assertTrue(mocked_content.called)
        self.assertEqual(mocked_content.call_count, 2)
