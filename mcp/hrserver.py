from mcp.server.fastmcp import FastMCP
from pathlib import Path
from fastapi import FastAPI
import spacy
import json
import argparse
import fitz  # PyMuPDF

import uvicorn

mcp = FastMCP("hr", stateless_http=True)
app = FastAPI(title="hr",lifespan=lambda app: mcp.session_manager.run())
app.mount("/hr", mcp.streamable_http_app())

"""
 this will be the hr server that will include to tools for HR management]
    - tools: candidate screening, interview scheduling.
"""

skills_file = Path(__file__).parent / "hrskills.json"

nlp = spacy.load("en_core_web_lg") 

def __load_hr_skills():
    with open(skills_file, "r") as f:
        skills_data = json.load(f)
    return skills_data

def __preprocess_resume(resume: str) -> str:
    return " ".join(resume.lower().split())


def __extract_text_from_pdf(resume) -> str:
    doc_stream = fitz.open(stream=resume, filetype="pdf")
    text = ""
    for page in doc_stream:
        text += page.get_text()
    return text

@mcp.tool()
def candidate_screening(file_path: str, role: str) -> str:
    """
    check the candidate resume and return screening result

    Args:
        resume (MCPFile): The candidate's resume in text or uploaded pdf via MCP $file.
        role (str): The job role to screen for.
    
    Returns:
        str: A JSON string containing the screening results.
    """
    hr_skills = __load_hr_skills()
    required_skills = next((x["skills"] for x in hr_skills if x["role"].lower() == role.lower()), None)

    if not required_skills:
        return f"No skills found for the role: {role}"

    matched_report = {}
    total_skills = 0
    total_matched = 0

    results = {}
    if not file_path.exists() or not file_path.is_file():
        try:
            resume = __extract_text_from_pdf(resume)
        except Exception as e:
            return f"missing filepath or Error extracting text from PDF: {str(e)}"
    else:
        resume = str(resume)
    
    print("Resume Text Extracted:", resume[:1000])
    resume_processed = __preprocess_resume(resume)  
    resume_doc = nlp(resume_processed)

    for category, skills_list in required_skills["technical_skills"].items():
        matched_skills = []
        missing_skills = []
        for skill in skills_list:
            total_skills += 1
            skill_doc = nlp(skill.lower())

            similiarity = resume_doc.similarity(skill_doc)

            if similiarity > 0.5:
                matched_skills.append(skill)
                total_matched += 1
            else:
                missing_skills.append(skill)
        results[category] = {
            "matched_skills": matched_skills,
            "missing_skills": missing_skills            
        }
    match_percentage = (total_matched / total_skills) * 100 if total_skills > 0 else 0
    matched_report["results"] = results
    matched_report["summary"] = {
        "role": role,
        "total_skills": total_skills,
        "total_matched": total_matched,
        "match_percentage": match_percentage
    }

    return json.dumps(matched_report, indent=2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HR Server")
    parser.add_argument("--host", type=str, default="127.0.01", help="Host for the HR server")
    parser.add_argument("--port", type=int, default=8001, help="Port for the HR server")
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")

