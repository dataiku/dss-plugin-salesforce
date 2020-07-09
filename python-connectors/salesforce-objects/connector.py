from dataiku.connector import Connector
import json
from salesforce import SalesforceClient
from utils import log
import six


class MyConnector(Connector):

    def __init__(self, config):
        Connector.__init__(self, config)

        self.client = SalesforceClient(self.config)

        self.RESULT_FORMAT = self.config.get("result_format")

    def get_read_schema(self):

        if self.RESULT_FORMAT == 'json':
            return {
                    "columns": [
                        {"name": "json", "type": "object"}
                    ]
                }

        return None

    def generate_rows(self, dataset_schema=None, dataset_partitioning=None,
                      partition_id=None, records_limit=-1):

        results = self.client.make_api_call('/services/data/v37.0/sobjects/')

        log("records_limit: {}".format(records_limit))

        counter = 0

        for obj in results.get('sobjects'):
            if self.RESULT_FORMAT == 'json':
                row = {"json": json.dumps(obj)}
            else:
                row = {}
                for key, val in six.iteritems(obj):
                    if type(val) is dict:
                        row[key] = json.dumps(val)
                    else:
                        row[key] = val
            counter = counter + 1
            if records_limit < 0 or counter <= records_limit:
                yield row
