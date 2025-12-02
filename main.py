from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from auth.user_routes import router as user_router
from index_routes import router as index_router

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(user_router)
app.include_router(index_router)

if __name__ == "__main__":
    import uvicorn
    # Mount static files
    app.mount("/", StaticFiles(directory="static", html=True), name="static")
    uvicorn.run(app, host="0.0.0.0", port=8000)