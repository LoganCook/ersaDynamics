import sys
import json
import random
import string
import logging

from urllib.parse import parse_qs, urlparse

import requests
from adal import AuthenticationContext
from adal.adal_error import AdalError

AUTHZ_URL_FMT = ('https://login.windows.net/{}/oauth2/authorize?' +
                 'response_type=code&client_id={}&resource={}')
TOKEN_TYPE = 'Bearer'
logger = logging.getLogger(__name__)


class ADALConnection(object):
    """
    Use someone's login code to get token without hacking

    General usages:
    1. Call this script with only config file:
        python connection.py conf.json
       The script prints a login url for logging in to get tokens
    2. Once successfully logged in, copy the url in browser's address bar and run:
        python connection.py conf.json WHAT_EVER_URL_IS
       url can be very long. The result will be saved in saved_tokens.json
       by default for later use. Ignore the error message in browser.
    3. Use saved access_token to reconnect by calling retrieve. If access_token expired,
       try to use refresh_token to update the file with new tokens. If tires failed,
       print message and ask for login again.
    4. Calling refresh to refresh tokens without trying them.
    """

    REQUIRED_PARAS = ('resource', 'tenant', 'authorityHostUrl', 'clientId', 'clientSecret')

    def __init__(self, parameters):
        self._validate_parameters(parameters)
        self.parameters = parameters
        self.tokens = {}
        self.token_file = 'saved_tokens.json'

    @property
    def access_token(self):
        return self.tokens.get('access_token')

    @property
    def refresh_token(self):
        return self.tokens.get('refresh_token')

    @property
    def resource(self):
        """Which resource this connection is for"""
        return self.parameters['resource']

    @staticmethod
    def _generate_sate():
        """Generate a random string to prevent CSRF attack"""

        # Currently, use the method from the example from AAD. Can be anything for CSRF
        # character pool for generating state string
        CHPOOL = string.ascii_uppercase + string.digits
        MAX_LENGTH = 8

        auth_state = ''.join(
            random.SystemRandom()
            .choice(CHPOOL) for _ in range(MAX_LENGTH))
        return auth_state

    def _validate_parameters(self, parameters):
        for key in self.REQUIRED_PARAS:
            if key not in parameters:
                raise KeyError("Missing item '%s' from required parameters" % key)

    def _get_authority_url(self):
        return self.parameters['authorityHostUrl'] + '/' + self.parameters['tenant']

    def print_login_url(self):
        """Construct the login url and print instruction"""
        print("Your login url is:")

        # It is recommended to use state to prevent CSRF
        # but get method has no good way to verify it,
        # it is kind of a waste to have it.
        # auth_state = self._generate_sate()

        authorization_url = AUTHZ_URL_FMT.format(self.parameters['tenant'],
                                                 self.parameters['clientId'],
                                                 self.parameters['resource'])
        print(authorization_url)
        print("Once you have successfully logged in,",
              "copy the content in address bar",
              "and come back again with it as another argument.")

    def _to_file(self, name):
        with open(name, 'w') as jf:
            json.dump(self.tokens, jf)

    def _from_file(self, name):
        with open(name, 'r') as jf:
            self.tokens = json.load(jf)

    def _save(self, response, file_name):
        """Save token response"""
        # print(response)
        # for (k, v) in response.items():
        #     print(k, ":")
        #     print(v)

        # print("Please save these two:")
        # print(response['accessToken'][:10])
        # print(response['refreshToken'][:10])
        self.tokens['access_token'] = response['accessToken']
        self.tokens['refresh_token'] = response['refreshToken']
        self._to_file(file_name)

    def get(self, code_url, saved_file=None):
        """Get the token of a logged in user by the code in the code_url and save it in a file"""

        parsed = urlparse(code_url)
        # print(parsed)
        if not parsed.query:
            print("Cannot parse redirected url")
            return

        code = parse_qs(parsed.query)['code'][0]
        # Currently, no plan to use/verify state, so retrieve it has been commented out
        # state = parse_qs(parsed.query)['state'][0]

        print("About to use your code shown below to retrieve tokens")
        print(code[0:10], "..", code[-10:])
        # token_response has such keys:
        # tenantId :
        # isUserIdDisplayable :
        # expiresOn : 2016-10-11 16:51:21.663197
        # oid :
        # tokenType : Bearer
        # givenName :
        # familyName :
        # userId :
        # resource :
        # expiresIn : 3600
        # accessToken :
        # refreshToken :
        auth_context = AuthenticationContext(self._get_authority_url())
        try:
            token_response = auth_context.acquire_token_with_authorization_code(
                code,
                None,
                self.parameters['resource'],
                self.parameters['clientId'],
                self.parameters['clientSecret'])
        except requests.exceptions.ConnectionError as err:
            print("Failed to connect to the server")
            print(err)
        except AdalError as err:
            print("ADAL error")
            error_codes = err.error_response['error_codes']
            if any(code in error_codes for code in (70002, 70008)):
                print("Need to log in to get a new authorization code")
            # print(err.error_response['error'])
            # print(err.error_response['error_description'])
        except Exception as err:
            # requests.exceptions.ConnectionError
            print("You did something wrong")
            print(type(err))
            print(dir(err))
            print(err)
        else:
            print("All went well, save them")
            if saved_file is None:
                saved_file = self.token_file
            self._save(token_response, saved_file)

    def retrieve(self, saved_file='saved_tokens.json'):
        """Retrieve a token from a file"""
        try:
            self._from_file(saved_file)
            self.token_file = saved_file
        except OSError as err:
            logger.error(err)
            raise Exception("Cannot read tokens from %s. Detail: %s" % (saved_file, str(err)))

    def refresh(self, saved_file=None):
        """Refresh an expired access token of current connection or a saved file.

        New tokens are saved in the given file or default 'saved_tokens.json'.

        :param str saved_file: path to a file which contains access and refresh tokens. Default None
        """
        if saved_file:
            self.retrieve(saved_file)
        else:
            # verify self.tokens has keys
            if not ('access_token' in self.tokens and 'refresh_token' in self.tokens):
                raise KeyError("Tokens have not been set - cannot refresh.")

        try:
            auth_context = AuthenticationContext(self._get_authority_url())
            token_response = auth_context.acquire_token_with_refresh_token(
                self.tokens['refresh_token'],
                self.parameters['clientId'],
                self.parameters['resource'],
                self.parameters['clientSecret'])
        except Exception as err:
            logger.error(err)
        else:
            self._save(token_response, self.token_file)

    def generate_auth_header(self, refresh=False):
        if refresh:
            self.refresh()
        return {'Authorization': '%s %s' % (TOKEN_TYPE, self.access_token)}


if __name__ == "__main__":
    args = len(sys.argv)

    if args < 2:
        raise ValueError("Need a config json file and optional login code")

    conf = sys.argv[1]
    with open(conf, 'r') as jf:
        parameters = json.load(jf)

    try:
        x = ADALConnection(parameters)
    except KeyError as err:
        print(err)
        sys.exit(err)

    # x.refresh('saved_tokens.json')
    # sys.exit(0)

    if args < 3:
        x.print_login_url()
    else:
        x.get(sys.argv[2])
