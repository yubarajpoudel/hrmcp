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

UPLOAD_DIR = "./uploads/"
os.makedirs(UPLOAD_DIR, exist_ok=True)
FIREBASE_ML_API_KEY = os.getenv("FIREBASE_ML_API_KEY", "").strip()
FIREBASE_ML_ENDPOINT = "https://vision.googleapis.com/v1/images:annotate"

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

@app.post("/mcp/hr/candidate_screening")
async def cand_screening(file: UploadFile = File(...), role: str = Form(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")
    
    file_path = f"{UPLOAD_DIR}/{file.filename}"
    
    file_bytes = await file.read()
    async with aiofiles.open(file_path, "wb") as buffer:
        await buffer.write(file_bytes)
    
    if file.filename.lower().endswith(".pdf"):
        resume_text = await __extract_text_from_pdf(file_bytes)
    elif file.filename.lower().endswith((".png", ".jpg", ".jpeg")):
        resume_text = await extract_text_from_image(file_path)
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type")
    print(f"""role:: {role}""")
    result = hrserver.candidate_screening(resume_text, role)
    return result