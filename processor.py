# processor.py
from email import message_from_bytes
from email.policy import default
import base64
from typing import Tuple, Optional
import quopri
import re

def extract_plaintext_from_raw(raw_b64: str) -> str:
    """Accepts raw base64url string as returned by Gmail API 'raw' field; returns plaintext."""
    raw_bytes = base64.urlsafe_b64decode(raw_b64.encode("utf-8"))
    msg = message_from_bytes(raw_bytes, policy=default)
    text_parts = []

    def walk_parts(m):
        if m.is_multipart():
            for part in m.iter_parts():
                walk_parts(part)
        else:
            ctype = m.get_content_type()
            disp = m.get_content_disposition()
            if ctype == "text/plain" and disp != "attachment":
                payload = m.get_payload(decode=True)
                if payload:
                    charset = m.get_content_charset() or "utf-8"
                    try:
                        text_parts.append(payload.decode(charset, errors="replace"))
                    except Exception:
                        text_parts.append(payload.decode("utf-8", errors="replace"))
            elif ctype == "text/html":
                payload = m.get_payload(decode=True)
                if payload:
                    charset = m.get_content_charset() or "utf-8"
                    html = payload.decode(charset, errors="replace")
                    # crude html -> text
                    text = re.sub('<[^<]+?>', ' ', html)
                    text_parts.append(text)

    walk_parts(msg)
    joined = "\n".join(text_parts)
    # minimal cleanup
    joined = re.sub(r'\r\n', '\n', joined)
    joined = re.sub(r'\n{2,}', '\n\n', joined)
    return joined.strip()
