"""DM Flow - production entry point (Railway runs this)."""
import os

from dmflow.web import app  # noqa: F401

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("dmflow.web:app", host=os.environ.get("HOST", "0.0.0.0"),
                port=int(os.environ.get("PORT", 8000)), proxy_headers=True, forwarded_allow_ips="*")
