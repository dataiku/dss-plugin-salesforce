"""
This files contains kind of "wrapper functions" for Salesforce API and utility functions.
"""

import json
import requests
from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import os.path
from utils import log


class SalesforceClient(object):

    CREATE_RECORD_ACTION = "/services/data/v39.0/sobjects/{object_name}"
    UPDATE_RECORD_ACTION = "/services/data/v39.0/sobjects/{object_name}/{object_id}"

    def __init__(self, config):
        self.API_BASE_URL = None
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
        if self.API_BASE_URL is None or self.ACCESS_TOKEN is None:
            raise ValueError("JSON token must contain access_token and instance_url")


        # Session object for requests
        self.session = requests.Session()
        # Retry strategy (cf http://stackoverflow.com/a/35504626/4969056)
        retries = Retry(total=3,
                        backoff_factor=2)
        self.session.mount('https://', HTTPAdapter(max_retries=retries))

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
            response = self.session.request(method, self.API_BASE_URL+action, headers=headers, params=parameters, timeout=30)
        elif method == 'post':
            response = self.session.request(method, self.API_BASE_URL+action, headers=headers, data=data, params=parameters, timeout=10)
        elif method == 'patch':
            response = self.session.request(method, self.API_BASE_URL+action, headers=headers, data=json.dumps(data), params=parameters, timeout=10)
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
            raise ValueError('API error when calling %s : %s' % (response.url, response.content))

    def get_token(self, auth_details):
        """
        auth_type = config.get("auth_type", "legacy")
        if auth_type == "legacy":
            return get_json(config.get("token"))
        elif auth_type == ""
        auth_details = config.get(auth_type)
        """
        data = {
            "grant_type": "password",
            "client_id": auth_details.get("client_id"),
            "client_secret": auth_details.get("client_secret"),
            "username": auth_details.get("username"),
            "password": "{}{}".format(auth_details.get("password"), auth_details.get("security_token"))
        }
        if auth_details.get('sandbox', False):
            token_url = "https://test.salesforce.com/services/oauth2/token"
        else:
            token_url = "https://login.salesforce.com/services/oauth2/token"
        response = requests.post(token_url, data=data)
        return response.json()

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
