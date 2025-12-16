# claude_client.py
import os
from typing import List, Dict, Any
import anthropic
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not API_KEY:
    raise RuntimeError("Set ANTHROPIC_API_KEY environment variable")

client = anthropic.Client(api_key=API_KEY)

SYSTEM_PROMPT = """
You are an assistant that reads short email text and classifies and summarizes them.
Return JSON only when asked.
"""

def summarize_cluster(cluster_texts: List[str], max_chars: int = 1200) -> str:
    """Ask Claude to produce a short summary and a suggested label for a cluster."""
    sample_text = "\n---\n".join(cluster_texts[:6])
    prompt = f"{SYSTEM_PROMPT}\n\nHuman: Given the following emails (separated by '---'), produce a short label (3 words or less) and a 2-3 sentence human readable summary explaining why they were grouped. Output JSON: {{\"label\": \"...\", \"summary\": \"...\"}}.\n\nEmails:\n{sample_text}\n\nAssistant:"
    # resp = client.completions.create(
    #     model="claude-2.1", 
    #     prompt=prompt, 
    #     max_tokens_to_sample=300)
    # return resp.completion.strip()
    response = client.messages.create(
        model="claude-3-7-sonnet-20250219",
        max_tokens=256,
        messages=[
            {"role": "user", "content": f"{prompt}"}
        ]
    )
    return response.content[0].text

def safe_delete_score_for_message(msg_text: str) -> Dict[str, Any]:
    """Ask Claude if this single message is safe to delete. Return {score:0-1, reason:...}"""
    prompt = f"""{SYSTEM_PROMPT}
User: For the following single email text, respond with JSON containing:
- "score": a float from 0.0 to 1.0 showing how safe it is to DELETE this email (1.0 = very safe to delete, 0.0 = definitely do not delete),
- "reason": short explanation (1-2 sentences).
Email:
\"\"\"{msg_text[:3000]}\"\"\"
Assistant:"""
    response = client.messages.create(
        model="claude-3-7-sonnet-20250219",
        max_tokens=512,
        messages=[
            {"role": "user", "content": f"{prompt}"}
        ]
    )
    return response.content[0].text
