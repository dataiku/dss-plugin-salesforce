# -*- coding: utf-8 -*-
import dataiku
from dataiku.customrecipe import get_output_names_for_role, get_recipe_config, get_input_names_for_role
import json
import salesforce


# Output
output_name = get_output_names_for_role('main')[0]
output = dataiku.Dataset(output_name)
output.write_schema([
    {"name": "operation", "type": "string"},
    {"name": "error", "type": "string"},
    {"name": "salesforce_id", "type": "string"},
    {"name": "data", "type": "object"}
])

# Read configuration
config = get_recipe_config()
object_name = config.get('object_name', None)
if object_name is None:
    raise Exception("Object name has to be set")

token = salesforce.get_token(config)
try:
    salesforce.API_BASE_URL = token.get('instance_url')
    salesforce.ACCESS_TOKEN = token.get('access_token')
except Exception as e:
    salesforce.log("Error {}".format(e))
    raise ValueError("JSON token must contain access_token and instance_url")

incoming_dataset_name = get_input_names_for_role('incoming_dataset_name')
incoming_dataset = dataiku.Dataset(incoming_dataset_name[0])
incoming_dataset_df = incoming_dataset.get_dataframe()
writer = output.get_writer()
json_dataset = json.loads(incoming_dataset_df.to_json(orient="records"))  # turning row into json would get None int to be replaced by NaN
for row in json_dataset:
    row_id = row.get("Id", None)
    if row_id is None:
        data = row
        data.pop('Id', None)
        response = salesforce.make_api_call("/services/data/v20.0/sobjects/" + object_name, method="post", data=json.dumps(data), ignore_errors=True)
        writer.write_row_dict({
            "operation": "Added",
            "error": response.get("error", None),
            "salesforce_id": response.get("id", None),
            "data": json.dumps(data)
        })
    else:
        data = row
        data.pop('Id', None)
        url = "/services/data/v20.0/sobjects/" + object_name + "/" + row_id
        response = salesforce.make_api_call(url, method="patch", data=data, ignore_errors=True)
        data['DSS_operation'] = "Updated"
        writer.write_row_dict({
            "operation": "Updated",
            "error": response.get("error", None),
            "salesforce_id": row_id,
            "data": json.dumps(data)
        })

writer.close()
