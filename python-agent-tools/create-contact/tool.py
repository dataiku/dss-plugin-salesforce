from dataiku.llm.agent_tools import BaseAgentTool
from salesforce import SalesforceClient
from safe_logger import SafeLogger


logger = SafeLogger("salesforce plugin")


class SalesforceCreateContactTool(BaseAgentTool):
    def set_config(self, config, plugin_config):
        self.config = config
        self.client = SalesforceClient(config)

    def get_descriptor(self, tool):
        return {
            "description": "This tool is a wrapper around Salesforce contact create API, useful when you need to add a new contact to Salesforce. The input to this tool is a dictionary containing the new contact details, e.g. '{'LastName':'Doe', 'FirstName':'John'}'",
            "inputSchema": {
                "$id": "https://dataiku.com/agents/tools/search/input",
                "title": "Create Salesforce contact tool",
                "type": "object",
                "properties": {
                    "LastName": {
                        "type": "string",
                        "description": "The contact's last name"
                    },
                    "FirstName": {
                        "type": "string",
                        "description": "The contact's first name"
                    },
                    "Salutation": {
                        "type": "string",
                        "description": "The contact's stalutation. The value can be Mr., Ms., Mrs., Dr. or Prof."
                    },
                    "Email": {
                        "type": "string",
                        "description": "The contact's email address"
                    },
                    "Title": {
                        "type": "string",
                        "description": "The contact's title in the company, for instance CFO, CEO, Sales Engineer..."
                    },
                    "Department": {
                        "type": "string",
                        "description": "The department where the contact is working, for instance Procurement, Finance..."
                    },
                    "AssistantName": {
                        "type": "string",
                        "description": "The name of the contact's assistant, if the information is avaible."
                    },
                    "LeadSource": {
                        "type": "string",
                        "description": "The source of the information. The value can be: Web, Trade Show, Phone Inquiry, Partner Referral, Purchased List, Other."
                    },
                    "Birthdate": {
                        "type": "string",
                        "description": "The contact's birthdate, in YYYY-MM-DD format."
                    },
                    "MailingStreet": {
                        "type": "string",
                        "description": "The street name and number of the contact's address"
                    },
                    "MailingCity": {
                        "type": "string",
                        "description": "The city name of the contact's address"
                    },
                    "MailingState": {
                        "type": "string",
                        "description": "The state or province of the contact's address, if applies"
                    },
                    "MailingPostalCode": {
                        "type": "string",
                        "description": "The post code of the contact's address"
                    },
                    "MailingCountry": {
                        "type": "string",
                        "description": "The country of the contact's address"
                    },
                    "Phone": {
                        "type": "string",
                        "description": "The phone number of the contact"
                    },
                    "MobilePhone": {
                        "type": "string",
                        "description": "The mobile phone number of the contact"
                    },
                    "AccountName": {
                        "type": "string",
                        "description": "Name of the company or organization"
                    },
                    "Website": {
                        "type": "string",
                        "description": "Website of the company or organization"
                    }
                },
                "required": ["LastName", "FirstName"]
            }
        }

    def invoke(self, input, trace):
        logger.info("salesforce tool invoked with {}".format(input))
        args = input.get("input", {})
        is_interactive_mode = args.get("is_interactive_mode", False)
        record = {}
        account_name = args.get("AccountName")
        website = args.get("Website")
        account_id = self.get_account_id(account_name)
        if not account_id:
            if account_name and is_interactive_mode:
                return {
                    "output": "More details are necessary to create the Salesforce contact:"
                                + "the account does not exists, should I create it ?"
                }
            response = self.client.create_record(
                "Account",
                {
                    "Name": account_name,
                    "Website": website
                }
            )
            account_id = response.get("id")
        else:
            if len(account_id) == 1:
                # We should handles cases where there is more than one hit. Match on address too ?
                pass
            account_id = account_id[0].get("Id")
        record = add_if_applies(args,
                [
                    "FirstName", "LastName", "Salutation", "Email", "Title",
                    "Department", "AssistantName", "LeadSource",
                    "LeadSource", "Birthdate", "MailingStreet", "MailingCity",
                    "MailingState", "MailingPostalCode", "MailingCountry",
                    "Phone", "MobilePhone"
                ]
                ,record
        )
        if account_id:
            record["AccountId"] = account_id
        try:
            response = self.client.create_record("Contact", record)
            logger.info("response to contact creationg: {}".format(response))
        except Exception as error:
            logger.error("There was an error '{}' while creating the contact".format(error))
            return {
                "output": "There was a problem while creating the contact: {}".format(error)
            }
        output = 'A contact was created with the following data: {}'.format(record)
        logger.info("salesforce tool output: {}".format(output))
        return {
            "output": output
        }
    
    def get_account_id(self, account_name):
        if not account_name:
            return
        logger.info("Searching account id for '{}'".format(account_name))
        query = "SELECT name,id from Account WHERE name = '{}'".format(account_name)
        results = self.client.make_api_call('/queryAll/', {'q': query})
        return results.get("records", [])

def add_if_applies(source, keys, destination):
    for key in keys:
        value = source.get(key)
        if value:
            destination[key] = value
    return destination
