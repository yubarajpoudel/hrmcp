from fastapi import FastAPI, UploadFile, File, Form, HTTPException
app = FastAPI()
import shutil
import aiofiles
import fitz  # PyMuPDF
import pytesseract
from PIL import Image, ImageFilter, ImageOps
from hrmcpserver import hrserver
import os
import base64
import httpx
from typing import List, Optional
import ollama

UPLOAD_DIR = "./uploads/"
os.makedirs(UPLOAD_DIR, exist_ok=True)
FIREBASE_ML_API_KEY = os.getenv("FIREBASE_ML_API_KEY", "").strip()
FIREBASE_ML_ENDPOINT = "https://vision.googleapis.com/v1/images:annotate"

async def extract_text_with_firebase_ml(
    image_path: str,
    language_hints: Optional[List[str]] = None,
) -> str:
    """
    Use Firebase ML (backed by Google Cloud Vision API) to extract text from an image.
    Requires FIREBASE_ML_API_KEY environment variable to be set.
    """
    if not FIREBASE_ML_API_KEY:
        raise RuntimeError(
            "FIREBASE_ML_API_KEY is not configured; cannot use Firebase ML OCR."
        )

    try:
        async with aiofiles.open(image_path, "rb") as image_file:
            image_bytes = await image_file.read()
        encoded_image = base64.b64encode(image_bytes).decode("utf-8")

        request_body = {
            "requests": [
                {
                    "image": {"content": encoded_image},
                    "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
                }
            ]
        }

        if language_hints:
            request_body["requests"][0]["imageContext"] = {
                "languageHints": language_hints
            }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{FIREBASE_ML_ENDPOINT}?key={FIREBASE_ML_API_KEY}",
                json=request_body,
            )
            response.raise_for_status()

        response_json = response.json()
        annotations = response_json.get("responses", [{}])[0].get(
            "fullTextAnnotation", {}
        )
        return annotations.get("text", "").strip()

    except Exception as exc:
        print(f"Error using Firebase ML OCR for {image_path}: {exc}")
        return ""

async def __extract_text_from_pdf(resume_bytes: bytes) -> str:
    doc_stream = fitz.open(stream=resume_bytes, filetype="pdf")
    text = ""
    for page in doc_stream:
        text += page.get_text()
    return text

@app.get("/")
async def read_root():
    return {"Hello": "World"}

@app.post("/chat")
async def chat(message: str = Form(...)):
    """
    Chat endpoint for HR management
     - this will accept the input from the user as a plain text, plan the action with the ollama model to execute the available tools
     - this will call the right tool based on the plan and return the result as the plain text
    """
    """ System prompt to inform the model about the tool is usage """
    system_message = {
        "role": "system", 
        "content": f""" You are a HR management assistant. You can do following actions:
                   - read or extract text from image using 'mcp/hr/read_resume_from_file' 
                   - candidate screening or review cv using 'mcp/hr/candidate_screening'
                   - can get available time slots using 'mcp/hr/get_interviewer_free_time' and 
                   - can schedule an interview using 'mcp/hr/schedule_interview' if needed."""
    }
    # User asks a question that involves a calculation
    user_message = {
        "role": "user", 
        "content": message
    }
    messages = [system_message, user_message]
    available_tools = [ hrserver.read_resume_from_file, hrserver.candidate_screening, hrserver.get_interviewer_free_time , hrserver.schedule_interview]
    
    response = ollama.chat(
        model="llama3.2",
        messages=messages,
        tools=available_tools,
    )
    tool_map = {tool.__name__: tool for tool in available_tools}
    for tool_call in (response.message.tool_calls or []):
        print("toosl called {} with argument {}".format(tool_call.function.name, tool_call.function.arguments))
        func = tool_map.get(tool_call.function.name)
        if func:
            result = func(**tool_call.function.arguments)
            messages.append({"role": "assistant", "content": f"The result is {result}."})
            follow_up = ollama.chat(model='llama3.2', messages=messages)
            return {"result": follow_up.message.content}
    return {"result": response.message.content}

@app.post("/upload")
async def upload_file(file: UploadFile = File(...), role: str = Form(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")
    
    file_path = f"{UPLOAD_DIR}/{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {"info": "File saved successfully", "file_path": file_path , "role": role}