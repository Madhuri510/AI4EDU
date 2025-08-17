import asyncio
import streamlit as st

from utils.agentic_workflow import generate_case_from_blob
from utils.azure_blob_utils import upload_to_blob, upload_text_to_blob

# History store
from utils.conversation_store import (
    init_db, create_session, list_sessions, get_session,
    add_message, rename_session, delete_session
)

# -------------------- App setup --------------------
st.set_page_config(page_title="Agentic AI Case Builder", layout="wide")
init_db()

# -------------------- Sidebar: Chat-like history --------------------
with st.sidebar:
    st.header("History")

    search = st.text_input("Search", "", placeholder="filter by title…")
    sessions = list_sessions(search=search, limit=100)

    # Keep selected session id in session_state
    if "selected_session_id" not in st.session_state:
        st.session_state.selected_session_id = None

    # List sessions (newest first)
    for s in sessions:
        if st.button(s["title"], key=f"sessbtn-{s['id']}"):
            st.session_state.selected_session_id = s["id"]

    st.markdown("---")
    col_a, col_b, col_c = st.columns(3)

    with col_a:
        if st.button("New"):
            sid = create_session("Untitled")
            st.session_state.selected_session_id = sid
            st.rerun()

    with col_b:
        # Rename uses a small inline input + apply button
        if st.session_state.selected_session_id:
            new_title = st.text_input("Rename to:", key="rename_title", placeholder="type new title")
            if st.button("Apply rename"):
                rename_session(st.session_state.selected_session_id, new_title or "Untitled")
                st.rerun()

    with col_c:
        if st.session_state.selected_session_id and st.button("Delete"):
            delete_session(st.session_state.selected_session_id)
            st.session_state.selected_session_id = None
            st.rerun()

# -------------------- Main UI --------------------
st.title("Agentic AI Case Builder")
st.markdown("---")

st.subheader("1. Enter a prompt")
prompt = st.text_area("Prompt", placeholder="e.g., Generate a teaching case using the writer's guide.")

st.subheader("2. Upload a file (PDF or DOCX)")
uploaded_file = st.file_uploader("Browse and Upload", type=["pdf", "docx"])

# Show a short tail of history for the selected session
loaded_session = None
if st.session_state.get("selected_session_id"):
    loaded_session = get_session(st.session_state.selected_session_id)
    if loaded_session.get("messages"):
        st.markdown("##### Loaded from history")
        for m in loaded_session["messages"][-4:]:
            who = "You" if m["role"] == "user" else "App"
            # Trim long messages for display
            preview = (m["content"][:400] + "…") if len(m["content"]) > 400 else m["content"]
            st.markdown(f"**{who}:** {preview}")

# Keep last output around (e.g., for Teams later if you add it)
if "generated_case" not in st.session_state:
    st.session_state.generated_case = ""
if "prompt_used" not in st.session_state:
    st.session_state.prompt_used = ""

# -------------------- Generate --------------------
st.subheader("3. Generate Case")
if st.button("Generate Case"):
    # Ensure there is an active session
    if not st.session_state.get("selected_session_id"):
        st.session_state.selected_session_id = create_session("Untitled")
    sid = st.session_state.selected_session_id

    # Validate inputs
    if not prompt and not uploaded_file:
        st.warning("Please enter a prompt or upload a file.")
        st.stop()
    if uploaded_file and not prompt:
        st.warning("Prompt is required when a file is uploaded.")
        st.stop()

    # Save the user prompt (and filename) into history BEFORE generation
    meta = {}
    if uploaded_file is not None:
        meta["uploaded_filename"] = uploaded_file.name
    add_message(sid, role="user", content=prompt or "(no prompt)", meta=meta)

    # Try uploading file to Azure (if configured); otherwise fall back to local-only flow
    blob_path = None
    if uploaded_file is not None:
        try:
            blob_path = upload_to_blob(uploaded_file)
        except Exception as e:
            st.info(f"(Local-only run) Skipping Azure upload: {e}")

    # Run generation
    st.subheader("Case Output")
    with st.spinner("Generating the case..."):
        try:
            result = asyncio.run(generate_case_from_blob(blob_path, prompt))
        except Exception as e:
            st.error(f"Error during generation: {e}")
            st.stop()

    # Show output
    st.session_state.generated_case = result
    st.session_state.prompt_used = prompt
    st.markdown(result)

    # Save assistant output into history
    add_message(sid, role="assistant", content=result, meta={"type": "case_output"})

    # Auto-title session from first prompt (if still Untitled)
    sess = get_session(sid)
    if sess and sess.get("title") == "Untitled" and prompt.strip():
        auto = (prompt.strip()[:50] + "...") if len(prompt.strip()) > 50 else prompt.strip()
        rename_session(sid, auto)

    # Try saving result text to Azure (if configured)
    try:
        path = upload_text_to_blob(result, folder="results/")
        st.success(f"Saved to Azure Blob: {path}")
    except Exception as e:
        st.info(f"(Local-only run) Skipping Azure save: {e}")
