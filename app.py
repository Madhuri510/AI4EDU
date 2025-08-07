# # 

#
# import streamlit as st
# import os
# import asyncio
# import requests
# from datetime import datetime, timezone
# from utils.agentic_workflow import generate_case_from_blob
# from utils.azure_blob_utils import upload_to_blob, upload_text_to_blob

# st.set_page_config(page_title="Agentic Case Generator", layout="wide")
# st.title("📄 AI Case Composer with Multi-Agent Workflow")
# st.markdown("---")

# # Step 1: Prompt input
# st.subheader("1. Enter a prompt")
# prompt = st.text_area("Prompt", placeholder="e.g., Generate a teaching case from the uploaded files based on the writer's guide.")

# # Step 2: Upload file
# st.subheader("2. Upload a file (PDF or DOCX)")
# uploaded_file = st.file_uploader("Browse and Upload", type=["pdf", "docx"])

# # Step 3: Generate Case
# st.subheader("3. Generate Case")
# if st.button("Generate Case"):
#     if not prompt and not uploaded_file:
#         st.warning("⚠️ Please enter a prompt or upload a file before generating the case.")
#     elif uploaded_file and not prompt:
#         st.warning("⚠️ Prompt required for generating a case from the file.")
#     elif not uploaded_file:
#         st.info("💬 Generating case based on prompt only (no document uploaded)...")
#         try:
#             result = asyncio.run(generate_case_from_blob(None, prompt))
#             st.subheader("📘 Case Output")
#             st.markdown(result)
#             try:
#                 case_path = upload_text_to_blob(result, folder="results/")
#                 st.success(f"✅ Case saved to Azure Blob: {case_path}")

#                 # Send raw text to Teams
#                 teams_url = st.secrets["TEAMS_WEBHOOK_URL"]
#                 preview = result[:3000]
#                 message = {
#                             "text": (
#                                 f"📘 *New Case Generated from Agentic Workflow!*\n\n"
#                                 f"📝 *Prompt:* {prompt}\n\n"
#                                 f"🗂️ *Generated Case:*\n\n```\n{preview}\n```"
#                             )
#                         }
#                 response = requests.post(teams_url, json=message)
#                 if response.status_code == 200:
#                     st.success("✅ Case sent to Microsoft Teams!")
#                 else:
#                     st.warning(f"⚠️ Failed to send to Teams (Status {response.status_code})")
#             except Exception as save_err:
#                 st.warning(f"⚠️ Could not upload case to Azure Blob: {save_err}")
#         except Exception as e:
#             st.error(f"❌ Error: {e}")
#     else:
#         try:
#             blob_path = upload_to_blob(uploaded_file)
#             st.subheader("📘 Case Output")
#             with st.spinner("Generating the case using AI agents..."):
#                 result = asyncio.run(generate_case_from_blob(blob_path, prompt))
#                 st.markdown(result)
#                 try:
#                     case_path = upload_text_to_blob(result, folder="results/")
#                     st.success(f"✅ Case saved to Azure Blob: {case_path}")

#                     # Send raw text to Teams
#                     teams_url = st.secrets["TEAMS_WEBHOOK_URL"]
#                     preview = result[:3000]
#                     message = {
#                             "text": (
#                                 f"📘 *New Case Generated from Agentic Workflow!*\n\n"
#                                 f"📝 *Prompt:* {prompt}\n\n"
#                                 f"🗂️ *Generated Case:*\n\n```\n{preview}\n```"
#                             )
#                         }
#                     response = requests.post(teams_url, json=message)
#                     if response.status_code == 200:
#                         st.success("✅ Case sent to Microsoft Teams!")
#                     else:
#                         st.warning(f"⚠️ Failed to send to Teams (Status {response.status_code})")
#                 except Exception as save_err:
#                     st.warning(f"⚠️ Could not upload case to Azure Blob or send to Teams: {save_err}")
#         except Exception as e:
#             st.error(f"❌ Error: {e}")


import streamlit as st
import os
import asyncio
import requests
from datetime import datetime, timezone
from utils.agentic_workflow import generate_case_from_blob
from utils.azure_blob_utils import upload_to_blob, upload_text_to_blob


st.markdown("<meta name='robots' content='noindex'>", unsafe_allow_html=True)


st.set_page_config(page_title="Agentic Case Generator", layout="wide")
st.title("📄 Agentic AI Case Builder")
st.markdown("---")

# Step 1: Prompt input
st.subheader("1. Enter a prompt")
prompt = st.text_area("Prompt", placeholder="e.g., Generate a teaching case from the uploaded files based on the writer's guide.")

# Step 2: Upload file
st.subheader("2. Upload a file (PDF or DOCX)")
uploaded_file = st.file_uploader("Browse and Upload", type=["pdf", "docx"])

# Initialize session state
if "generated_case" not in st.session_state:
    st.session_state.generated_case = ""
if "prompt_used" not in st.session_state:
    st.session_state.prompt_used = ""

# Step 3: Generate Case
st.subheader("3. Generate Case")
if st.button("Generate Case"):
    if not prompt and not uploaded_file:
        st.warning("⚠️ Please enter a prompt or upload a file before generating the case.")
    elif uploaded_file and not prompt:
        st.warning("⚠️ Prompt required for generating a case from the file.")
    elif not uploaded_file:
        st.info("💬 Generating case based on prompt only (no document uploaded)...")
        try:
            result = asyncio.run(generate_case_from_blob(None, prompt))
            st.session_state.generated_case = result
            st.session_state.prompt_used = prompt
            st.subheader("📘 Case Output")
            st.markdown(result)
            try:
                case_path = upload_text_to_blob(result, folder="results/")
                st.success(f"✅ Case saved to Azure Blob: {case_path}")
            except Exception as save_err:
                st.warning(f"⚠️ Could not upload case to Azure Blob: {save_err}")
        except Exception as e:
            st.error(f"❌ Error: {e}")
    else:
        try:
            blob_path = upload_to_blob(uploaded_file)
            st.subheader("📘 Case Output")
            with st.spinner("Generating the case using AI agents..."):
                result = asyncio.run(generate_case_from_blob(blob_path, prompt))
                st.session_state.generated_case = result
                st.session_state.prompt_used = prompt
                st.markdown(result)
                try:
                    case_path = upload_text_to_blob(result, folder="results/")
                    st.success(f"✅ Case saved to Azure Blob: {case_path}")
                except Exception as save_err:
                    st.warning(f"⚠️ Could not upload case to Azure Blob: {save_err}")
        except Exception as e:
            st.error(f"❌ Error: {e}")

# Step 4: Optional Teams Send
if st.session_state.generated_case:
    st.subheader("4. Optional: Send to Teams")
    if st.button("📤 Send Case to Microsoft Teams"):
        try:
            teams_url = st.secrets["TEAMS_WEBHOOK_URL"]
            preview = st.session_state.generated_case[:3000]  # Trim to fit Teams message limit
            message = {
                "text": f"📘 *New Case Generated!*\n\n📝 *Prompt:* {st.session_state.prompt_used}\n\n🗂️ *Case Output:*\n```\n{preview}\n```"
            }
            response = requests.post(teams_url, json=message)
            if response.status_code == 200:
                st.success("✅ Case sent to Microsoft Teams!")
            else:
                st.warning(f"⚠️ Failed to send to Teams (Status {response.status_code})")
        except Exception as e:
            st.error(f"❌ Error sending to Teams: {e}")

