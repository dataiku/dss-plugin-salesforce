from dataiku.llm.agent_tools import BaseAgentTool
from salesforce import SalesforceClient
from safe_logger import SafeLogger


logger = SafeLogger("salesforce plugin")


class SalesforceLookupAccountTool(BaseAgentTool):
    """
    Looks up a Salesforce account by name.
    • First attempts an exact match.
    • If none found, falls back to a LIKE search.
    • Returns the single best match (or a 'not found' message).
    """

    # ------------------------------------------------------------- CONFIG
    def set_config(self, config, plugin_config):
        self.client = SalesforceClient(config)

    # ---------------------------------------------------------- DESCRIPTOR
    def get_descriptor(self, tool):
        return {
            "description": (
                "Look up a Salesforce account by name. "
                "Provide {'Name': '<account name>'}. "
                "Returns the single best‑matched account record."
            ),
            "inputSchema": {
                "$id": "https://dataiku.com/agents/tools/search/input",
                "title": "Salesforce account lookup tool",
                "type": "object",
                "properties": {
                    "Name": {
                        "type": "string",
                        "description": "Exact or partial account name"
                    }
                },
                "required": ["Name"]
            }
        }

    def invoke(self, input, trace):
        args = input.get("input", {})

        trace.span["name"] = "SALESFORCE_LOOKUP_ACCOUNT_TOOL_CALL"
        for key, value in args.items():
            trace.inputs[key] = value
        trace.attributes["config"] = self.config

        raw_name = args.get("Name", "").strip()
        if not raw_name:
            output_text = "Account name cannot be empty."
            trace.outputs["output"] = output_text
            return {
                "output": output_text
            }

        # Escape single quotes for SOQL safety
        name = raw_name.replace("'", "\\'")
        base_fields = (
            "Id, Name, Website, Industry, Phone, Type, BillingCity, BillingCountry"
        )

        # ---------- 1) exact match
        exact_q = f"SELECT {base_fields} FROM Account WHERE Name = '{name}' LIMIT 1"
        try:
            resp = self.client.make_api_call("/query/", {"q": exact_q})
            recs = resp.get("records", [])
            if recs:
                output_text = recs[0]
                trace.outputs["output"] = output_text
                return {
                    "output": output_text
                }
        except Exception as err:
            logger.error("Exact‑match query failed: %s", err)
            output_text = f"There was a problem while looking up the account: {err}"
            trace.outputs["output"] = output_text
            return {
                "output": output_text
            }

        # ---------- 2) fallback LIKE search
        like_q = (
            f"SELECT {base_fields} FROM Account "
            f"WHERE Name LIKE '%{name}%' "
            "LIMIT 1"
        )
        try:
            resp = self.client.make_api_call("/queryAll/", {"q": like_q})
            recs = resp.get("records", [])
        except Exception as err:
            logger.error("LIKE query failed: %s", err)
            output_text = f"There was a problem while looking up the account: {err}"
            trace.outputs["output"] = output_text
            return {
                "output": output_text
            }

        if not recs:
            output_text = "No Salesforce account matched the supplied name."
            trace.outputs["output"] = output_text
            return {
                "output": output_text
            }
        
        output_text = recs[0]
        trace.outputs["output"] = output_text
        return {
            "output": output_text
        }