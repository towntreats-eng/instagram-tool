"""
Main entry point alias for ConverFlow / Instagram Tool.
Re-exports the FastAPI 'app' instance from app.py so both
'uvicorn main:app' and 'uvicorn app:app' work seamlessly.
"""
from app import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
