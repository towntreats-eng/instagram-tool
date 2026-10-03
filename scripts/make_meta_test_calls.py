"""
Helper script to execute test API calls against Meta / Instagram Graph API
to satisfy Meta App Review's "1 API call required" testing prerequisites.
"""

import os
import sys
import json
import urllib.request
import urllib.error
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import store


CONFIG_FILE = "data/meta_config.json"

def main():
    if not store.exists(CONFIG_FILE):
        print(f"Error: {CONFIG_FILE} not found.")
        return
    
    config = store.read(CONFIG_FILE)
    token = config.get("access_token")
    if not token:
        print("Error: No access_token found in data/meta_config.json.")
        return

    print("Found access token. Starting Meta Graph API test calls...\n")

    endpoints = [
        # instagram_basic / instagram_business_basic
        ("instagram_basic (User Profile)", 
         f"https://graph.instagram.com/v21.0/me?fields=id,username,account_type,media_count&access_token={token}"),
        
        # instagram_business_manage_insights
        ("instagram_business_manage_insights (Profile Insights)", 
         f"https://graph.instagram.com/v21.0/me/insights?metric=reach,follower_count,profile_views&period=day&access_token={token}"),
        
        # instagram_business_manage_messages / conversations
        ("instagram_business_manage_messages (Conversations)", 
         f"https://graph.instagram.com/v21.0/me/conversations?fields=id,updated_time&access_token={token}"),
        
        # instagram_business_manage_comments / media
        ("instagram_business_manage_comments (Media List)", 
         f"https://graph.instagram.com/v21.0/me/media?fields=id,caption,timestamp&limit=5&access_token={token}"),
    ]

    # Try fetching media ID to query comments
    media_url = f"https://graph.instagram.com/v21.0/me/media?fields=id&limit=1&access_token={token}"
    try:
        with urllib.request.urlopen(media_url) as r:
            media_data = json.loads(r.read().decode())
            items = media_data.get("data", [])
            if items:
                mid = items[0]["id"]
                endpoints.append(
                    ("instagram_business_manage_comments (Media Comments)",
                     f"https://graph.instagram.com/v21.0/{mid}/comments?access_token={token}")
                )
    except Exception:
        pass

    results = []
    for name, url in endpoints:
        print(f"Testing [{name}]...")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "DMFlow-Tester"})
            with urllib.request.urlopen(req, timeout=15) as res:
                body = json.loads(res.read().decode())
                print(f"  [SUCCESS 200 OK]")
                results.append((name, True, "HTTP 200 OK"))
        except urllib.error.HTTPError as exc:
            err_msg = ""
            try:
                err_msg = json.loads(exc.read().decode()).get("error", {}).get("message")
            except Exception:
                err_msg = f"HTTP {exc.code}"
            print(f"  [FAILED {exc.code}]: {err_msg}")
            results.append((name, False, err_msg))
        except Exception as exc:
            print(f"  [ERROR]: {exc}")
            results.append((name, False, str(exc)))

    print("\n" + "="*50)
    print("Summary of Test Calls:")
    for name, ok, note in results:
        status = "PASSED" if ok else "FAILED"
        print(f" - {name}: {status} ({note})")
    print("="*50)
    print("\nNote: Meta Developer Dashboard updates test call metrics within 5-15 minutes.")

if __name__ == "__main__":
    main()
