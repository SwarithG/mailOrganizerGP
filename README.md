# Gmail Archives Cleaner

A powerful Streamlit application that intelligently clusters, summarizes, and helps organize your Gmail inbox. Uses Claude AI to intelligently analyze email groups and safely manage message deletion.

## Overview

Gmail Archives Cleaner is a Streamlit prototype designed to help you:
- **Scan & List**: Query and fetch messages from your Gmail inbox
- **Cluster**: Group similar emails together using semantic embeddings
- **Summarize**: Use Claude AI to generate labels and summaries for email clusters
- **Preview**: Extract and view plaintext content from messages
- **Score**: Get AI-powered safety scores before deleting emails
- **Archive/Delete**: Batch manage messages with built-in retry logic

## Features

### Core Functionality
- **Gmail Integration**: Full OAuth2 authentication with Gmail API for secure access
- **Smart Clustering**: Agglomerative clustering using sentence-transformers for semantic similarity
- **AI Summarization**: Claude API integration to summarize email groups and generate descriptive labels
- **Safe Deletion**: AI-powered safety scoring for individual messages before deletion
- **Batch Operations**: Efficient bulk deletion with retry logic and rate limiting
- **Message Preview**: Extract and display plaintext content from emails with MIME parsing
- **Session State Management**: Persistent state across Streamlit reruns

### Technical Highlights
- Email embedding using `all-MiniLM-L6-v2` model for fast, accurate similarity matching
- Customizable clustering parameters (distance threshold)
- Alternative KMeans clustering with silhouette score optimization
- Graceful error handling with exponential backoff retry logic
- Chunked batch processing to avoid API rate limits

## Quick Start

### Prerequisites
- Python 3.8+
- Google Account with Gmail enabled
- Anthropic API key (for Claude access)

### Installation

1. **Clone/Open the Project**
   ```bash
   cd c:\Projects\Python\mailOrganizerGP
   ```

2. **Create Virtual Environment**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Google OAuth**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create an OAuth 2.0 Desktop Application
   - Download credentials as `credentials.json` and place in project root
   - Ensure Gmail API is enabled

5. **Set Up Environment Variables**
   Create a `.env` file in the project root:
   ```
   ANTHROPIC_API_KEY=sk-<your-anthropic-api-key>
   ```
   ⚠️ Never commit `.env` or `credentials.json` to version control

6. **Run the Application**
   ```bash
   streamlit run streamlit_app.py
   ```
   
   The app will open in your browser. On first run, you'll be prompted for Google OAuth authorization.

## How It Works

### Architecture Flow

```
1. Scan & List
   └─> GmailClient.list_message_ids() → fetch message IDs
   └─> GmailClient.get_message_meta() → get snippets and headers

2. Clustering
   └─> Clusterer.embed_texts() → generate embeddings
   └─> Clusterer.make_clusters() → agglomerative clustering

3. Summarization
   └─> claude_client.summarize_cluster() → AI label + summary

4. Preview & Scoring
   └─> GmailClient.get_message_raw() → fetch raw MIME
   └─> processor.extract_plaintext_from_raw() → extract text
   └─> claude_client.safe_delete_score_for_message() → safety score

5. Deletion
   └─> delete_worker.bulk_delete_with_retry() → batch delete with retries
   └─> GmailClient.batch_delete() → Gmail API delete
```

### Key Components

#### Core Modules

| Module | Purpose |
|--------|---------|
| `streamlit_app.py` | Main Streamlit UI with session management |
| `gmail_client.py` | Gmail API wrapper for authentication and operations |
| `clustering.py` | Embedding and clustering logic using sentence-transformers |
| `claude_client.py` | Claude API integration for summarization and scoring |
| `processor.py` | MIME parsing and plaintext extraction |
| `delete_worker.py` | Batch deletion with retry logic |
| `utils.py` | Helper utilities for chunking and rate limiting |

#### `streamlit_app.py`
Main UI with two columns:
- **Left**: Query controls, message fetching, clustering parameters
- **Right**: Results display, cluster summaries, message previews, batch operations

Key session state variables:
- `msgs_meta`: Dictionary of message ID → {snippet, subject, from}
- `clusters`: Dictionary of cluster ID → list of message indices
- `cluster_labels`: Dictionary of cluster ID → {label, summary}

#### `gmail_client.py`
**Class: `GmailClient`**

Key methods:
- `list_message_ids(query, max_results)` - Fetch message IDs with pagination
- `get_message_meta(message_id)` - Get snippet and headers
- `get_message_raw(message_id)` - Fetch raw MIME for plaintext extraction
- `batch_delete(message_ids)` - Delete messages via batchDelete endpoint
- `archive_messages(message_ids)` - Move messages to archive

Features:
- OAuth2 flow with local server
- Token caching in `token.pickle`
- Automatic credential refresh

#### `clustering.py`
**Class: `Clusterer`**

Key methods:
- `embed_texts(texts)` - Generate embeddings using `all-MiniLM-L6-v2`
- `make_clusters(texts, distance_threshold)` - Agglomerative clustering with cosine similarity
- `make_kmeans_clusters(texts, k_min, k_max)` - KMeans with silhouette optimization

Parameters:
- `distance_threshold` (default: 0.25) - Lower = more clusters
- `model_name` - Sentence-transformer model (default: `all-MiniLM-L6-v2`)

#### `claude_client.py`
Uses Claude 3.5 Sonnet model for:

**`summarize_cluster(cluster_texts, max_chars)`**
- Generates a 3-word-or-less label
- Produces 2-3 sentence summary
- Returns JSON: `{"label": "...", "summary": "..."}`

**`safe_delete_score_for_message(msg_text)`**
- Scores message safety for deletion (0.0 to 1.0)
- Provides reasoning
- Returns JSON: `{"score": float, "reason": "..."}`

#### `processor.py`
**Function: `extract_plaintext_from_raw(raw_b64)`**

Features:
- Decodes base64url MIME
- Extracts text/plain parts
- Converts text/html to plaintext (crude)
- Handles charset decoding
- Returns cleaned text

#### `delete_worker.py`
**Function: `bulk_delete_with_retry(gmail_client, message_ids, batch_size, pause)`**

Features:
- Chunks deletes into batches
- Implements exponential backoff retry (up to 3 attempts)
- Configurable pause between batches to avoid API throttling
- Graceful error reporting

#### `utils.py`

Utility functions:
- `chunks(iterable, size)` - Generator for chunking
- `rate_limited_executor(items, fn, batch_size, delay_seconds)` - Apply function with rate limiting

## Configuration

### Environment Variables

```env
# Required
ANTHROPIC_API_KEY=sk-...

# Optional
# Add other service secrets as needed
```

### Clustering Parameters

In `clustering.py`, adjust:
```python
MODEL_NAME = "all-MiniLM-L6-v2"  # Embedding model
```

In `streamlit_app.py`, UI controls for:
- `distance_threshold` (0.0 - 1.0) - Clustering sensitivity
- `Max messages to fetch` (100 - 50000) - Query limit

### API Limits

- Gmail API: 1,000,000 requests/day (shared quota)
- Claude API: Check Anthropic dashboard for rate limits
- Batch size: Default 100 messages per delete request

## File Structure

```
mailOrganizerGP/
├── README.md                 # This file
├── streamlit_app.py         # Main Streamlit UI
├── gmail_client.py          # Gmail API wrapper
├── clustering.py            # Embedding and clustering
├── claude_client.py         # Claude AI integration
├── processor.py             # MIME/plaintext extraction
├── delete_worker.py         # Batch deletion worker
├── utils.py                 # Helper utilities
├── requirements.txt         # Python dependencies
├── credentials.json         # Google OAuth (gitignored)
├── token.pickle             # OAuth token cache (gitignored)
├── .env                     # Environment variables (gitignored)
└── __pycache__/            # Python cache

```

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| streamlit | ≥1.25.0 | Web UI framework |
| google-api-python-client | ≥2.90.0 | Gmail API client |
| google-auth-oauthlib | ≥1.0.0 | Google OAuth2 flow |
| google-auth-httplib2 | ≥0.1.0 | HTTP transport for auth |
| anthropic | ≥0.22.0 | Claude API client |
| sentence-transformers | ≥2.2.2 | Text embeddings |
| scikit-learn | ≥1.2.2 | Clustering algorithms |
| pandas | ≥2.0.0 | Data manipulation |
| numpy | ≥1.25.0 | Numerical operations |
| tqdm | ≥4.65.0 | Progress bars |
| python-dotenv | ≥1.0.0 | Environment variable loading |

## Usage Guide

### Step 1: Initial Setup
1. Start the app: `streamlit run streamlit_app.py`
2. First run will prompt browser OAuth with Google
3. Grant access to Gmail (app won't modify/delete without explicit action)

### Step 2: Scan Your Inbox
1. Enter Gmail query (e.g., "from:noreply@", "label:Updates", or leave blank for all)
2. Set max messages to fetch (recommend 1000-2000 for first run)
3. Click "Scan Inbox / Archive"
4. Wait for message fetching and metadata extraction

### Step 3: Cluster Emails
1. Adjust distance threshold for sensitivity (lower = more clusters)
2. Select clustering method (Agglomerative recommended)
3. Click "Cluster messages"
4. View cluster summaries and sizes

### Step 4: Preview & Score
1. Expand a cluster to see messages
2. Click "Preview message" to see full plaintext
3. Click "Score for deletion" to get AI safety assessment
4. Review score and reason

### Step 5: Delete/Archive
1. Select messages to delete (checkbox)
2. Click "Delete selected" (with 3-click confirmation)
3. Or use cluster-level "Archive cluster" button
4. Monitor progress and retry status

## Troubleshooting

### Google OAuth Issues
- **Error**: "credentials.json not found"
  - Download OAuth credentials from Google Cloud Console
  - Save as `credentials.json` in project root
  
- **Error**: "Failed to start local server"
  - Check if port 8080 is available
  - Try a different port in `gmail_client.py`

### Claude API Issues
- **Error**: "ANTHROPIC_API_KEY not set"
  - Create `.env` file with `ANTHROPIC_API_KEY=sk-...`
  - Verify API key is valid and has quota

- **Error**: "Overloaded" from Claude API
  - Wait a moment and retry
  - Consider reducing batch size
  - Check Anthropic status page

### Gmail API Issues
- **Error**: "Service not enabled"
  - Enable Gmail API in Google Cloud Console
  - Wait 1-2 minutes for changes to propagate

- **Error**: "Quota exceeded"
  - Daily limit is 1M requests
  - Increase pause between batches in settings
  - Try again tomorrow

### Performance Issues
- **Slow clustering**: Reduce max messages or increase distance_threshold
- **Memory issues**: Process in smaller batches, close other apps
- **Embedding timeout**: Check internet connection, model may be large on first load

## Security & Privacy

### Best Practices
- ⚠️ **Never commit** `credentials.json`, `.env`, or `token.pickle` to version control
- Create `.gitignore` with these entries:
  ```
  credentials.json
  token.pickle
  .env
  __pycache__/
  *.pyc
  .streamlit/secrets.toml
  ```
- Store API keys in environment variables, never in code
- Review cluster summaries before batch deletion
- Use "Score for deletion" on important messages

### Permissions
- **Gmail API scope**: `gmail.modify`
  - Allows: List, read, delete, archive operations
  - Does NOT allow: Send emails, access account password
- **Claude API**: Text-only, no account data exposed beyond email content
- Messages are processed locally first, sent to Claude only for summarization/scoring

## Advanced Usage

### Custom Clustering
Modify `distance_threshold` in code:
```python
# Lower = more clusters (fine-grained)
clusters = clusterer.make_clusters(texts, distance_threshold=0.15)

# Higher = fewer clusters (coarse-grained)
clusters = clusterer.make_clusters(texts, distance_threshold=0.40)
```

### Using KMeans Instead
Switch to KMeans clustering with silhouette optimization:
```python
clusters = clusterer.make_kmeans_clusters(texts, k_min=3, k_max=30)
```

### Batch Operations
Rate-limited batch processing:
```python
from utils import rate_limited_executor

results = rate_limited_executor(
    items=message_ids,
    fn=lambda batch: gmail_client.batch_delete(batch),
    batch_size=100,
    delay_seconds=0.5
)
```

### Custom Gmail Queries
Examples of Gmail search operators:
- `from:sender@example.com` - From specific sender
- `label:Promotions` - In Promotions label
- `before:2024/01/01` - Before date
- `has:attachment` - Has attachments
- `subject:unsubscribe` - Subject contains text
- Combine with AND/OR: `label:Updates AND from:noreply`

## Development Notes

### Embedding Model
- Current: `all-MiniLM-L6-v2` (22M parameters)
- Fast inference, good quality for emails
- ~400MB disk space with Hugging Face cache
- Alternatives: `all-mpnet-base-v2` (larger but better), `paraphrase-MiniLM-L6-v2`

### Clustering Algorithm
- **Agglomerative**: Hierarchical, deterministic, good for varied cluster sizes
- **KMeans**: Faster, requires choosing K, assumes spherical clusters
- Current default: Agglomerative with cosine similarity

### Claude Model
- Current: `claude-3-5-sonnet-20250219`
- Replaced: claude-2.1
- Cost-effective, good for summarization and scoring tasks

### Rate Limiting
- Gmail API: No explicit limit, but batching recommended
- Claude API: Token-based, limits vary by plan
- Default pause between batches: 0.4-0.5 seconds

## Limitations & Known Issues

1. **First embedding load**: Sentence-transformers model downloads on first use (~400MB)
2. **Large batches**: Processing 10k+ messages may be slow; use clustering threshold
3. **Duplicate detection**: No built-in deduplication; clustering may split duplicates
4. **Archive operation**: Currently implemented as archive, not permanent delete
5. **Error handling**: Retry logic is basic; critical errors may need manual recovery
6. **HTML emails**: Crude regex-based HTML stripping; complex HTML may not parse perfectly

## Future Enhancements

- [ ] Persistent database for message metadata
- [ ] Advanced duplicate detection
- [ ] Custom clustering algorithms (DBSCAN, hierarchical merge)
- [ ] Message attachment analysis
- [ ] Label/tag suggestions
- [ ] Scheduled/automated cleanup jobs
- [ ] Web UI deployment (Streamlit Cloud)
- [ ] Performance metrics and analytics
- [ ] Support for multiple Google accounts

## Contributing

To extend this project:

1. **Add new clustering methods**: Extend `Clusterer` class in `clustering.py`
2. **Add new AI operations**: Add functions to `claude_client.py`
3. **Add UI features**: Modify `streamlit_app.py` sections
4. **Add new email operations**: Extend `GmailClient` class in `gmail_client.py`

## License

This project is provided as-is for personal use. Ensure compliance with:
- [Gmail API Terms of Service](https://developers.google.com/gmail/api/guides)
- [Anthropic Terms of Service](https://www.anthropic.com/legal)

## Support & Issues

For issues, check:
1. API credentials and scopes
2. Python version compatibility (3.8+)
3. Network connectivity
4. API quota/rate limits
5. Log output in terminal for detailed errors

## Disclaimer

⚠️ **This tool performs destructive operations** (permanent email deletion). Always:
- Test with small batches first
- Review cluster summaries before bulk deletion
- Use "Score for deletion" on important messages
- Keep backups of important emails
- Understand Gmail's undo/restore limitations

The authors are not responsible for accidentally deleted emails.
