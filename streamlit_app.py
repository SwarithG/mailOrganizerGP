# streamlit_app.py
import streamlit as st
from gmail_client import GmailClient
from processor import extract_plaintext_from_raw
from clustering import Clusterer
from claude_client import summarize_cluster, safe_delete_score_for_message
from utils import chunks
import pandas as pd
import ast
import json

st.set_page_config(layout="wide", page_title="Email Organizer")

@st.cache_resource
def get_clients():
    gmail = GmailClient()
    clusterer = Clusterer()
    return gmail, clusterer

gmail, clusterer = get_clients()

st.title("Email Organizer — Prototype")

def remove_mids_from_clusters(deleted_mids):
    clusters = st.session_state.get("clusters", {})
    if not clusters:
        return

    new_clusters = {}

    for cid, cluster_mids in clusters.items():
        # keep only message IDs not in deleted_mids
        remaining = [mid for mid in cluster_mids if mid not in deleted_mids]
        if remaining:
            new_clusters[cid] = remaining

    st.session_state["clusters"] = new_clusters

if "msgs_meta" not in st.session_state:
    st.session_state["msgs_meta"] = {}
if "clusters" not in st.session_state:
    st.session_state["clusters"] = {}
if "cluster_labels" not in st.session_state:
    st.session_state["cluster_labels"] = {}

col1, col2 = st.columns([1, 3])
with col1:
    q = st.text_input("Gmail query (leave blank for all):", value="", key="query_input")
    max_fetch = st.number_input("Max messages to fetch", min_value=100, max_value=50000, value=300, step=100, key="max_fetch_input")
    if st.button("Scan Inbox / Archive", key="scan_button"):
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
        # New Signature Based Clusters

        index_clusters = clusterer.hybrid_clusters(texts)
        clusters = {
            cid: [mids[i] for i in indices]
            for cid,indices in index_clusters.items()
        }
        st.session_state["clusters"] = clusters
        st.success(f"Formed {len(clusters)} clusters.")
        st.session_state['cluster_labels'] = {}
with col2:
    clusters = st.session_state.get("clusters", {})

    st.header("Clusters")

    cluster_summaries = {}
    for cid, cluster_mids in sorted(clusters.items(), key=lambda x: -len(x[1])):
            sig = clusterer.cluster_signature(cluster_mids)
            if sig not in st.session_state["cluster_labels"]:
                try:
                    # Build sample texts
                    sample_texts = []
                    for mid in cluster_mids[:6]:
                        meta = st.session_state["msgs_meta"][mid]
                        sample_texts.append(
                            f"Subject: {meta.get('subject','')}\n{meta.get('snippet','')}"
                        )

                    # ---- LABELING STRATEGY ----
                    if len(cluster_mids) == 1:
                        meta = st.session_state["msgs_meta"][cluster_mids[0]]
                        out = json.dumps({ # pyright: ignore[reportPossiblyUnboundVariable]
                            "label": meta.get("subject", "Single email"),
                            "summary": meta.get("snippet", "")
                        })

                    elif len(cluster_mids) == 2:
                        meta = st.session_state["msgs_meta"][cluster_mids[0]]
                        out = json.dumps({ # pyright: ignore[reportPossiblyUnboundVariable]
                            "label": meta.get("from", "Two emails"),
                            "summary": meta.get("subject", "")
                        })

                    else:
                        out = summarize_cluster(sample_texts)

                except Exception as e:
                    out = json.dumps({ # pyright: ignore[reportPossiblyUnboundVariable]
                        "label": "Cluster",
                        "summary": f"Labeling failed: {e}"
                    })

                # ---- PARSE RESULT ----
                import re, json
                m = re.search(r"\{.*\}", out, re.S)
                if m:
                    try:
                        j = json.loads(m.group(0))
                        label = j.get("label", "Cluster")
                        summary = j.get("summary", "")
                    except Exception:
                        label = "Cluster"
                        summary = out
                else:
                    label = "Cluster"
                    summary = out

                st.session_state["cluster_labels"][sig] = {
                    "label": label,
                    "summary": summary
                }

            cluster_summaries[cid] = st.session_state["cluster_labels"][sig]

        # Display cluster cards
    for cid, indices in sorted(clusters.items(), key=lambda x: -len(x[1])):

        cluster_mids = indices
        sig = clusterer.cluster_signature(cluster_mids)

        # Fetch stable label
        meta = st.session_state["cluster_labels"].get(
            sig,
            {"label": "Unlabeled", "summary": ""}
        )

        with st.expander(f"{meta['label']} — {len(indices)} emails"):

            st.write(meta["summary"])

            cols = st.columns([3, 1, 1])
    
            # Delete group
            if cols[2].button("Delete entire group", key=f"del_group_{cid}"):
                with st.spinner("Permanently deleting messages..."):
                    success_count, failure_count = gmail.move_to_trash(cluster_mids)

                if success_count > 0:
                    st.success(f"Successfully trashed {success_count} messages.")
                    for mid in cluster_mids:
                        st.session_state["msgs_meta"].pop(mid, None)
                    remove_mids_from_clusters(cluster_mids)
                    st.rerun()

            # Archive group
            if cols[1].button("Archive entire group", key=f"archive_group_{cid}"):
                with st.spinner("Archiving messages..."):
                    success_count, failure_count = gmail.archive_messages(cluster_mids)

                if success_count > 0:
                    st.success(f"Successfully archived {success_count} messages.")
                    for mid in cluster_mids:
                        st.session_state["msgs_meta"].pop(mid, None)
                    remove_mids_from_clusters(cluster_mids)
                    st.rerun()

            # Preview table
            rows = []
            for mid in cluster_mids[:10]:
                mmeta = st.session_state["msgs_meta"].get(mid, {})
                rows.append({
                    "message_id": mid,
                    "from": mmeta.get("from", "")[:80],
                    "subject": mmeta.get("subject", "")[:120],
                    "snippet": mmeta.get("snippet", "")[:180]
                })

            df = pd.DataFrame(rows)
            sel = st.multiselect(
                "Select emails to preview/delete (select rows below)",
                options=list(df['message_id']),
                format_func=lambda x: df[df['message_id']==x]['subject'].values[0],
                key=f"multiselect_{cid}"
            )
            if sel:
                # show full bodies in a modal-like area
                for mid in sel:
                    raw = gmail.get_message_raw(mid)
                    raw_raw = raw.get("raw", "")
                    text = extract_plaintext_from_raw(raw_raw) if raw_raw else "(no raw body cached)"
                    st.markdown(f"**From:** {st.session_state['msgs_meta'][mid]['from']}  ")
                    st.markdown(f"**Subject:** {st.session_state['msgs_meta'][mid]['subject']}  ")
                    st.text_area("Full email", value=text[:10000], height=300, key=f"email_{cid}_{mid}")
                    # safe-delete prediction for the single message
                    if st.button(f"Check safe-delete for this email ({mid[:8]})", key=f"score_{cid}_{mid}"):
                        with st.spinner("Asking Claude..."):
                            out = safe_delete_score_for_message(text)
                            # Parse the string response into a dict
                            import json, re
                            m = re.search(r'\{.*\}', str(out), re.S)
                            if m:
                                try:
                                    parsed_out = json.loads(m.group(0))
                                except json.JSONDecodeError:
                                    try:
                                        parsed_out = ast.literal_eval(m.group(0))
                                    except (ValueError, SyntaxError):
                                        parsed_out = {"score": "Error", "reason": f"Could not parse response: {out}"}
                            else:
                                parsed_out = {"score": "Error", "reason": f"No dict found in response: {out}"}
                            st.write(parsed_out["score"])
                            st.caption(parsed_out["reason"])

                if st.button("Delete selected emails (permanently)", key=f"delete_selected_{cid}"):
                    ids_to_delete = sel
                    with st.spinner("Moving messages to trash..."):
                        success_count, failure_count = gmail.move_to_trash(ids_to_delete)
                    if success_count > 0:
                        st.success(f"Successfully moved {success_count} messages to Trash.")
                        for mid in ids_to_delete:
                            st.session_state["msgs_meta"].pop(mid, None)
                        remove_mids_from_clusters(ids_to_delete)
                        st.rerun()
                        st.session_state.pop(f"multiselect_{cid}", None)
    else:
        st.info("Scan your mailbox to see clusters.")
