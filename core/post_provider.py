from typing import List, Dict, Any

class PostProvider:
    """
    Supplies recent Instagram Posts & Reels for Step 1 of the ManyChat wizard.
    If Meta Graph API is connected, it fetches live media directly from Meta.
    Otherwise falls back to high-fidelity creator presets.
    """

    DEFAULT_POSTS = [
        {
            "id": "post_1",
            "url": "https://www.instagram.com/reel/C7xyz101/",
            "type": "reel",
            "thumbnail": "https://images.unsplash.com/photo-1555066931-4365d14bab8c?w=500&q=80",
            "caption": "Simple website = 20% conversion. Ek clear message, ek CTA > Price + delivery + return upar hi > 2-step checkout, guest allowed. Mobile pe 2 sec load #webdesigner #freelancelife #clientpehle",
            "likes": 47,
            "comments": 2,
            "created_at": "18 Sep, 2026"
        },
        {
            "id": "post_2",
            "url": "https://www.instagram.com/p/C7xyz102/",
            "type": "post",
            "thumbnail": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=500&q=80",
            "caption": "We build sites that actually convert. The 5 critical UI elements every landing page needs in 2026. Comment 'CONVERT' for free checklist! 🚀",
            "likes": 132,
            "comments": 14,
            "created_at": "16 Sep, 2026"
        },
        {
            "id": "post_3",
            "url": "https://www.instagram.com/reel/C7xyz103/",
            "type": "reel",
            "thumbnail": "https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=500&q=80",
            "caption": "70% of website visitors bounce in the first 3 seconds. Here is why your hero section is hurting your conversions #growth #marketing",
            "likes": 284,
            "comments": 29,
            "created_at": "14 Sep, 2026"
        },
        {
            "id": "post_4",
            "url": "https://www.instagram.com/reel/C7xyz104/",
            "type": "reel",
            "thumbnail": "https://images.unsplash.com/photo-1507238691740-187a5b1d37b8?w=500&q=80",
            "caption": "Free 2026 Freelance Growth Blueprint guide! Comment 'GUIDE' to receive it instantly in your DMs 📚",
            "likes": 512,
            "comments": 88,
            "created_at": "10 Sep, 2026"
        }
    ]

    @classmethod
    def get_recent_posts(cls, meta_client=None) -> List[Dict[str, Any]]:
        if meta_client and meta_client.config.get("enabled"):
            try:
                live_media = meta_client.get_recent_media(limit=8)
                if live_media:
                    return live_media
            except Exception:
                pass
        return cls.DEFAULT_POSTS
