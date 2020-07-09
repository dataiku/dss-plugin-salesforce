from dataiku.connector import Connector
import json
from salesforce import SalesforceClient
from utils import log


class MyConnector(Connector):

    def __init__(self, config):
        Connector.__init__(self, config)

        self.client = SalesforceClient(self.config)

        self.REPORT = self.config.get("report", "")
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

        results = self.client.make_api_call("/services/data/v39.0/analytics/reports/%s" % self.REPORT, parameters={"includeDetails": True})

        report_format = results.get("reportMetadata").get("reportFormat")

        if report_format != "TABULAR":
            raise Exception("The format of the report is %s but the plugin only supports TABULAR." % report_format)

        columns = results.get("reportMetadata").get("detailColumns", [])
        log(columns)

        log("records_limit: %i" % records_limit)

        n = 0

        for obj in results.get("factMap").get("T!T", {}).get("rows", []):
            arr = obj.get("dataCells", {})
            if self.RESULT_FORMAT == 'json':
                els = {}
                for c, o in zip(columns, arr):
                    els[c] = o
                row = {"json": json.dumps(els)}
            else:
                row = {}
                for c, o in zip(columns, arr):
                    row[c] = o["label"]
            n = n + 1
            if records_limit < 0 or n <= records_limit:
                yield row
