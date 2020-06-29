import json


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


def log(*args):
    for thing in args:
        if type(thing) is dict:
            thing = json.dumps(thing)
        print('Salesforce plugin - %s' % thing)
