from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from auth.user_routes import router as user_router
from index_routes import router as index_router
from middleware import GlobalMiddleWare
import os

app = FastAPI()

origins = [
    "http://localhost:8000",
    "http://127.0.0.1:8000"
]

app.add_middleware(GlobalMiddleWare)    
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "./uploads/"
os.makedirs(UPLOAD_DIR, exist_ok=True)


app.include_router(user_router)
app.include_router(index_router)

if __name__ == "__main__":
    import uvicorn
    # Mount static files
    app.mount("/", StaticFiles(directory="static", html=True), name="static")
    uvicorn.run(app, host="0.0.0.0", port=8000)