from dataiku.connector import Connector
import json
from salesforce import SalesforceClient
from utils import unnest_json, log


class MyConnector(Connector):

    def __init__(self, config):
        Connector.__init__(self, config)

        self.client = SalesforceClient(self.config)

        self.OBJECT = self.config.get("object", "")
        self.LIMIT = self.config.get("limit", "")
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

        # First, building an SOQL query

        describe = self.client.make_api_call('/services/data/v39.0/sobjects/%s/describe' % self.OBJECT)

        log(describe)

        if not describe.get('queryable', False):
            raise ValueError("This object is not queryable")

        fields = [f['name'] for f in describe.get('fields')]

        query = "SELECT %s FROM %s LIMIT %i" % (
                ", ".join(fields),
                self.OBJECT,
                self.LIMIT
            )

        log(query)

        # Then, running the SOQL query

        results = self.client.make_api_call('/services/data/v39.0/queryAll/', {'q': query})

        log("records_limit: %i" % records_limit)
        log("length initial request: %i" % len(results.get('records')))

        n = 0

        for obj in results.get('records'):
            n = n + 1
            if records_limit < 0 or n <= records_limit:
                yield self._format_row_for_dss(obj)

        next = results.get('nextRecordsUrl', None)
        if records_limit >= 0 and n >= records_limit:
            next = None

        while next:
            results = self.client.make_api_call(next)
            for obj in results.get('records'):
                n = n + 1
                if records_limit < 0 or n <= records_limit:
                    yield self._format_row_for_dss(obj)
            next = results.get('nextRecordsUrl', None)
            if records_limit >= 0 and n >= records_limit:
                next = None

    def _format_row_for_dss(self, row):

        if self.RESULT_FORMAT == 'json':
            return {"json": json.dumps(row)}
        else:
            return unnest_json(row)
