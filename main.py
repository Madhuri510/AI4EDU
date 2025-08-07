# main.py
from fastapi import FastAPI
from fastapi.responses import Response, FileResponse
import os
import streamlit.web.bootstrap

app = FastAPI()

@app.get("/robots.txt")
def robots():
    file_path = os.path.join(os.path.dirname(__file__), "robots.txt")
    return FileResponse(file_path, media_type="text/plain")

@app.get("/{full_path:path}")
def streamlit_app(full_path: str):
    # Redirect all other requests to Streamlit
    streamlit.web.bootstrap.run(
        "app.py",
        command_line=["streamlit", "run", "app.py", "--server.port", "8000", "--server.address", "0.0.0.0"],
        args=[]
    )
    return Response("Streamlit app started.", media_type="text/plain")
