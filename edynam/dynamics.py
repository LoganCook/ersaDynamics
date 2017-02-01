import json
import logging
import requests


from .connection import ADALConnection


def parse_www_authenticate(raw_string):
    return dict(pair.strip().split('=') for pair in raw_string.split(','))

DYNAMICS_VER = '8.2'
FORMATTED_VALUE_SUF = 'OData.Community.Display.V1.FormattedValue'
logger = logging.getLogger(__name__)


class Dynamics(object):
    """RESTful methods for communicating with MS Dynamics

    It handles ADALConnection through an instance of ADALConnection.
    Most methods just need to know end point and query stings, some
    need to set headers.
    """
    def __init__(self, connection):
        """
        :param ADALConnection connection: ADAL connection instance
        """
        self._conn = connection

    def _get_url_of(self, end_point):
        return '%s/api/data/v%s/%s' % (self._conn.resource, DYNAMICS_VER, end_point)

    @staticmethod
    def construct_headers(other={}):
        # for POST, which has JSON data in request body, should include:
        # 'Content-Type': 'application/json'
        # Prefer header with key odata.include-annotations with one of the choices, to include:
        # 1. formatted values:
        #    odata.include-annotations=OData.Community.Display.V1.FormattedValue
        # 2. name of the single-valued navigation property:
        #    odata.include-annotations=Microsoft.Dynamics.CRM.associatednavigationproperty
        # 3. logical name of the entity referenced by the lookup:
        #    'odata.include-annotations=Microsoft.Dynamics.CRM.lookuplogicalname'
        # 4. more than one:
        #    all three:
        #      odata.include-annotations="*"
        #    two var namespace:
        #      odata.include-annotations=Microsoft.Dynamics.CRM.*
        # https://msdn.microsoft.com/en-us/library/mt607901.aspx;
        # Note: multiple values with separating commas does not work for odata.include-annotations
        # Pagination using Prefer:
        #    odata.maxpagesize=n (n <= 5000)
        #  use @odata.nextlink for further queries
        headers = {
            'OData-MaxVersion': '4.0',
            'OData-Version': '4.0',
            'Accept': 'application/json',
            'Prefer': 'odata.include-annotations=' + FORMATTED_VALUE_SUF
        }
        headers.update(other)
        return headers

    @staticmethod
    def _get_content(url, headers, params={}):
        """Makes request at url and turn string to a JSON object

        Raises ConnectionError with status code.
        """
        r = requests.get(url, headers=headers, params=params)
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 401:
            raise ConnectionError(r.status_code)
        else:
            # TODO: what error to raise? Is status code only enough?
            # www_authenticate_header = parse_www_authenticate(r.headers['WWW-Authenticate'])
            # raise RuntimeError('Unauthorized access. Error code: %(Bearer error)s, description: %(error_description)s' % www_authenticate_header)
            logger.debug(r.url)
            logger.debug(r.status_code)
            try:
                logger.error(r.json()['error']['message'])
            except ValueError:
                logger.error(r.status_code)
            except Exception as err:
                logger.error(err)
                logger.error(r.json())
            else:
                raise LookupError(r.status_code)

    def get(self, end_point, params={}):
        """Get method which tries twice

        First to use access_token. If access_token fails, it uses refresh
        token to get a new access_token, try again. If still fails, raise
        exception.
        """
        # TODO: better to allow extra headers
        # use case: formatted (most likely be useful)
        #           lookup and navigation (so far only customer in Contact)
        def extract_value(raw_content):
            if 'value' in raw_content:
                content = raw_content['value']
            elif '@odata.context' in raw_content:
                content = raw_content
            else:
                logger.error("No @odata.context or value key!!!")
                logger.debug(raw_content)
                raise ValueError('Unqualified query result: no @odata.context or value key.')
            return content

        url = self._get_url_of(end_point)
        content = None
        try:
            headers = self.construct_headers(self._conn.generate_auth_header())
            content = extract_value(self._get_content(url, headers, params))
        except ConnectionError as err:
            logger.debug("Debugging %s", str(err))
            # refresh can fail
            headers = self.construct_headers(self._conn.generate_auth_header(True))
            # content = self._get_content(url, headers, params)
            content = extract_value(self._get_content(url, headers, params))
            # if still fails let caller know
        return content

    def get_accounts(self):
        try:
            accounts = self.get('accounts')
            for elm in accounts['value']:
                for k, v in elm.items():
                    logger.debug(k, v)
                break

        except Exception:
            logger.error('No valid access token and refresh failed to get a new access token.')

    def get_top(self):
        try:
            params = {'$filter': '_parentaccountid_value eq null',
                      '$count': 'true',
                      '$select': 'name'}
            accounts = self.get('accounts', params)
            logger.debug("Total count: %s" % accounts['@odata.count'])
            for elm in accounts['value']:
                for k, v in elm.items():
                    logger.debug(k, v)
                break

        except Exception:
            logger.error('No valid access token and refresh failed to get a new access token.')


if __name__ == "__main__":
    conf = 'conf.json'
    with open(conf, 'r') as jf:
        parameters = json.load(jf)

    conn = ADALConnection(parameters)
    conn.retrieve('saved_tokens.json')

    reader = Dynamics(conn)
    try:
        reader.get_top()
    except Exception as err:
        logger.error(err)
