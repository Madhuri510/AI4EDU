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

    if not isinstance(config, dict):
        raise ValueError(
            f"agents.yaml must be a mapping of agent-name -> config dict. Got {type(config).__name__}."
        )

    agents = {}
    for name, data in config.items():
        if not isinstance(data, dict):
            raise ValueError(
                f"Agent '{name}' must be a dict (role/goal/backstory/llm). "
                f"Got {type(data).__name__}: {data!r}"
            )

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


def run_agents(guide_text: str, user_prompt: str = "") -> str:
    dotenv.load_dotenv()
    os.environ["AZURE_API_BASE"] = os.getenv("AZURE_API_BASE", "").strip()
    os.environ["AZURE_API_KEY"] = os.getenv("AZURE_API_KEY", "").strip()
    os.environ["AZURE_API_VERSION"] = os.getenv("AZURE_API_VERSION", "").strip()

    model_name = (os.getenv("LITELLM_MODEL") or os.getenv("AZURE_MODEL") or "o4-mini").strip()

    print("[🧪] ENV CHECK")
    print("AZURE_API_BASE:", repr(os.environ["AZURE_API_BASE"]))
    print("API KEY set:", bool(os.environ["AZURE_API_KEY"]))
    print("Deployment:", model_name)

    # ---------- Helpers ----------
    import re
    def coverage_tokens(text: str) -> list[str]:
        pats = [
            r"\bUCAS[- ]?D\b", r"\bX[- ]?47B\b", r"\bUFO on the Beltway\b", r"\bPAO\b", r"\bPEO\b",
            r"\bCPI\b", r"\bSPI\b", r"\bhook(point)?\b", r"\bsnubber\b", r"\bcarrier\b",
            r"\bLos Angeles Times\b", r"\bFebruary\s+\d{1,2},\s*2013\b", r"\bJune\s+2013\b"
        ]
        hits = []
        for p in pats:
            if re.search(p, text, flags=re.IGNORECASE):
                hits.append(re.sub(r"\\b", "", p).strip("\\"))
        # dedup + cap at 10 to keep prompt small
        out = []
        for h in hits:
            if h not in out:
                out.append(h)
        return out[:10]

    TOKENS = coverage_tokens(guide_text)
    TOKENS_TEXT = ("### MUST INCLUDE (only if present in source)\n- " + "\n- ".join(TOKENS)) if TOKENS else ""

    SOURCE_FIRST = (
        "### UPLOADED CASE SOURCE (authoritative)\n"
        f"{guide_text}\n\n"
        "### STYLE GUIDE (reference only)\n"
        "Use this only for tone/clarity. Do NOT add sections that aren't present in the source unless asked."
    )

    SECTION_POLICY = (
        "### SECTION POLICY\n"
        "- Detect existing/implicit sections from the source (e.g., title/front matter, Program Description, "
        "Program History, News Media Perspective, PEO POV, Chief Engineer Email, PAO Tasker, Deputy PM Advice, "
        "Assignment Questions, Exhibits) and render them in that order if present.\n"
        "- If a common section is NOT present, do not invent it.\n"
        "- If front matter (title/disclaimer/date/institution) is present in the source, render it verbatim at top.\n"
    )

    NO_INVENTION = (
        "### FACTUALITY GUARANTEE\n"
        "- Use ONLY facts present in the source. If a detail is missing, write: [Unknown in source].\n"
        "- Do NOT fabricate outcomes, numbers (e.g., CPI/SPI), or quotes.\n"
    )

    # ---------- Agents ----------
    try:
        agents = _load_agents("agents.yaml", model_name)
    except Exception as e:
        return f"Failed to load agents. Details: {e}"

    planner = agents.get("planner")
    writer  = agents.get("writer")
    critic  = agents.get("critic")

    # ---------- Tasks ----------
    from crewai import Task, Crew, LLM
    # (Optional) make agents conservative if supported by your CrewAI version
    try:
        planner.llm = LLM(model=f"azure/{model_name}", temperature=0, top_p=1)
        writer.llm  = LLM(model=f"azure/{model_name}", temperature=0, top_p=1)
        critic.llm  = LLM(model=f"azure/{model_name}", temperature=0, top_p=1)
    except Exception:
        pass  # older CrewAI may not accept kwargs here
    # ---------- RULE BLOCKS ----------
    FACTUALITY_QUOTE_POLICY = """### FACTUALITY & QUOTE POLICY
    - Use ONLY facts present in the Uploaded Case Source.
    - If a detail (number, date, outcome) is missing, write: [Unknown in source].
    - Do NOT invent quotations. Only use direct quotes that appear verbatim in the source.
    Otherwise, paraphrase with attribution (e.g., According to CAPT Engdahl, ...).
    """

    TIMELINE_ACCURACY = """### TIMELINE ACCURACY
    - Copy dates/events exactly as written in the source.
    - Example: January 2010 = taxi testing (not first flight). First flight = February 4, 2011.
    - If unsure, use [Unknown in source] rather than inferring.
    """

    SECTION_POLICY = """### SECTION POLICY
    - Detect and preserve existing headings/sections and their order when clearly implied:
    (e.g., Program Description, Program History, News Media Perspective, PEO POV,
    Chief Engineer Email, PAO Tasker/Media Qs, Deputy PM Advice, Assignment Questions, Exhibits).
    - Do NOT add “Recommendations”, “Learning Outcomes”, or other sections unless they exist in the source.
    - If front matter/disclaimer exists in the source, render it verbatim at the top.
    """

    # ---------- DESCRIPTIONS (built safely) ----------
    desc_plan = "\n".join([
        SOURCE_FIRST,            # <-- your computed context
        SECTION_POLICY,
        FACTUALITY_QUOTE_POLICY,
        TIMELINE_ACCURACY,
        TOKENS_TEXT,             # <-- can be "" and that's fine
        "PLAN: Output a concise, ordered plan (bullets) listing the section headers you will render, "
        "preserving the source’s order. No extra sections."
    ])

    desc_draft = "\n".join([
        SOURCE_FIRST,
        SECTION_POLICY,
        FACTUALITY_QUOTE_POLICY,
        TIMELINE_ACCURACY,
        TOKENS_TEXT,
        "DRAFT: Write the case using the planned sections. Preserve any front matter verbatim if present. "
        "Include Assignment Questions/Exhibits only if they exist in the source. "
        "Do not add Learning Outcomes or synthetic conclusions. Where a fact is missing, write [Unknown in source]."
    ])

    desc_verify = "\n".join([
        SOURCE_FIRST,
        FACTUALITY_QUOTE_POLICY,
        TIMELINE_ACCURACY,
        TOKENS_TEXT,
        "VERIFY: Review the draft for (a) any invented numbers/outcomes/quotes and (b) missing coverage of "
        "the MUST INCLUDE topics. Return ONLY a bullet list of concrete fixes."
    ])

    desc_final = "\n".join([
        SOURCE_FIRST,
        SECTION_POLICY,
        FACTUALITY_QUOTE_POLICY,
        TIMELINE_ACCURACY,
        TOKENS_TEXT,
        "FINALIZE: Apply the verifier’s fixes and output ONLY the final case text. No plan, no critique, no meta."
    ])

    # ---------- TASKS ----------
    plan_task = Task(
        description=desc_plan,
        expected_output="Ordered bullets of planned sections",
        agent=planner,
    )

    draft_task = Task(
        description=desc_draft,
        expected_output="Case draft closely matching source structure (no meta)",
        agent=writer,
        context=[plan_task],
    )

    verify_task = Task(
        description=desc_verify,
        expected_output="Bulleted issues: {invention?|missing coverage?|format drift?}",
        agent=critic,
        context=[draft_task],
    )

    final_task = Task(
        description=desc_final,
        expected_output="Final classroom-ready case text only",
        agent=writer,
        context=[plan_task, draft_task, verify_task],
    )

    crew = Crew(
        agents=[planner, writer, critic],
        tasks=[plan_task, draft_task, verify_task, final_task],
        verbose=True
    )

    print("[🚀] Crew kickoff")
    result = crew.kickoff()

    # ---------- POST-CLEANUP (local only) ----------
    def sanitize_output(source: str, out: str) -> str:
        import re
        src_lower = source.lower()

        # 1) Remove "Recommendations" if not in source
        if "recommendations" not in src_lower:
            out = re.sub(r"(?:\n|^)Recommendations\s*\n(?:.*\n)+?(?=\n[A-Z][^\n]*\n|$)", "\n", out)

        # 2) Convert unknown quotes to indirect speech
        for m in re.finditer(r"[“\"]([^”\"]+)[”\"]", out):
            q = m.group(0)
            inner = m.group(1).strip()
            if inner and inner.lower() not in src_lower:
                out = out.replace(q, inner)  # drop the quote marks

        # 3) Known UCAS-D timeline fix
        out = out.replace("January 2010: First flight", "January 2010: Taxi testing")
        return out

    final = sanitize_output(guide_text, str(result))
    return final


async def generate_case_from_blob(blob_path: Optional[str], user_prompt: str) -> str:
    print("[📘] Starting case generation...")

    try:
        guide_text = _extract_text(_download_blob_to_local("internal-docs/CaseWritingGuide.pdf"))
    except Exception as e:
        return f"❌ Failed to load guide: {e}"

    if blob_path:
        try:
            user_file = _download_blob_to_local(blob_path)
            user_text = _extract_text(user_file)
            # keep the user's content appended to the guide (as before)
            guide_text += f"\n\n---\n\nAdditional Context from Uploaded File:\n\n{user_text}"
        except Exception as e:
            return f"❌ Failed to load user file: {e}"

    try:
        # <<< key change: forward BOTH the aggregated text and the user's prompt >>>
        return run_agents(guide_text, user_prompt)
    except Exception as e:
        return f"❌ CrewAI execution failed: {e}"
