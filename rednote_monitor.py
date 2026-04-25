import os
import json
import time
import random
import logging
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from rednote_client import RednoteClient

logger = logging.getLogger(__name__)


class RednotePostIndex:
    """
    Rich post index that tracks metadata (timestamps, position, title) for each note.
    Replaces the simpler RednoteSeenStore with auto-migration from the old format.
    """
    def __init__(self, path: str):
        self.path = path
        self.data = self._load()

    def _load(self) -> dict:
        # Try new format first
        if os.path.exists(self.path):
            try:
                with open(self.path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if data.get("version") == 2:
                    return data
            except Exception as e:
                logger.error(f"Failed to load post index from {self.path}: {e}")

        # Fall back to old rednote_seen.json format and migrate
        old_path = os.path.join(os.path.dirname(self.path), "rednote_seen.json")
        if os.path.exists(old_path):
            try:
                with open(old_path, 'r', encoding='utf-8') as f:
                    old_data = json.load(f)
                logger.info(f"Migrating from {old_path} to {self.path}")
                return self._migrate_v1(old_data)
            except Exception as e:
                logger.error(f"Failed to migrate from {old_path}: {e}")

        return {"version": 2, "users": {}}

    def _migrate_v1(self, old_data: dict) -> dict:
        """Migrate v1 (rednote_seen.json) format to v2 (rednote_posts.json)."""
        new_data = {"version": 2, "users": {}}
        for user_id, user_info in old_data.get("users", {}).items():
            new_notes = {}
            for note_id, note_info in user_info.get("notes", {}).items():
                seen_at = note_info.get("seen_at")
                new_notes[note_id] = {
                    "first_seen_at": seen_at,
                    "last_seen_at": seen_at,
                    "published_at": None,
                    "title": None,
                    "position": None
                }
            new_data["users"][user_id] = {
                "baseline_at": user_info.get("baseline_at"),
                "notes": new_notes
            }
        return new_data

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save post index to {self.path}: {e}")

    def is_seen(self, user_id: str, note_id: str) -> bool:
        return note_id in self.data.get("users", {}).get(user_id, {}).get("notes", {})

    def mark_seen(self, user_id: str, note: dict):
        """Mark a note as seen, storing its metadata."""
        if "users" not in self.data:
            self.data["users"] = {}
        if user_id not in self.data["users"]:
            self.data["users"][user_id] = {"notes": {}, "baseline_at": None}

        now = datetime.now().isoformat()
        note_id = note["id"]
        existing = self.data["users"][user_id]["notes"].get(note_id)

        self.data["users"][user_id]["notes"][note_id] = {
            "first_seen_at": existing["first_seen_at"] if existing else now,
            "last_seen_at": now,
            "published_at": note.get("published_at"),
            "title": note.get("title"),
            "position": note.get("position")
        }
        self._save()

    def has_baseline(self, user_id: str) -> bool:
        return self.data.get("users", {}).get(user_id, {}).get("baseline_at") is not None

    def set_baseline(self, user_id: str, notes: list):
        """Set baseline with full note metadata."""
        if "users" not in self.data:
            self.data["users"] = {}
        if user_id not in self.data["users"]:
            self.data["users"][user_id] = {"notes": {}, "baseline_at": None}

        now = datetime.now().isoformat()
        self.data["users"][user_id]["baseline_at"] = now
        for note in notes:
            nid = note["id"]
            if nid not in self.data["users"][user_id]["notes"]:
                self.data["users"][user_id]["notes"][nid] = {
                    "first_seen_at": now,
                    "last_seen_at": now,
                    "published_at": note.get("published_at"),
                    "title": note.get("title"),
                    "position": note.get("position")
                }
        self._save()

    def is_likely_sticky(self, note: dict, all_notes: list, threshold_days: int = 7) -> bool:
        """
        Detect if a note is likely sticky/pinned.
        A post is sticky if its published_at is significantly older than the newest post.
        """
        note_time = note.get("published_at")
        if not note_time:
            return False

        try:
            note_dt = datetime.fromisoformat(note_time)
        except ValueError:
            return False

        other_times = []
        for n in all_notes:
            t = n.get("published_at")
            if t and n["id"] != note["id"]:
                try:
                    other_times.append(datetime.fromisoformat(t))
                except ValueError:
                    continue

        if not other_times:
            return False

        newest = max(other_times)
        return (newest - note_dt) > timedelta(days=threshold_days)

class RednoteMonitor:
    """
    Monitor that polls multiple users and sends notifications for new notes.
    """
    def __init__(self, cookie: str, user_ids: list, webhook_url: str, state_path: str = "cache/rednote_posts.json"):
        self.client = RednoteClient(cookie)
        self.user_ids = [uid.strip() for uid in user_ids if uid.strip()]
        self.webhook_url = webhook_url
        self.store = RednotePostIndex(state_path)

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

        # Annotate position in the fetched list
        for idx, note in enumerate(notes):
            note['position'] = idx

        # Handle baseline (first run)
        if not self.store.has_baseline(user_id):
            logger.info(f"Seeding baseline for user {user_id} with {len(notes)} notes.")
            self.store.set_baseline(user_id, notes)
            return

        # Find unseen notes
        new_notes = [n for n in notes if not self.store.is_seen(user_id, n['id'])]

        if not new_notes:
            return

        # Filter out sticky/pinned posts
        genuinely_new = []
        for note in new_notes:
            if self.store.is_likely_sticky(note, notes):
                logger.info(f"Skipping likely sticky post {note['id']} (old timestamp at top of feed)")
                self.store.mark_seen(user_id, note)
            else:
                genuinely_new.append(note)

        if not genuinely_new:
            return

        logger.info(f"Found {len(genuinely_new)} new notes for user {user_id}!")

        # Process oldest first (notes are typically newest-first from API)
        for note in reversed(genuinely_new):
            detail = self.client.fetch_note_content(note['id'], note.get('xsec_token', ''))
            note['content'] = detail['content']
            # Prefer authoritative timestamp from detail page over note-ID-derived one
            if detail['published_at']:
                note['published_at'] = detail['published_at']

            self.notify(note)
            self.store.mark_seen(user_id, note)

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
