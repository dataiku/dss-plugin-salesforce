import json
import logging
from typing import Any, Dict, List, Optional

from dataiku.llm.python import BaseLLM

from salesforce import SalesforceClient

AGENTFORCE_API_BASE = "https://api.salesforce.com/einstein/ai-agent/v1"

logger = logging.getLogger("SalesforceAgentforceAgent")


class SalesforceAgentforceAgent(BaseLLM):
    """Bridge between Dataiku Agent Hub and Salesforce Agentforce."""

    def __init__(self):
        self.config: Dict[str, Any] = {}
        self.client: Optional[SalesforceClient] = None

    def set_config(self, config, plugin_config):
        # Force OAuth because Agentforce endpoints require a bearer token
        self.config = dict(config or {})
        self.config.setdefault("auth_type", "oauth")
        self.client = SalesforceClient(self.config)
        logger.info(
            f"Configured Agentforce client (auth_type={self.config.get('auth_type')}, agent_id={self.config.get('agent_id')})"
        )

    def process(self, query, settings, trace) -> Dict[str, str]:
        """
        Synchronous entry point to call Agentforce and return a combined reply.
        """
        if not self.client:
            raise ValueError("Salesforce client is not initialized")

        agent_id = self.config.get("agent_id", "").strip()
        if not agent_id:
            raise ValueError("Agentforce Agent ID is required")

        user_message = self._extract_latest_user_message(query.get("messages", []))
        if not user_message:
            return {"text": "No user message found to send to Agentforce."}

        conversation_id = query.get("context", {}).get("conversationId")
        external_session_key = conversation_id or ""

        trace.span["name"] = "SALESFORCE_AGENTFORCE_CHAT"
        trace.inputs["agent_id"] = agent_id
        trace.inputs["user_message"] = user_message
        trace.inputs["external_session_key"] = external_session_key
        logger.info(
            f"Processing Agentforce request (agent_id={agent_id}, convo_id={conversation_id}, message_len={len(user_message)})"
        )

        session_response = self._start_session(agent_id, external_session_key)
        reply_chunks: List[str] = []
        reply_chunks.extend(self._extract_text_messages(session_response))

        session_id = session_response.get("sessionId")
        if not session_id:
            logger.error(f"No sessionId in Agentforce session response: {session_response}")
            raise ValueError("Agentforce sessionId is missing from the response")
        logger.info(f"Agentforce session started with id {session_id}")

        message_response = self._send_message(session_id, user_message)

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

    def _send_message(self, session_id: str, text: str) -> Dict[str, Any]:
        payload = {"message": {"sequenceId": 1, "type": "Text", "text": text}}
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
