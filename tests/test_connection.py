import re
import unittest

from .context import edynam
from edynam.connection import ADALConnection


class TestConnectionMethods(unittest.TestCase):
    def test_required_parameters(self):
        # KeyError message has ""
        missed = re.compile(r"^\"Missing item.+\'(.*)\'")
        parameters = {}
        has_exception = True
        while has_exception:
            try:
                ADALConnection(parameters)
            except KeyError as err:
                missed_key = missed.match(str(err))
                self.assertTrue(missed_key)
                parameters[missed_key.group(1)] = missed_key.group(1)
            except Exception:
                # force to fail if there is unexpected exception
                self.assertFalse(has_exception)
            else:
                has_exception = False
        self.assertFalse(has_exception)
        self.assertGreater(len(parameters), 4)
        for k, v in parameters.items():
            self.assertEqual(k, v)
