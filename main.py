"""
Main entry point alias for ConverFlow / Instagram Tool.
Re-exports the FastAPI 'app' instance from app.py so both
'uvicorn main:app' and 'uvicorn app:app' work seamlessly.
"""
import os
from app import app

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run("main:app", host=host, port=port, reload=False)
