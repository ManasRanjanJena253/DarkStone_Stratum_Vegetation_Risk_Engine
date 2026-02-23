from fastapi import FastAPI
from fastapi import Form, File, UploadFile, HTTPException

app = FastAPI()

@app.get("/health")
def api_health():
    return {"Status": HTTPException(status_code = 200)}