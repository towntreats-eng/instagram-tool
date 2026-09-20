import sys
import time
import webbrowser
import threading
import uvicorn

def open_browser():
    time.sleep(1.8)
    print("\n✨ Opening ConverFlow in your browser...")
    webbrowser.open("http://localhost:8000")

if __name__ == "__main__":
    print("=" * 62)
    print("  ConverFlow - Instagram Automation, CRM & Outreach Suite")
    print("=" * 62)
    print("  Landing page  ->  http://localhost:8000/")
    print("  Pricing       ->  http://localhost:8000/pricing")
    print("  Sign up       ->  http://localhost:8000/signup")
    print("  Dashboard     ->  http://localhost:8000/app")
    print("  Admin console ->  http://localhost:8000/admin")
    print("-" * 62)
    print("  Press Ctrl + C in this window to stop the server.")
    print("=" * 62)

    # Launch browser automatically
    threading.Thread(target=open_browser, daemon=True).start()

    # Start FastAPI server via uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False, log_level="info")
