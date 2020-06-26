"""
This files contains kind of "wrapper functions" for Salesforce API and utility functions.
"""

import json
import requests
from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import os.path


# Basic logging
def log(*args):
    for thing in args:
        if type(thing) is dict:
            thing = json.dumps(thing)
        print('Salesforce plugin - %s' % thing)


# Session object for requests
session = requests.Session()
# Retry strategy (cf http://stackoverflow.com/a/35504626/4969056)
retries = Retry(total=3,
                backoff_factor=2)
session.mount('https://', HTTPAdapter(max_retries=retries))

# Global variables
API_BASE_URL = ''
ACCESS_TOKEN = ''


def make_api_call(action, parameters={}, method='get', data={}, ignore_errors=False):
    """
    Makes an API call to SalesForce
    Parameters: action (the URL), params, method (GET or POST), data for POST
    """
    headers = {
        'Content-type': 'application/json',
        'Accept-Encoding': 'gzip',
        'Authorization': 'Bearer %s' % ACCESS_TOKEN
    }
    if method == 'get':
        response = session.request(method, API_BASE_URL+action, headers=headers, params=parameters, timeout=30)
    elif method == 'post':
        response = session.request(method, API_BASE_URL+action, headers=headers, data=data, params=parameters, timeout=10)
    elif method == 'patch':
        response = session.request(method, API_BASE_URL+action, headers=headers, data=json.dumps(data), params=parameters, timeout=10)
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


def get_token(config):
    auth_type = config.get("auth_type", "legacy")
    if auth_type == "legacy":
        return get_json(config.get("token"))
    auth_details = config.get(auth_type)
    data = {
        "grant_type": "password",
        "client_id": auth_details.get("client_id"),
        "client_secret": auth_details.get("client_secret"),
        "username": auth_details.get("username"),
        "password": "{}{}".format(auth_details.get("password"), auth_details.get("security_token"))
    }
    response = requests.post("https://login.salesforce.com/services/oauth2/token", data=data)
    return response.json()


def update_token(config):
    token = get_token(config)
    API_BASE_URL = token.get('instance_url', None)
    ACCESS_TOKEN = token.get('access_token', None)
    if API_BASE_URL is None or ACCESS_TOKEN is None:
        raise Exception("JSON token must contain access_token and instance_url")


def get_json(input):
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


def iterate_dict(dictionary, parents=[]):
    """
    This function iterates over one dict and returns a list of tuples: (list_of_keys, value)
    Usefull for looping through a multidimensional dictionary.
    """

    ret = []
    for key, value in dictionary.iteritems():
        if isinstance(value, dict):
            ret.extend(iterate_dict(value, parents + [key]))
        elif isinstance(value, list):
            ret.append((parents + [key], value))
        else:
            ret.append((parents + [key], value))
    return ret


def unnest_json(row_obj):
    """
    Iterates over a JSON to tranfsorm each element into a column.
    Example:
    {'a': {'b': 'c'}} -> {'a.b': 'c'}
    """
    row = {}
    for keys, value in iterate_dict(row_obj):
        row[".".join(keys)] = value if value is not None else ''
    return row
