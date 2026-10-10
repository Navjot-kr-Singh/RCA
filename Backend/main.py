from fastapi import FastAPI
from pydantic import BaseModel
from rca_engine import analyze_issue
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(title="Root Cause Analysis API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Query(BaseModel):
    issue: str

@app.get("/")
def home():
    return {"message": "RCA API is running 🚀"}

@app.post("/analyze")
def analyze(query: Query):
    result = analyze_issue(query.issue)
    return result