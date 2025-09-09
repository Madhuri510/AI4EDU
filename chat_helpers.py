# utils/chat_helpers.py
import streamlit as st
from fpdf import FPDF
import tempfile
import base64

def display_conversation(conversation):
    """
    Render all chat messages in ChatGPT-style UI.
    """
    for msg in conversation:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        st.chat_message(role).markdown(content)

def download_as_pdf(text, title="Generated_Case"):
    """
    Create a downloadable PDF button from a string of text.
    """
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", size=12)

    # Split content into lines and write to PDF
    lines = text.split("\n")
    for line in lines:
        pdf.multi_cell(0, 10, line)

    # Save to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        pdf.output(tmp.name)
        tmp.seek(0)
        b64 = base64.b64encode(tmp.read()).decode()
        href = f'<a href="data:application/octet-stream;base64,{b64}" download="{title}.pdf">📥 Download Case as PDF</a>'
        st.markdown(href, unsafe_allow_html=True)

def get_friendly_response(prompt: str) -> str | None:
    """
    Simple rule-based response for basic greetings or small talk.
    Returns None if the message is not a friendly small-talk message.
    """
    p = prompt.lower().strip()

    responses = {
        "hello": "Hi there! 😊 What would you like to do today?",
        "hi": "Hello! 👋 Ready to generate a case?",
        "hey": "Hey! How can I help you today?",
        "how are you": "I'm doing great, thanks for asking! 😊",
        "thank you": "You're very welcome! 🙌",
        "thanks": "Anytime! 😊",
        "bye": "Goodbye! 👋 Have a great day!",
    }

    for key in responses:
        if key in p:
            return responses[key]

    return None
