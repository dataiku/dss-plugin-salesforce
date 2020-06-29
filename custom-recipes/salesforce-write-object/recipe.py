# -*- coding: utf-8 -*-
import dataiku
from dataiku.customrecipe import get_output_names_for_role, get_recipe_config, get_input_names_for_role
import json
from salesforce import SalesforceClient


# Output
output_name = get_output_names_for_role('main')[0]
output = dataiku.Dataset(output_name)
output.write_schema([
    {"name": "operation", "type": "string"},
    {"name": "error", "type": "string"},
    {"name": "salesforce_record_id", "type": "string"},
    {"name": "data", "type": "object"}
])

# Read configuration
config = get_recipe_config()
object_name = config.get('object_name', None)
if object_name is None:
    raise Exception("Object name has to be set")

client = SalesforceClient(config)

incoming_dataset_name = get_input_names_for_role('incoming_dataset_name')
incoming_dataset = dataiku.Dataset(incoming_dataset_name[0])
incoming_dataset_df = incoming_dataset.get_dataframe()
writer = output.get_writer()
json_dataset = json.loads(incoming_dataset_df.to_json(orient="records"))  # turning row into json would get None int to be replaced by NaN
for salesforce_record in json_dataset:
    salesforce_record_id = salesforce_record.pop("Id", None)
    if salesforce_record_id is None:
        response = client.create_record(object_name, salesforce_record)
        writer.write_row_dict({
            "operation": "Added",
            "error": response.get("error", None),
            "salesforce_record_id": response.get("id", None),
            "data": json.dumps(salesforce_record)
        })
    else:
        response = client.update_record(object_name, salesforce_record_id, salesforce_record)
        writer.write_row_dict({
            "operation": "Updated",
            "error": response.get("error", None),
            "salesforce_record_id": salesforce_record_id,
            "data": json.dumps(salesforce_record)
        })

writer.close()
