from dataiku.connector import Connector
import json
import salesforce


class MyConnector(Connector):

    def __init__(self, config):
        Connector.__init__(self, config)

        auth_type = self.config.get("auth_type", "legacy")
        if auth_type == "legacy":
            token = salesforce.get_json(self.config.get("token"))
        else:
            token = salesforce.get_token(self.config)

        try:
            salesforce.API_BASE_URL = token.get('instance_url')
            salesforce.ACCESS_TOKEN = token.get('access_token')
        except Exception as e:
            salesforce.log("Error {}".format(e))
            raise ValueError("JSON token must contain access_token and instance_url")

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

        results = salesforce.make_api_call('/services/data/v37.0/sobjects/')

        salesforce.log("records_limit: {}".format(records_limit))

        counter = 0

        for obj in results.get('sobjects'):
            if self.RESULT_FORMAT == 'json':
                row = {"json": json.dumps(obj)}
            else:
                row = {}
                for key, val in obj.iteritems():
                    if type(val) is dict:
                        row[key] = json.dumps(val)
                    else:
                        row[key] = val
            counter = counter + 1
            if records_limit < 0 or counter <= records_limit:
                yield row
