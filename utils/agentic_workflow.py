# agentic_workflow.py
import os
import tempfile
from datetime import datetime, timezone
from typing import Optional
import dotenv
import yaml
from azure.storage.blob import BlobServiceClient
from docx import Document
from PyPDF2 import PdfReader
from crewai import Agent, Task, Crew, LLM

def _download_blob_to_local(blob_path: str) -> str:
    print(f"[⏬] Downloading blob: {blob_path}")
    connection_string = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
    container_name = os.environ["AZURE_CONTAINER_NAME"]

    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_path)

    _, ext = os.path.splitext(os.path.basename(blob_path))
    fd, tmp_path = tempfile.mkstemp(suffix=ext)
    os.close(fd)

    with open(tmp_path, "wb") as f:
        f.write(blob_client.download_blob().readall())

    print(f"[✅] Blob saved: {tmp_path}")
    return tmp_path

def _extract_text(file_path: str) -> str:
    print(f"[📄] Extracting text: {file_path}")
    if file_path.endswith(".pdf"):
        with open(file_path, "rb") as f:
            reader = PdfReader(f)
            return "\n".join([p.extract_text() or "" for p in reader.pages])
    elif file_path.endswith(".docx"):
        return "\n".join([p.text for p in Document(file_path).paragraphs])
    raise ValueError("Unsupported file type")

def _load_agents(yaml_path: str, model_name: str) -> dict:
    print(f"[INFO] Loading agents from: {yaml_path}")
    with open(yaml_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    agents = {}
    for name, data in config.items():
        raw_llm = data.get("llm", f"azure/{model_name}")
        model = raw_llm.replace("${LITELLM_MODEL}", model_name).strip()
        if not model.startswith("azure/"):
            model = f"azure/{model}"

        try:
            llm = LLM(model=model)
        except Exception as e:
            print(f"[ERROR] Failed to init LLM for {name}: {e}")
            raise

        agents[name] = Agent(
            role=data.get("role", name.title()),
            goal=data.get("goal", ""),
            backstory=data.get("backstory", ""),
            allow_delegation=data.get("allow_delegation", False),
            verbose=True,
            llm=llm
        )
        print(f"[INFO] Created agent: {name}")
    return agents

def run_agents(guide_text: str, yaml_path: str = "agents.yaml") -> str:
    dotenv.load_dotenv()
    os.environ["AZURE_API_BASE"] = os.getenv("AZURE_API_BASE", "").strip()
    os.environ["AZURE_API_KEY"] = os.getenv("AZURE_API_KEY", "").strip()
    os.environ["AZURE_API_VERSION"] = os.getenv("AZURE_API_VERSION", "").strip()

    model_name = os.getenv("LITELLM_MODEL") or os.getenv("AZURE_MODEL") or "o4-mini"
    model_name = model_name.strip()

    print("[🧪] ENV CHECK")
    print("AZURE_API_BASE:", repr(os.environ["AZURE_API_BASE"]))
    print("API KEY set:", bool(os.environ["AZURE_API_KEY"]))
    print("Deployment:", model_name)

    try:
        agents = _load_agents(yaml_path, model_name)
    except Exception as e:
        print(f"[⚠️] Error loading YAML agents: {e}")
        return "Failed to load agents."

    planner = agents.get("planner")
    writer = agents.get("writer")
    critic = agents.get("critic")

    plan_description = (
        "Based on the Case Writing Guide, create a step-by-step plan to produce a complete case study. "
        "Ensure the output is structured with clear steps such as case framing, background research, issue identification, alternatives, and discussion questions. "
        "The format must match the following structure:\n\n"
        "1. Opening Paragraph\n2. Background\n3. Specific Issue/Decision Point\n4. Alternatives\n5. Conclusion\n6. Discussion Questions\n"
    )

    write_description = (
        "Using the case study guide and structured plan, write a complete case study draft. The final output should strictly follow this structure:\n\n"
        "**Case Study: [Title]**\n\n"
        "**Opening Paragraph**: ...\n\n"
        "**Background**: ...\n\n"
        "**Specific Issue/Decision Point**: ...\n\n"
        "**Alternatives**: ...\n\n"
        "**Conclusion**: ...\n\n"
        "**Discussion Questions**:\n1. ...\n2. ...\n3. ...\n"
    )

    critique_description = (
        "Review the draft and provide improvement suggestions. Ensure the case is engaging, well-formatted, and helpful for classroom discussion."
    )

    crew = Crew(
        agents=[planner, writer, critic],
        tasks=[
            Task(description=plan_description, expected_output="Structured case plan", agent=planner),
            Task(description=write_description, expected_output="Formatted case draft", agent=writer),
            Task(description=critique_description, expected_output="Detailed critique and suggestions", agent=critic)
        ],
        verbose=True
    )

    print("[🚀] Crew kickoff at", datetime.now(timezone.utc).isoformat())
    result = crew.kickoff()
    return str(result)


async def generate_case_from_blob(blob_path: Optional[str], user_prompt: str) -> str:
    print("[📘] Starting case generation...")

    try:
        # Load the internal case writing guide first
        guide_text = _extract_text(_download_blob_to_local("internal-docs/CaseWritingGuide.pdf"))
    except Exception as e:
        return f"❌ Failed to load guide: {e}"

    if blob_path:
        try:
            user_file = _download_blob_to_local(blob_path)
            user_text = _extract_text(user_file)

            # If you want to include user prompt content into guide_text, append here
            guide_text += f"\n\n---\n\nAdditional Context from Uploaded File:\n\n{user_text}"

        except Exception as e:
            return f"❌ Failed to load user file: {e}"

    try:
        return run_agents(guide_text)
    except Exception as e:
        return f"❌ CrewAI execution failed: {e}"
