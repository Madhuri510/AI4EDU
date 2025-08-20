# app_flask.py
import os
from flask import Flask, request, render_template_string
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import check_password_hash, generate_password_hash

from utils.agentic_workflow import generate_case_from_blob
from utils.azure_blob_utils import upload_to_blob, upload_text_to_blob
import asyncio

# ----- HTTP Basic Auth -----
BASIC_USER = os.getenv("BASIC_AUTH_USERNAME", "admin")
BASIC_PASS = os.getenv("BASIC_AUTH_PASSWORD", "AI4EDU")
PASSWORD_HASH = generate_password_hash(BASIC_PASS)

auth = HTTPBasicAuth()
USERS = {BASIC_USER: PASSWORD_HASH}

@auth.verify_password
def verify_password(username, password):
    if username in USERS and check_password_hash(USERS[username], password):
        return username
    return None

# ----- Flask app -----
app = Flask(__name__)

@app.get("/robots.txt")
def robots():
    return ("User-agent: *\nDisallow: /\n", 200, {"Content-Type": "text/plain; charset=utf-8"})

HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Agentic AI Case Builder</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    body { font-family: system-ui, Segoe UI, Roboto, Arial, sans-serif; padding: 24px; max-width: 880px; margin: auto; }
    textarea { width: 100%; height: 160px; }
    input[type=file] { width: 100%%; }
    .btn { background:#1f6feb; color:#fff; padding:10px 16px; border:none; border-radius:8px; cursor:pointer; }
    .card { border:1px solid #e5e7eb; border-radius:12px; padding:18px; margin-top:16px; }
    pre { white-space: pre-wrap; }
    .muted { color:#6b7280; }
  </style>
</head>
<body>
  <h1>📄 Agentic AI Case Builder</h1>
  <p class="muted">Protected by HTTP Basic Authentication</p>
  <form action="/generate" method="post" enctype="multipart/form-data">
    <div class="card">
      <h3>1) Enter a prompt</h3>
      <textarea name="prompt" placeholder="e.g., Generate a teaching case..."></textarea>
    </div>
    <div class="card">
      <h3>2) Upload a file (PDF or DOCX)</h3>
      <input type="file" name="file" accept=".pdf,.docx" />
    </div>
    <div class="card">
      <h3>3) Generate</h3>
      <button class="btn" type="submit">Generate Case</button>
    </div>
  </form>

  {% if error %}
    <div class="card" style="border-color:#ef4444;">
      <h3>❌ Error</h3>
      <pre>{{ error }}</pre>
    </div>
  {% endif %}

  {% if result %}
    <div class="card">
      <h3>📘 Case Output</h3>
      <pre>{{ result }}</pre>
    </div>
    {% if saved %}
      <div class="card">✅ Saved to Azure Blob: <code>{{ saved }}</code></div>
    {% endif %}
  {% endif %}
</body>
</html>
"""

@app.get("/")
@auth.login_required
def index():
    return render_template_string(HTML)

@app.post("/generate")
@auth.login_required
def generate():
    prompt = (request.form.get("prompt") or "").strip()
    f = request.files.get("file")

    if not prompt and not f:
        return render_template_string(HTML, error="Please enter a prompt or upload a file.")

    try:
        blob_path = None
        if f and f.filename:
            blob_path = upload_to_blob(f)

        result = asyncio.run(generate_case_from_blob(blob_path, prompt))
        saved_path = None
        try:
            saved_path = upload_text_to_blob(result, folder="results/")
        except Exception:
            saved_path = None

        return render_template_string(HTML, result=result, saved=saved_path)
    except Exception as e:
        return render_template_string(HTML, error=str(e))

@app.get("/healthz")
def healthz():
    return "ok", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")))

