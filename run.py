"""Run DM Flow on this computer: python run.py  ->  http://localhost:8000

Uses a local SQLite file (data/dmflow.db) unless DATABASE_URL is set.
"""
import os
import threading
import time
import webbrowser

os.environ.setdefault("COOKIE_SECURE", "0")   # plain http on localhost

if __name__ == "__main__":
    import uvicorn
    threading.Thread(target=lambda: (time.sleep(1.5), webbrowser.open("http://localhost:8000")), daemon=True).start()
    print("DM Flow -> http://localhost:8000   (admin: /admin)   Ctrl+C to stop")
    uvicorn.run("dmflow.web:app", host="127.0.0.1", port=8000)
