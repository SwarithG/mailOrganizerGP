# delete_worker.py
from gmail_client import GmailClient
from utils import chunks
import time

def bulk_delete_with_retry(gmail_client: GmailClient, message_ids: list, batch_size: int = 100, pause: float = 0.4):
    """Delete message ids using batchDelete in chunks, with basic retry."""
    for batch in chunks(message_ids, batch_size):
        attempts = 0
        while attempts < 3:
            try:
                gmail_client.batch_delete(batch)
                break
            except Exception as e:
                attempts += 1
                print("Batch delete error, retrying:", e)
                time.sleep(2 ** attempts)
        time.sleep(pause)
