# streamlit_app.py
import streamlit as st
from gmail_client import GmailClient
from processor import extract_plaintext_from_raw
from clustering import Clusterer
from claude_client import summarize_cluster, safe_delete_score_for_message
from delete_worker import bulk_delete_with_retry
from utils import chunks
import pandas as pd
import threading

st.set_page_config(layout="wide", page_title="Gmail Archives Cleaner")

@st.cache_resource
def get_clients():
    gmail = GmailClient()
    clusterer = Clusterer()
    return gmail, clusterer

gmail, clusterer = get_clients()

st.title("Gmail Archives Cleaner — Streamlit Prototype")

if "msgs_meta" not in st.session_state:
    st.session_state["msgs_meta"] = {}
if "clusters" not in st.session_state:
    st.session_state["clusters"] = {}
if "cluster_labels" not in st.session_state:
    st.session_state["cluster_labels"] = {}

col1, col2 = st.columns([1, 3])
with col1:
    q = st.text_input("Gmail query (leave blank for all):", value="")
    max_fetch = st.number_input("Max messages to fetch", min_value=100, max_value=50000, value=2000, step=100)
    if st.button("Scan Inbox / Archive"):
        with st.spinner("Listing message IDs..."):
            ids = gmail.list_message_ids(query=q, max_results=max_fetch)
            st.session_state["message_ids"] = ids
            st.success(f"Found {len(ids)} messages.")
        # Fetch metadata (snippets)
        snippets = []
        for i, mid in enumerate(st.session_state["message_ids"]):
            if i >= 2000:
                break
            meta = gmail.get_message_meta(mid)
            snippet = meta.get("snippet", "")
            headers = {h["name"]: h["value"] for h in meta.get("payload", {}).get("headers", [])}
            st.session_state["msgs_meta"][mid] = {
                "snippet": snippet,
                "subject": headers.get("Subject", ""),
                "from": headers.get("From", ""),
                "date": headers.get("Date", ""),
            }
        st.info(f"Loaded metadata for {len(st.session_state['msgs_meta'])} messages. Now clustering...")

        # Prepare small sample texts for clustering: use snippet + subject
        texts = []
        mids = []
        for mid, d in st.session_state["msgs_meta"].items():
            txt = f"Subject: {d.get('subject','')}\n{d.get('snippet','')}"
            texts.append(txt)
            mids.append(mid)
        # cluster
        clusters = clusterer.hybrid_clusters(texts)
        st.session_state["clusters"] = {"mapping": clusters, "texts": texts, "mids": mids}
        st.success(f"Formed {len(clusters)} clusters.")

with col2:
    if "clusters" in st.session_state and st.session_state["clusters"]:
        st.header("Clusters")
        mapping = st.session_state["clusters"]["mapping"]
        texts = st.session_state["clusters"]["texts"]
        mids = st.session_state["clusters"]["mids"]
        cluster_summaries = {}
        for cid, indices in sorted(mapping.items(), key=lambda x: -len(x[1])):
            label = st.session_state["cluster_labels"].get(str(cid))
            if not label:
                sample_texts = [texts[i] for i in indices[:6]]
                # call claude to label/summarize
                with st.spinner(f"Labeling cluster {cid}..."):
                    try:
                        out = summarize_cluster(sample_texts)
                    except Exception as e:
                        out = f'{{"label":"Cluster {cid}","summary":"Could not call Claude: {e}"}}'
                # Claude returns text; try to parse minimal JSON heuristically
                import json, re
                m = re.search(r'\{.*\}', out, re.S)
                if m:
                    try:
                        j = json.loads(m.group(0))
                        label = j.get("label", f"Cluster {cid}")
                        summ = j.get("summary", "")
                    except Exception:
                        label = f"Cluster {cid}"
                        summ = out
                else:
                    label = f"Cluster {cid}"
                    summ = out
                st.session_state["cluster_labels"][str(cid)] = {"label": label, "summary": summ}
            cluster_summaries[cid] = st.session_state["cluster_labels"][str(cid)]

        # Display cluster cards
        for cid, indices in sorted(mapping.items(), key=lambda x: -len(x[1])):
            meta = cluster_summaries[cid]
            with st.expander(f"{meta['label']} — {len(indices)} emails"):
                st.write(meta['summary'])
                cols = st.columns([3, 1, 1])
                if cols[2].button("Delete entire group", key=f"del_group_{cid}"):
                    # confirm
                    if st.checkbox(f"Are you sure you want to DELETE all {len(indices)} messages in this group? This is irreversible."):
                        ids_to_delete = [mids[i] for i in indices]
                        bulk_delete_with_retry(gmail, ids_to_delete)
                        st.success(f"Deleted {len(ids_to_delete)} messages.")
                if cols[1].button("Archive entire group", key=f"archive_group_{cid}"):
                    # naive: remove INBOX label
                    for i in indices:
                        mid = mids[i]
                        try:
                            gmail.modify_labels(mid, labels_to_add=[], labels_to_remove=["INBOX"])
                        except Exception as e:
                            pass
                    st.success("Archived group (best-effort).")

                # sample preview
                sample_idx = indices[:10]
                rows = []
                for i in sample_idx:
                    mid = mids[i]
                    mmeta = st.session_state["msgs_meta"].get(mid, {})
                    rows.append({
                        "message_id": mid,
                        "from": mmeta.get("from", "")[:80],
                        "subject": mmeta.get("subject", "")[:120],
                        "snippet": mmeta.get("snippet", "")[:180]
                    })
                df = pd.DataFrame(rows)
                sel = st.multiselect("Select emails to preview/delete (select rows below)", options=list(df['message_id']), format_func=lambda x: df[df['message_id']==x]['subject'].values[0])
                if sel:
                    # show full bodies in a modal-like area
                    for mid in sel:
                        raw = gmail.get_message_raw(mid)
                        raw_raw = raw.get("raw", "")
                        text = extract_plaintext_from_raw(raw_raw) if raw_raw else "(no raw body cached)"
                        st.markdown(f"**From:** {st.session_state['msgs_meta'][mid]['from']}  ")
                        st.markdown(f"**Subject:** {st.session_state['msgs_meta'][mid]['subject']}  ")
                        st.text_area("Full email", value=text[:10000], height=300, key=f"email_{mid}")
                        # safe-delete prediction for the single message
                        if st.button(f"Check safe-delete for this email ({mid[:8]})", key=f"score_{mid}"):
                            with st.spinner("Asking Claude..."):
                                out = safe_delete_score_for_message(text)
                                st.write(out)

                    # if st.button("Delete selected emails (permanently)"):
                    #     if st.checkbox("Confirm permanent deletion of selected messages?"):
                    #         ids_to_delete = sel
                    #         bulk_delete_with_retry(gmail, ids_to_delete)
                    #         st.success(f"Deleted {len(ids_to_delete)} messages.")
                    if st.button("Delete selected emails (permanently)"):
                        if st.checkbox("Confirm permanent deletion of selected messages?"):
                            ids_to_delete = sel
                            # safer + works with gmail.modify
                            gmail.move_to_trash(ids_to_delete)
                            st.success(f"Moved {len(ids_to_delete)} messages to Trash.")
    else:
        st.info("Scan your mailbox to see clusters.")
