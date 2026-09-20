import os
import json
import logging
import requests
from typing import Dict, Any, Optional, List

logger = logging.getLogger("MetaAPI")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
META_CONFIG_FILE = os.path.join(BASE_DIR, "data", "meta_config.json")

class MetaAPIClient:
    """
    Official Meta (Facebook Developer) Graph API & Webhook Handler for Instagram:
    - Messenger API for Instagram (Send DMs, Buttons, Quick Replies)
    - Instagram Graph API (Read comments, Reply to comments, Fetch live reels)
    - Webhook Event Processor for 0-second Real-time triggers
    """

    GRAPH_API_VERSION = "v19.0"
    GRAPH_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

    def __init__(self, config_file: str = META_CONFIG_FILE):
        self.config_file = config_file
        self._ensure_file()
        self.config = self._load()

    def _ensure_file(self):
        folder = os.path.dirname(self.config_file)
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
        if not os.path.exists(self.config_file):
            default_config = {
                "enabled": False,
                "app_id": "",
                "app_secret": "",
                "access_token": "",
                "page_id": "",
                "instagram_account_id": "",
                "verify_token": "manychat_secret_token_123",
                "connected_account_name": "",
                "connected_account_username": ""
            }
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=2)

    def _load(self) -> Dict[str, Any]:
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_config(self, new_config: Dict[str, Any]) -> Dict[str, Any]:
        self.config.update(new_config)
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2)
        return self.config

    def test_connection(self, access_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Validates Access Token against Meta Graph API and retrieves Instagram business account details.
        """
        token = access_token or self.config.get("access_token")
        if not token:
            return {"success": False, "message": "No Access Token provided."}

        try:
            # 1. Fetch connected user / page details
            url = f"{self.GRAPH_URL}/me?fields=id,name,accounts{{id,name,access_token,instagram_business_account{{id,username,name,profile_picture_url}}}}&access_token={token}"
            resp = requests.get(url, timeout=10)
            data = resp.json()

            if "error" in data:
                return {
                    "success": False,
                    "error": data["error"].get("message", "Invalid token or permissions"),
                    "code": data["error"].get("code")
                }

            # Check for connected Instagram accounts
            accounts = data.get("accounts", {}).get("data", [])
            ig_accounts = []
            for page in accounts:
                ig_info = page.get("instagram_business_account")
                if ig_info:
                    ig_accounts.append({
                        "page_id": page.get("id"),
                        "page_name": page.get("name"),
                        "page_access_token": page.get("access_token"),
                        "ig_id": ig_info.get("id"),
                        "ig_username": ig_info.get("username"),
                        "ig_name": ig_info.get("name"),
                        "profile_picture": ig_info.get("profile_picture_url")
                    })

            # Also check if token is directly an Instagram User token
            if not ig_accounts and "id" in data:
                direct_url = f"{self.GRAPH_URL}/{data['id']}?fields=username,name,profile_picture_url&access_token={token}"
                d_resp = requests.get(direct_url, timeout=10).json()
                if "username" in d_resp:
                    ig_accounts.append({
                        "page_id": data.get("id"),
                        "page_name": data.get("name", "Instagram Page"),
                        "ig_id": data.get("id"),
                        "ig_username": d_resp.get("username"),
                        "ig_name": d_resp.get("name")
                    })

            if ig_accounts:
                chosen = ig_accounts[0]
                self.save_config({
                    "enabled": True,
                    "access_token": chosen.get("page_access_token") or token,
                    "page_id": chosen["page_id"],
                    "instagram_account_id": chosen["ig_id"],
                    "connected_account_name": chosen["ig_name"],
                    "connected_account_username": chosen["ig_username"]
                })
                return {
                    "success": True,
                    "message": f"Successfully connected to @{chosen['ig_username']} ({chosen['ig_name']})!",
                    "account": chosen,
                    "all_accounts": ig_accounts
                }
            else:
                return {
                    "success": False,
                    "message": "Connected to Facebook, but no Instagram Business/Creator account found linked to your Facebook Pages. Please link your Instagram account to a Facebook Page."
                }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def send_instagram_dm(self, recipient_ig_id: str, message_text: str, button_text: Optional[str] = None, button_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Sends an official Instagram DM via Meta Messenger API for Instagram.
        Supports standard text and structured buttons/quick replies.
        """
        token = self.config.get("access_token")
        page_id = self.config.get("page_id") or "me"

        if not token:
            return {"success": False, "error": "Meta Graph API token is not configured."}

        url = f"{self.GRAPH_URL}/{page_id}/messages?access_token={token}"

        # If button with URL is requested, use Generic Template
        if button_text and button_url:
            payload = {
                "recipient": {"id": recipient_ig_id},
                "message": {
                    "attachment": {
                        "type": "template",
                        "payload": {
                            "template_type": "generic",
                            "elements": [
                                {
                                    "title": message_text[:80],
                                    "subtitle": "Tap button below to access:",
                                    "buttons": [
                                        {
                                            "type": "web_url",
                                            "url": button_url,
                                            "title": button_text[:20]
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                }
            }
        else:
            payload = {
                "recipient": {"id": recipient_ig_id},
                "message": {"text": message_text}
            }

        try:
            resp = requests.post(url, json=payload, timeout=10)
            data = resp.json()
            if "error" in data:
                logger.error(f"Meta DM Error: {data['error']}")
                return {"success": False, "error": data["error"].get("message")}
            return {"success": True, "message_id": data.get("message_id")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def reply_to_comment(self, comment_id: str, reply_text: str) -> Dict[str, Any]:
        """
        Replies publicly to an Instagram Reel / Post comment via Graph API.
        """
        token = self.config.get("access_token")
        if not token:
            return {"success": False, "error": "Token not configured."}

        url = f"{self.GRAPH_URL}/{comment_id}/replies?access_token={token}"
        try:
            resp = requests.post(url, json={"message": reply_text}, timeout=10)
            data = resp.json()
            if "error" in data:
                return {"success": False, "error": data["error"].get("message")}
            return {"success": True, "reply_id": data.get("id")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_recent_media(self, limit: int = 12) -> List[Dict[str, Any]]:
        """
        Fetches live Posts and Reels directly from Instagram Graph API.
        """
        token = self.config.get("access_token")
        ig_id = self.config.get("instagram_account_id")
        if not token or not ig_id:
            return []

        url = f"{self.GRAPH_URL}/{ig_id}/media?fields=id,caption,media_type,media_url,thumbnail_url,permalink,like_count,comments_count,timestamp&limit={limit}&access_token={token}"
        try:
            resp = requests.get(url, timeout=10)
            data = resp.json()
            results = []
            for item in data.get("data", []):
                results.append({
                    "id": item.get("id"),
                    "type": "reel" if item.get("media_type") == "VIDEO" else "post",
                    "url": item.get("permalink"),
                    "thumbnail": item.get("thumbnail_url") or item.get("media_url"),
                    "caption": item.get("caption", ""),
                    "likes": item.get("like_count", 0),
                    "comments": item.get("comments_count", 0),
                    "created_at": item.get("timestamp")
                })
            return results
        except Exception as e:
            logger.error(f"Error fetching live IG media: {e}")
            return []
