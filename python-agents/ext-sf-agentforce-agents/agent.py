import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import dataiku
from dataiku.core.sql import SQLExecutor2
from dataiku.llm.python import BaseLLM

from salesforce import SalesforceClient

AGENTFORCE_API_BASE = "https://api.salesforce.com/einstein/ai-agent/v1"
DEFAULT_SESSION_DATASET = "agentforce_session_state_ds"

logger = logging.getLogger("SalesforceAgentforceAgent")


class SalesforceAgentforceAgent(BaseLLM):
    """Bridge between Dataiku Agent Hub and Salesforce Agentforce."""

    def __init__(self):
        self.config: Dict[str, Any] = {}
        self.client: Optional[SalesforceClient] = None
        self.physical_table_name: Optional[str] = None
        self.session_record: Dict[str, Any] = {}
        self.executor: Optional[SQLExecutor2] = None

    def set_config(self, config, plugin_config):
        # Force OAuth because Agentforce endpoints require a bearer token
        self.config = dict(config or {})
         self.config.setdefault("auth_type", "oauth")
        self.client = SalesforceClient(self.config)
        conn_name = self.config.get("session_connection", "")
        if conn_name:
            self.physical_table_name = self._get_underlying_table_name(conn_name)
            self.executor = SQLExecutor2(dataset=DEFAULT_SESSION_DATASET)
        logger.info(f"Configured Agentforce client (agent_id={self.config.get('agent_id')})")

    def process(self, query, settings, trace) -> Dict[str, str]:
        """
        Synchronous entry point to call Agentforce and return a combined reply.
        """
        if not self.client:
            raise ValueError("Salesforce client is not initialized")

        agent_id = self.config.get("agent_id", "").strip()
        if not self.physical_table_name:
            raise ValueError("Dataset for session storage could not be accessed or created.")

        user_message = self._extract_latest_user_message(query.get("messages", []))
        if not user_message:
            return {"text": "No user message found to send to Agentforce."}

        dku_conversation_id = query.get("context", {}).get("conversationId")
        if not dku_conversation_id:
            logger.info("No conversation id exist in the input, creating one")
            dku_conversation_id = str(uuid.uuid4())
        
        self.session_record = {
            "dku_conversation_id": dku_conversation_id,
            "af_agent_id": agent_id
        }
        
        external_session_key = dku_conversation_id

        trace.span["name"] = "SALESFORCE_AGENTFORCE_CHAT"
        trace.inputs["agent_id"] = agent_id
        trace.inputs["user_message"] = user_message
        trace.inputs["external_session_key"] = external_session_key
        logger.info(
            f"Processing Agentforce request (agent_id={agent_id}, dku_conversation_id={dku_conversation_id})"
        )

        reply_chunks: List[str] = []
        session_id: Optional[str] = None

        session_id, sequence_no = self._get_existing_session(dku_conversation_id, agent_id)

        if not session_id:
            session_response = self._start_session(agent_id, external_session_key)
            #reply_chunks.extend(self._extract_text_messages(session_response))
            session_id = session_response.get("sessionId")
            
            if not session_id:
                logger.error(f"No sessionId in Agentforce session response: {session_response}")
                raise ValueError("Agentforce sessionId is missing from the response")

            logger.info(f"Agentforce new session started with id {session_id}")
            
        else:
            sequence_no += 1
            logger.info(f"Using existing Agentforce session with id {session_id} and incremented sequence_no {sequence_no}")

        self.session_record.update({
                "af_agent_session_id": session_id,
                "sequence_no": sequence_no
                })
        
        log_session_info = self._insert_or_update_session_record()
        if not log_session_info:
            raise ValueError("Failed to log session information to dataset.")

        message_response = self._send_message(session_id, user_message, sequence_no)

        reply_chunks.extend(self._extract_text_messages(message_response))

        final_text = "\n".join(reply_chunks) if reply_chunks else ""
        trace.outputs["output"] = final_text
        logger.info(f"Agentforce reply length: {len(final_text)} chars")
        return {"text": final_text}

    def _start_session(
        self, agent_id: str, external_session_key: Optional[str]
    ) -> Dict[str, Any]:
        payload = {
            "externalSessionKey": external_session_key or "",
            "instanceConfig": {"endpoint": self.client.API_BASE_URL},
            "streamingCapabilities": {"chunkTypes": ["Text"]},
            "bypassUser": False,
        }
        url = f"{AGENTFORCE_API_BASE}/agents/{agent_id}/sessions"
        logger.info(f"Starting Agentforce session at {url}")
        response = self.client.make_api_call(
            url, method="post", data=json.dumps(payload)
        )
        logger.info(f"Agentforce session response keys: {list(response.keys())}")
        return response

    def _send_message(self, session_id: str, text: str, sequence_id: int) -> Dict[str, Any]:
        payload = {
            "message": {"sequenceId": sequence_id, "type": "Text", "text": text}
        }
        url = f"{AGENTFORCE_API_BASE}/sessions/{session_id}/messages"
        logger.info(f"Sending message to Agentforce session {session_id}")
        response = self.client.make_api_call(
            url, method="post", data=json.dumps(payload)
        )
        logger.info(f"Agentforce message response keys: {list(response.keys())}")
        return response

    def _extract_latest_user_message(
        self, messages: List[Dict[str, Any]]
    ) -> Optional[str]:
        for msg in reversed(messages):
            if msg.get("role") == "user" and msg.get("content"):
                logger.debug(
                    f"Using latest user message of length {len(str(msg.get('content')))}"
                )
                return str(msg.get("content"))
        return None

    def _extract_text_messages(self, agent_response: Dict[str, Any]) -> List[str]:
        texts: List[str] = []
        for msg in agent_response.get("messages", []):
            if not isinstance(msg, dict):
                continue
            message_text = msg.get("message") or msg.get("text")
            if message_text:
                texts.append(str(message_text))
        return texts

    def _get_underlying_table_name(self, conn_name: str) -> Optional[str]:
        if self.physical_table_name:
            return self.physical_table_name
        try:
            dku_client = dataiku.api_client()
            project = dku_client.get_default_project()
            builder = project.new_managed_dataset(DEFAULT_SESSION_DATASET)

            ds_exist = builder.already_exists()
            if not ds_exist:
                logger.info(f"DS {DEFAULT_SESSION_DATASET} doesn't exist. Creating one. ")

                builder.with_store_into(conn_name)
                dataset = builder.create()
                ds_settings = dataset.get_settings()
                ds_settings.add_raw_schema_column({'name': 'dku_conversation_id', 'type': 'string'})
                ds_settings.add_raw_schema_column({'name': 'af_agent_id', 'type': 'string'})
                ds_settings.add_raw_schema_column({'name': 'af_agent_session_id', 'type': 'string'})
                ds_settings.add_raw_schema_column({'name': 'session_start', 'type': 'date'})
                ds_settings.add_raw_schema_column({'name': 'session_end', 'type': 'date'})
                ds_settings.add_raw_schema_column({'name': 'sequence_no', 'type': 'bigint'})
                ds_settings.add_raw_schema_column({'name': 'last_updated_ts', 'type': 'date'})
                ds_settings.save()

                dss_dataset_obj = dataiku.Dataset(DEFAULT_SESSION_DATASET)
                with dss_dataset_obj.get_writer() as writer:
                    pass
                
                logger.info(f"DS {DEFAULT_SESSION_DATASET} created successfully. ")
                physical_table_name = dss_dataset_obj.get_location_info()["info"]["table"]

                executor = SQLExecutor2(dataset=DEFAULT_SESSION_DATASET)
                pk_sql = f"""
                            ALTER TABLE "{physical_table_name}" 
                            ADD PRIMARY KEY (dku_conversation_id, af_agent_id, af_agent_session_id)
                        """
                executor.query_to_df(pk_sql,post_queries=["COMMIT"])
                logger.info(f"Primary key added to table {physical_table_name} successfully. ")

                return physical_table_name
            
            dss_dataset_obj = dataiku.Dataset(DEFAULT_SESSION_DATASET)
            physical_table_name = dss_dataset_obj.get_location_info()["info"]["table"]
            return physical_table_name
        except Exception as e:
            logger.error(f"Failed to get underlying table name: {e}")
            return None

    def _get_existing_session(self, dku_conversation_id: str, agent_id: str):
        try:
            if not self.executor:
                self.executor = SQLExecutor2(dataset=DEFAULT_SESSION_DATASET)
            query = f"SELECT af_agent_session_id, sequence_no FROM \"{self.physical_table_name}\" WHERE dku_conversation_id = '{dku_conversation_id}' AND af_agent_id = '{agent_id}'"
            df = self.executor.query_to_df(query)
            
            if not df.empty:
                return df.iloc[0]['af_agent_session_id'], int(df.iloc[0]['sequence_no'])
        except Exception as e:
            logger.error(f"Failed to get existing session: {e}")
            raise e
        return None, 1

    def _insert_or_update_session_record(self) -> bool:
        try:
            current_ts = datetime.utcnow().isoformat()
            
            insert_stmt = f"""
            INSERT INTO "{self.physical_table_name}" (
                dku_conversation_id,
                af_agent_id,
                af_agent_session_id,
                session_start,
                session_end,
                sequence_no,
                last_updated_ts
            ) VALUES (
                '{self.session_record.get("dku_conversation_id")}',
                '{self.session_record.get("af_agent_id")}',
                '{self.session_record.get("af_agent_session_id")}',
                '{current_ts}',
                NULL,
                {self.session_record.get("sequence_no")},
                '{current_ts}'
            )
            ON CONFLICT (dku_conversation_id, af_agent_id, af_agent_session_id)
            DO UPDATE SET
                sequence_no = EXCLUDED.sequence_no,
                last_updated_ts = EXCLUDED.last_updated_ts
            """
            
            if not self.executor:
                self.executor = SQLExecutor2(dataset=DEFAULT_SESSION_DATASET)
            self.executor.query_to_df(insert_stmt, post_queries=["COMMIT"])
            logger.info(f"Session record updated for {self.session_record.get('dku_conversation_id')}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to insert/update session record: {e}")
            return False
        
        
       
