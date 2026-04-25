import os
import json
import time
import random
import logging
import requests
from datetime import datetime
from typing import List, Dict, Optional
from rednote_client import RednoteClient

logger = logging.getLogger(__name__)

class RednoteSeenStore:
    """
    Store for keeping track of already seen note IDs to avoid duplicate notifications.
    """
    def __init__(self, path: str):
        self.path = path
        self.seen_data = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.path):
            try:
                with open(self.path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load seen state from {self.path}: {e}")
        return {"users": {}}

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump(self.seen_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save seen state to {self.path}: {e}")

    def is_seen(self, user_id: str, note_id: str) -> bool:
        user_notes = self.seen_data.get("users", {}).get(user_id, {}).get("notes", {})
        return note_id in user_notes

    def mark_seen(self, user_id: str, note_id: str):
        if "users" not in self.seen_data:
            self.seen_data["users"] = {}
        if user_id not in self.seen_data["users"]:
            self.seen_data["users"][user_id] = {"notes": {}, "baseline_at": None}
        
        self.seen_data["users"][user_id]["notes"][note_id] = {
            "seen_at": datetime.now().isoformat()
        }
        self._save()

    def has_baseline(self, user_id: str) -> bool:
        return self.seen_data.get("users", {}).get(user_id, {}).get("baseline_at") is not None

    def set_baseline(self, user_id: str, note_ids: list):
        if "users" not in self.seen_data:
            self.seen_data["users"] = {}
        if user_id not in self.seen_data["users"]:
            self.seen_data["users"][user_id] = {"notes": {}, "baseline_at": None}
        
        now = datetime.now().isoformat()
        self.seen_data["users"][user_id]["baseline_at"] = now
        for nid in note_ids:
            if nid not in self.seen_data["users"][user_id]["notes"]:
                self.seen_data["users"][user_id]["notes"][nid] = {"seen_at": now}
        self._save()

class RednoteMonitor:
    """
    Monitor that polls multiple users and sends notifications for new notes.
    """
    def __init__(self, cookie: str, user_ids: list, webhook_url: str, state_path: str = "cache/rednote_seen.json"):
        self.client = RednoteClient(cookie)
        self.user_ids = [uid.strip() for uid in user_ids if uid.strip()]
        self.webhook_url = webhook_url
        self.store = RednoteSeenStore(state_path)

    def scan_all(self):
        """
        Scan all configured users for new notes.
        """
        logger.info(f"Starting Rednote scan for {len(self.user_ids)} users...")
        
        for user_id in self.user_ids:
            # Random delay 2-5s to reduce blocking
            delay = random.uniform(2, 5)
            logger.info(f"Waiting {delay:.1f}s before scanning user {user_id}...")
            time.sleep(delay)
            
            try:
                self.scan_user(user_id)
            except Exception as e:
                logger.error(f"Error scanning user {user_id}: {e}", exc_info=True)

    def scan_user(self, user_id: str):
        """
        Scan a single user and handle notifications.
        """
        notes = self.client.fetch_user_notes(user_id)
        if not notes:
            return

        # Handle baseline (first run)
        if not self.store.has_baseline(user_id):
            logger.info(f"Seeding baseline for user {user_id} with {len(notes)} notes.")
            self.store.set_baseline(user_id, [n['id'] for n in notes])
            return

        # Find unseen notes
        new_notes = [n for n in notes if not self.store.is_seen(user_id, n['id'])]
        
        if not new_notes:
            return

        logger.info(f"Found {len(new_notes)} new notes for user {user_id}!")
        
        # Sort oldest to newest if possible (though we don't have accurate timestamps in simple list, 
        # usually they are sorted newest first in the API response)
        # We process them in reverse to send oldest first to Discord
        for note in reversed(new_notes):
            # Fetch full content for new note
            full_content = self.client.fetch_note_content(note['id'], note.get('xsec_token', ''))
            note['content'] = full_content
            
            self.notify(note)
            self.store.mark_seen(user_id, note['id'])

    def notify(self, note: Dict):
        """
        Send notification to Discord webhook.
        """
        if not self.webhook_url:
            logger.warning("No DISCORD_WEBHOOK_URL set, skipping notification.")
            return

        # Premium looking notification
        title = note.get('title') or "新笔记"
        author = note.get('author_name') or note.get('user_id', 'Unknown博主')
        url = note.get('url', '#')
        image_url = note.get('image_url', '')
        content_text = note.get('content', '')
        
        # Max length for content snippet
        if len(content_text) > 800:
            content_text = content_text[:797] + "..."
            
        msg_header = f"🏮 **Rednote 上新了！**\n👤 **博主**: {author}\n📝 **标题**: {title}"
        if content_text:
            msg_header += f"\n📖 **正文**: {content_text}"
        
        msg_header += f"\n🔗 **链接**: {url}"
        
        payload = {
            "content": msg_header,
            "username": "Rednote Monitor",
            "embeds": []
        }
        
        if image_url:
            payload["embeds"].append({
                "image": {"url": image_url}
            })
        
        try:
            resp = requests.post(self.webhook_url, json=payload, timeout=10)
            if resp.status_code not in [200, 204]:
                logger.error(f"Failed to send webhook: {resp.status_code} {resp.text}")
            else:
                logger.info(f"Notification sent for note {note['id']}")
        except Exception as e:
            logger.error(f"Webhook notification failed: {e}")

if __name__ == "__main__":
    # Standalone test
    import os
    from dotenv import load_dotenv
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    load_dotenv()
    
    cookie = os.getenv("REDNOTE_COOKIE")
    user_ids = os.getenv("REDNOTE_MONITOR_ID_LISTS", "").split(",")
    webhook = os.getenv("DISCORD_WEBHOOK_URL")
    
    if not cookie or not user_ids[0]:
        print("Missing config")
    else:
        monitor = RednoteMonitor(cookie, user_ids, webhook)
        monitor.scan_all()
