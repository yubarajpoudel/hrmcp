import sys
from pathlib import Path

# Add parent directory to path to import modules from root
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from mcp.server.fastmcp import FastMCP
from hrmcpserver.prompts import Prompt
from hrmcpserver.calendar_service import CalendarService
import uvicorn
from rapidfuzz import fuzz
from fastapi import FastAPI
import argparse
import json
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
from typing import List, Optional


from ollama_extractor import OllamaExtractor
mcp = FastMCP("hr", stateless_http=True)

"""
 this will be the hr server that will include to tools for HR management]
    - tools: candidate screening, interview scheduling.
"""

skills_file = Path(__file__).parent / "hrskills.json"

def __load_hr_skills():
    with open(skills_file, "r") as f:
        skills_data = json.load(f)
    return skills_data

async def __extract_text_from_pdf(resume_bytes: bytes) -> str:
    doc_stream = fitz.open(stream=resume_bytes, filetype="pdf")
    text = ""
    for page in doc_stream:
        text += page.get_text()
    return text

def _prepare_image_for_ocr(image: Image.Image) -> Image.Image:
    """
    Apply preprocessing steps to boost OCR accuracy, especially for numbers.
    """
    img = image.convert("L")  # grayscale

    # Upscale small images to improve recognition of fine details
    min_dimension = min(img.size)
    if min_dimension < 1500:
        scale_factor = 2
        img = img.resize(
            (img.width * scale_factor, img.height * scale_factor),
            Image.LANCZOS,
        )

    # Enhance contrast and reduce noise
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.MedianFilter(size=3))

    # Binarize (threshold) to help distinguish characters
    img = img.point(lambda x: 255 if x > 160 else 0, mode="1")
    return img


def extract_text_from_image(
    image_path: str,
    languages: str = "eng+ara",
    whitelist: Optional[str] = None,
) -> str:
    """
    Extract text from an image (PNG/JPG) using Tesseract OCR.
    """
    try:
        with Image.open(image_path) as img:
            processed_img = _prepare_image_for_ocr(img)
            config = "--psm 6 --oem 3"
            if whitelist:
                config += f' -c tessedit_char_whitelist="{whitelist}"'
            text = pytesseract.image_to_string(
                processed_img,
                lang=languages,
                config=config,
            )
            return text.strip()
    except Exception as exc:
        print(f"Error extracting text from image {image_path}: {exc}")
        return ""

def parse_skills_text(text: str) -> list[str]:
    """
    Parses a string containing a list of skills (e.g., hyphenated or newlines) into a list of strings.
    """
    if not text:
        return []
    # Split by newlines and remove leading/trailing whitespace and hyphens
    skills = [line.strip().lstrip('- ').strip() for line in text.split('\n') if line.strip()]
    return skills

def __preprocess_resume(role: str, resume_text: str, role_skills: dict) -> list[str]:
    prompt_text = Prompt.prompt_resume_preprocess(role, resume_text, role_skills)
    ollm_extractor = OllamaExtractor()
    process_data = ollm_extractor.extract_data(prompt_text)
    
    if isinstance(process_data, str):
        return parse_skills_text(process_data)
        
    return process_data

@mcp.tool()
def read_resume_from_file(file_name: str) -> str:
    """
    Read the resume from the given file path and extract text.
    
    Args:
        file_name: Name of the resume file (relative to uploads directory or absolute path)
        
    Returns:
        The extracted resume text as a string.
    """    
    # Handle relative paths (assume uploads directory)
    print(f"file_name: {file_name}")
    if not file_name.startswith('/'):
        uploads_dir = Path(__file__).parent.parent / "uploads"
        full_path = uploads_dir / file_name
    else:
        full_path = Path(file_name)
    
    if not full_path.exists():
        return f"Error: File not found at {full_path}"
    print(f"full_path: {full_path}")
    try:
        # Extract text based on file type
        if str(full_path).lower().endswith(".pdf"):
            # Extract from PDF
            return __extract_text_from_pdf(full_path)            
        elif str(full_path).lower().endswith((".png", ".jpg", ".jpeg")):
            # Extract from image using OCR
            text = extract_text_from_image(str(full_path))
            return text.strip()
            
        else:
            return f"Error: Unsupported file type. Supported: PDF, PNG, JPG, JPEG"
            
    except Exception as e:
        return f"Error extracting text from file: {str(e)}"


@mcp.tool()
def get_interviewer_free_time(interviewer: str) -> dict:
    """
    Get the free time of the given interviewer.

    Args:
        interviewer: Email address of the interviewer
    Returns:
        A dictionary containing the free time of the interviewer.
    """
    return CalendarService.get_free_time_from_google(interviewer)

# tools to check the free time in the teams calendar of interviewers and schedule a call
@mcp.tool()
def schedule_interview(to_email: str, start_time: str, end_time: str, candidate_name: str = None, role: str = None) -> dict:
    """
    Schedule an interview with the given interviewer for the given role.
     Args:
        to_email: Email address of the interviewee
        start_time: Start time in ISO format (e.g., "2025-11-27T10:00:00+04:00")
        end_time: End time in ISO format (e.g., "2025-11-27T11:00:00+04:00")
        candidate_name: Optional name of the candidate
        role: Optional role being interviewed for
    Returns:
        A dictionary containing the result of the interview scheduling.
    """
    return CalendarService.schedule_interview_on_google(to_email, start_time, end_time, candidate_name, role)

@mcp.tool()
def candidate_screening(resume: str, role: str) -> dict:
    """
    Hybrid candidate screening that evaluates technical skills, soft skills, and certifications
    with weighted scoring using fuzzy and semantic matching.
    """
    hr_skills = __load_hr_skills()
    role_skills = next((x["skills"] for x in hr_skills if x["role"].lower() == role.lower()), None)

    if not role_skills:
        return {"error": f"No skills found for the role: {role}"}
 
    resume_processed = __preprocess_resume(role, resume, role_skills)

    if not isinstance(resume_processed, list):
        print(f"Resume processing failed :: {resume_processed}")
        return {"error": "Resume processing failed"}

    categories = ["technical_skills", "soft_skills", "certifications"]
    results = {}
    for category in categories:
        category_data = role_skills.get(category)
        
        skill_names = []
        if isinstance(category_data, dict):
            for skills_list in category_data.values():
                if isinstance(skills_list, list):
                    skill_names.extend(skills_list)
        elif isinstance(category_data, list):
            skill_names = category_data
        matched_skills = []
        missing_skills = []
        
        # check if resume_processed has similiarity with skill_names for eg: angularjs and angular like fuzzy matching
        for skill in skill_names:
            found = False
            for resume_skill in resume_processed:
                if fuzz.ratio(skill, resume_skill) > 80:
                    matched_skills.append(skill)
                    found = True
                    break
            if not found:
                missing_skills.append(skill)    
        
        results[category] = {
            "matched_skills": matched_skills,
            "missing_skills": missing_skills
        }
    total_matched_count = (
        len(results["technical_skills"]["matched_skills"]) +
        len(results["soft_skills"]["matched_skills"]) +
        len(results["certifications"]["matched_skills"])
    )
    total_missing_count = (
        len(results["technical_skills"]["missing_skills"]) +
        len(results["soft_skills"]["missing_skills"]) +
        len(results["certifications"]["missing_skills"])
    )
    total_skills = total_matched_count + total_missing_count
    match_percentage = (total_matched_count / total_skills) * 100 if total_skills > 0 else 0

    return {
        "results": results,
        "summary": {
            "role": role,
            "total_matched": {
                "technical_skills": len(results["technical_skills"]["matched_skills"]),
                "soft_skills": len(results["soft_skills"]["matched_skills"]),
                "certifications": len(results["certifications"]["matched_skills"])},
            "total_missing": {
                "technical_skills": len(results["technical_skills"]["missing_skills"]),
                "soft_skills": len(results["soft_skills"]["missing_skills"]),
                "certifications": len(results["certifications"]["missing_skills"])},
            "match_percentage": round(match_percentage, 2)
        }   
    }


app = FastAPI(title="hr",lifespan=lambda app: mcp.session_manager.run())
app.mount("/hr", mcp.streamable_http_app())

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HR Server")
    parser.add_argument("--host", type=str, default="127.0.01", help="Host for the HR server")
    parser.add_argument("--port", type=int, default=8001, help="Port for the HR server")
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
