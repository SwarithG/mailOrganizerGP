# gmail_client.py
import base64
import os
import pickle
from typing import List, Dict, Any

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify'
]
TOKEN_PICKLE = "token.pickle"
CREDENTIALS_FILE = "credentials.json"


class GmailClient:
    def __init__(self):
        creds = None
        if os.path.exists(TOKEN_PICKLE):
            with open(TOKEN_PICKLE, "rb") as f:
                creds = pickle.load(f)
        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
            with open(TOKEN_PICKLE, "wb") as f:
                pickle.dump(creds, f)
        self.service = build("gmail", "v1", credentials=creds)

    def list_message_ids(self, query: str = "", max_results: int = 5000) -> List[str]:
        """Return list of message ids matching query (empty query returns all)."""
        msgs = []
        try:
            response = self.service.users().messages().list(userId='me', q=query, maxResults=500).execute()
            while response:
                if "messages" in response:
                    msgs.extend([m["id"] for m in response["messages"]])
                if "nextPageToken" in response and len(msgs) < max_results:
                    response = self.service.users().messages().list(userId='me', q=query, pageToken=response["nextPageToken"], maxResults=500).execute()
                else:
                    break
                if len(msgs) >= max_results:
                    break
        except HttpError as error:
            print("Gmail list error:", error)
        return msgs[:max_results]

    def get_message_meta(self, message_id: str) -> Dict[str, Any]:
        """Get metadata fields (snippet, headers) without fetching full raw body by default."""
        msg = self.service.users().messages().get(userId='me', id=message_id, format='metadata', metadataHeaders=['From', 'To', 'Subject', 'Date']).execute()
        return msg

    def get_message_raw(self, message_id: str) -> Dict[str, Any]:
        """Get full raw message (MIME) for processing."""
        return self.service.users().messages().get(userId='me', id=message_id, format='raw').execute()

    def batch_delete(self, message_ids: List[str]) -> Dict[str, Any]:
        """Batch delete messages (permanently remove)."""
        if not message_ids:
            return {"status": "no-op"}
        body = {"ids": message_ids}
        return self.service.users().messages().batchDelete(userId="me", body=body).execute()

    def modify_labels(self, message_id: str, labels_to_add=None, labels_to_remove=None):
        body = {}
        if labels_to_add:
            body["addLabelIds"] = labels_to_add
        if labels_to_remove:
            body["removeLabelIds"] = labels_to_remove
        return self.service.users().messages().modify(userId="me", id=message_id, body=body).execute()

    def move_to_trash(self, message_ids: List[str]):
        for mid in message_ids:
            try:
                self.service.users().messages().modify(
                    userId='me',
                    id=mid,
                    body={"addLabelIds": ["TRASH"], "removeLabelIds": []}
                ).execute()
            except Exception as e:
                print(f"Failed to delete {mid}: {e}")