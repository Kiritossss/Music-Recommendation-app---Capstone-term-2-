from fastapi import FastAPI
from backend.routes import youtube, auth  # ✅ both imported

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ make sure these match the actual router files
app.include_router(auth.router, prefix="/api/auth")
app.include_router(youtube.router)

@app.get("/")
def home():
    return {"message": "OmniTune Backend is live!"}

@app.on_event("startup")
async def list_routes():
    for route in app.routes:
        print("🛣️", route.path)

