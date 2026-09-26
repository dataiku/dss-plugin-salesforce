"""
This files contains kind of "wrapper functions" for Salesforce API and utility functions.
"""

import json
import requests
import time
from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import os.path
from utils import log


class SalesforceClient(object):

    CREATE_RECORD_ACTION = "sobjects/{object_name}"
    UPDATE_RECORD_ACTION = "sobjects/{object_name}/{object_id}"

    def __init__(self, config, plugin_config):
        self.plugin_config = plugin_config
        self.API_BASE_URL = None
        self.API_VERSION = "services/data/v61.0"
        self.ACCESS_TOKEN = None
        auth_type = config.get("auth_type", "legacy")
        if auth_type == "legacy":
            token = self.get_json(config.get("token"))
            self.API_BASE_URL = token.get("instance_url", None)
            self.ACCESS_TOKEN = token.get("access_token", None)
        elif auth_type == "oauth":
            auth_details = config.get(auth_type)
            token = {}
            self.ACCESS_TOKEN = auth_details.get("salesforce_oauth", None)
            instance_hostname = auth_details.get("instance_hostname", "")
            self.API_BASE_URL = "https://{instance_hostname}".format(instance_hostname=instance_hostname)
        else:
            auth_details = config.get(auth_type)
            token = self.get_token(auth_details)
            self.API_BASE_URL = token.get("instance_url", None)
            self.ACCESS_TOKEN = token.get("access_token", None)
        if not self.ACCESS_TOKEN:
            raise ValueError("Could not retrieve the access token")
        if self.API_BASE_URL is None or self.ACCESS_TOKEN is None:
            raise ValueError("JSON token must contain access_token and instance_url")
        self.API_BASE_URL = self.API_BASE_URL.strip("/")

        # Timeouts
        self.read_timeout = self.get_timeout_from_config("read_timeout", 120)
        self.write_timeout = self.get_timeout_from_config("write_timeout", 10)

        # Session object for requests
        self.session = requests.Session()
        # Retry strategy (cf http://stackoverflow.com/a/35504626/4969056)
        retries = Retry(total=3,
                        backoff_factor=2)
        self.session.mount('https://', HTTPAdapter(max_retries=retries))

    def get_timeout_from_config(self, key, default, min=10):
        try:
            timeout = self.plugin_config.get(key, default)
        except Exception as e:
            log("get_timeout_from_config warning: {}".format(e))
            timeout = default

        if timeout < min:
            timeout = min
        return timeout
    
    def create_record(self, object_name, salesforce_object):
        salesforce_object.pop('Id', None)
        response = self.make_api_call(
            self.CREATE_RECORD_ACTION.format(object_name=object_name),
            method="post",
            data=json.dumps(salesforce_object),
            ignore_errors=True
        )
        return response

    def update_record(self, object_name, object_id, salesforce_object):
        salesforce_object.pop('Id', None)
        response = self.make_api_call(
            self.UPDATE_RECORD_ACTION.format(object_name=object_name, object_id=object_id),
            method="patch",
            data=salesforce_object,
            ignore_errors=True
        )
        return response

    def make_api_call(self, action, parameters={}, method='get', data={}, ignore_errors=False):
        """
        Makes an API call to SalesForce
        Parameters: action (the URL), params, method (GET or POST), data for POST
        """
        headers = {
            'Content-type': 'application/json',
            'Accept-Encoding': 'gzip',
            'Authorization': 'Bearer %s' % self.ACCESS_TOKEN
        }
        if method == 'get':
            response = self.session.request(method, self.get_base_url(action), headers=headers, params=parameters, timeout=self.read_timeout)
        elif method == 'post':
            response = self.session.request(method, self.get_base_url(action), headers=headers, data=data, params=parameters, timeout=self.write_timeout)
        elif method == 'patch':
            response = self.session.request(method, self.get_base_url(action), headers=headers, data=json.dumps(data), params=parameters, timeout=self.write_timeout)
        else:
            raise ValueError('Method should be get, post or patch.')
        log('API %s call: %s' % (method, response.url))
        if ((response.status_code == 200 and method == 'get') or (response.status_code == 201 and method == 'post')):
            return response.json()
        elif (response.status_code == 204 and method == 'patch'):
            return {}
        elif ignore_errors:
            return {"error": response.status_code}
        else:
            raise ValueError('API error when calling %s : %s' % (response.url, response.text))

    def get_base_url(self, action):
        action = action.strip("/")
        if action.startswith(self.API_VERSION):
            # action comes from a pagination nextRecordsUrl token
            return "/".join([self.API_BASE_URL, action])
        return "/".join([self.API_BASE_URL, self.API_VERSION, action])

    def get_token(self, auth_details):
        """
        auth_type = config.get("auth_type", "legacy")
        if auth_type == "legacy":
            return get_json(config.get("token"))
        elif auth_type == ""
        auth_details = config.get(auth_type)
        """
        if not auth_details:
            raise Exception("Please select a credential preset")
        username = auth_details.get("username")
        password = "{}{}".format(auth_details.get("password", ""), auth_details.get("security_token", ""))
        client_id = auth_details.get("client_id")
        client_secret = auth_details.get("client_secret")
        private_key = auth_details.get("private_key", "")
        if auth_details.get('sandbox', False):
            token_url = "https://test.salesforce.com/services/oauth2/token"
        else:
            token_url = "https://login.salesforce.com/services/oauth2/token"
        if username and password:
            grant_type = "password"
            data = {
                "grant_type": grant_type,
                "client_id": client_id,
                "client_secret": client_secret,
                "username": username,
                "password": password
            }
        elif username and private_key:
            grant_type = "urn:ietf:params:oauth:grant-type:jwt-bearer"
            assertion = build_jwt_assertion(client_id, username, private_key, token_url)
            data = {
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion
            }
        else:
            grant_type = "client_credentials"
            data = {
                "grant_type": grant_type,
                "client_id": client_id,
                "client_secret": client_secret
            }
            instance_hostname = auth_details.get("instance_hostname", "")
            if not instance_hostname.startswith("http"):
                instance_hostname = "https://{}".format(instance_hostname)
            token_url = "{}/services/oauth2/token".format(instance_hostname.rstrip("/"))
        try:
            response = requests.post(token_url, data=data)
            json_response = response.json()
        except Exception as error:
            raise Exception("Could not retrieve the access token: {}".format(error))
        if "error" in json_response or "error_description" in json_response:
            raise Exception("Error while retrieving the acces token: {} {}".format(
                json_response.get("error", ""),
                json_response.get("error_description", "")
            ))
        return json_response

    def get_json(self, input):
        """
        In the UI, the input can be a JSON object or a file path to a JSON object.
        This function takes any, and return the object.
        """

        if os.path.isfile(input):
            try:
                with open(input, 'r') as f:
                    obj = json.load(f)
                    f.close()
            except Exception as e:
                log("Error {}".format(e))
                raise ValueError("Unable to read the JSON file: %s" % input)
        else:
            try:
                obj = json.loads(input)
            except Exception as e:
                log("Error {}".format(e))
                raise ValueError("Unable to read the JSON: %s" % input)

        return obj


def build_jwt_assertion(client_id, user_email, private_key, login_url):
    import jwt
    EXPIRES_IN_SECONDS = 180
    now = int(time.time())
    audience = login_url.rstrip("/")
    payload = {
        "iss": client_id,
        "sub": user_email,
        "aud": audience,
        "exp": now + EXPIRES_IN_SECONDS,
    }
    assertion = jwt.encode(payload, private_key, algorithm="RS256")
    return assertion
