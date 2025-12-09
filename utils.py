# utils.py
import time
from typing import Iterable, List

def chunks(iterable: Iterable, size: int):
    lst = list(iterable)
    for i in range(0, len(lst), size):
        yield lst[i:i+size]

def rate_limited_executor(items: List, fn, batch_size: int = 100, delay_seconds: float = 0.5):
    """Run fn on batch of items, sleeping between batches to avoid quota bursts."""
    results = []
    for batch in chunks(items, batch_size):
        results.append(fn(batch))
        time.sleep(delay_seconds)
    return results
