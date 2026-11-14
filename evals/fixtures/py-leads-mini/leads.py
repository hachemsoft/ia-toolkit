import logging

logger = logging.getLogger(__name__)

LEADS = {1: {"name": "Alice", "phone": "+33600000001", "status": "to_call"}}


def leads_to_call():
    """Leads still waiting for a call."""
    return [lead_id for lead_id, lead in LEADS.items() if lead["status"] == "to_call"]
