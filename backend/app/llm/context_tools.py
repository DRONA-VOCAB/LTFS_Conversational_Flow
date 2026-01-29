"""
Context-catching tools for the LLM: the model can call these to fetch
transcript examples or session summary during a turn (context engineering).
"""

import json
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Lazy import to avoid circular import and to keep transcript_retrieval optional
_transcript_retrieval = None

def _get_transcript_retrieval():
    global _transcript_retrieval
    if _transcript_retrieval is None:
        from services.transcript_retrieval import get_examples_for_turn
        _transcript_retrieval = get_examples_for_turn
    return _transcript_retrieval


# -------- Tool declarations -------------

GET_TRANSCRIPT_EXAMPLES_DECLARATION = {
    "name": "get_transcript_examples",
    "description": (
        "Retrieve relevant call transcript examples from the knowledge base. "
        "Use this when you need more context on how to respond (e.g. similar customer phrases, "
        "wrong person handling, payment collection, summary style). "
        "phase: identity | loan | payment | summary | closing | generic. "
        "query: the customer's last message or a short search phrase. "
        "max_results: number of examples to return (1-5)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "phase": {
                "type": "string",
                "description": "Conversation phase: identity, loan, payment, summary, closing, or generic",
                "enum": ["identity", "loan", "payment", "summary", "closing", "generic"],
            },
            "query": {
                "type": "string",
                "description": "Customer message or search phrase to find relevant examples",
            },
            "max_results": {
                "type": "integer",
                "description": "Number of examples to return (1-5)",
                "default": 3,
            },
        },
        "required": ["phase", "query"],
    },
}

GET_SESSION_SUMMARY_DECLARATION = {
    "name": "get_session_summary",
    "description": (
        "Get a compact summary of the current conversation session: what has been "
        "collected so far (identity, loan, payment details) and what is still missing. "
        "Use this when you need to double-check session state before responding."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}


def get_tool_declarations() -> List[Dict[str, Any]]:
    """Return all context-tool declarations for the model."""
    return [
        GET_TRANSCRIPT_EXAMPLES_DECLARATION,
        GET_SESSION_SUMMARY_DECLARATION,
    ]


def execute_context_tool(
    name: str,
    args: Dict[str, Any],
    session: Dict[str, Any],
    user_input: str,
    conversation_stage: str,
) -> Dict[str, Any]:
    """
    Execute a context tool by name and return a result dict (will be sent back to the model).
    """
    if name == "get_transcript_examples":
        phase = (args.get("phase") or "generic").lower()
        query = args.get("query") or user_input or ""
        max_results = min(5, max(1, int(args.get("max_results", 3))))
        try:
            get_examples = _get_transcript_retrieval()
            examples = get_examples(session=session, user_input=query, phase=phase, k=max_results)
            return {
                "count": len(examples),
                "examples": [
                    {"id": ex.id, "sheet": ex.sheet, "text": ex.text[:800]}
                    for ex in examples
                ],
            }
        except Exception as e:
            logger.warning("get_transcript_examples failed: %s", e)
            return {"error": str(e), "count": 0, "examples": []}

    if name == "get_session_summary":
        summary = {
            "identity_confirmed": session.get("identity_confirmed"),
            "loan_taken": session.get("loan_taken"),
            "last_month_payment": session.get("last_month_payment"),
            "payee": session.get("payee"),
            "payment_date": session.get("payment_date"),
            "payment_mode": session.get("payment_mode"),
            "payment_reason": session.get("payment_reason"),
            "payment_amount": session.get("payment_amount"),
            "conversation_stage": conversation_stage,
            "last_bot_response": (session.get("last_bot_response") or "")[:200],
        }
        return {"session": summary}

    return {"error": f"Unknown tool: {name}"}
