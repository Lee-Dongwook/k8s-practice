from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return { "message": "Hello Kubernetes Lab - v2" }

@app.get("/health")
def health_check():
    return { "status": "healthy" }
