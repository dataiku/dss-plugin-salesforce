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

    # -------------------------------------------------------------- INVOKE
    def invoke(self, input, trace):
        args = input.get("input", {})
        raw_name = args.get("Name", "").strip()
        if not raw_name:
            return {"output": "Account name cannot be empty."}

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
                return {"output": recs[0]}
        except Exception as err:
            logger.error("Exact‑match query failed: %s", err)
            return {"output": f"There was a problem while looking up the account: {err}"}

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
            return {"output": f"There was a problem while looking up the account: {err}"}

        if not recs:
            return {"output": "No Salesforce account matched the supplied name."}

        return {"output": recs[0]}
