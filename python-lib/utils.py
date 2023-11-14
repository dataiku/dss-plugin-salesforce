import json
import six


def iterate_dict(dictionary, parents=[]):
    """
    This function iterates over one dict and returns a list of tuples: (list_of_keys, value)
    Usefull for looping through a multidimensional dictionary.
    """

    ret = []
    for key, value in six.iteritems(dictionary):
        if isinstance(value, dict):
            ret.extend(iterate_dict(value, parents + [str(key)]))
        elif isinstance(value, list):
            ret.append((parents + [str(key)], value))
        else:
            ret.append((parents + [str(key)], value))
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


def assert_response_ok(response):
    if response.status_code >= 400:
        error_message = "Error {}: {}".format(response.status_code, response.content)
        log(error_message)
        raise Exception(error_message)


def log(*args):
    for thing in args:
        if type(thing) is dict:
            thing = json.dumps(thing)
        print('Salesforce plugin - %s' % thing)
