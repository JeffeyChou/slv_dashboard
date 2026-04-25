import requests
import re
import json
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class RednoteClient:
    """
    Client to fetch Rednote/Xiaohongshu user notes by scraping the profile page.
    No browser automation required, just HTTP + JSON state parsing.
    """
    
    DEFAULT_HEADERS = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "cache-control": "no-cache",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    def __init__(self, cookie: str):
        self.cookie = cookie
        self.session = requests.Session()
        self.session.headers.update(self.DEFAULT_HEADERS)
        self.session.headers["cookie"] = cookie

    def _get_url(self, url: str) -> Optional[str]:
        """
        Fetch URL content using requests session with a fallback to curl if blocked.
        """
        # Attempt 1: Requests
        try:
            headers = {"Referer": "https://www.rednote.com/"}
            response = self.session.get(url, timeout=15, headers=headers)
            if response.ok and "window.__INITIAL_STATE__" in response.text:
                return response.text
        except Exception as e:
            logger.warning(f"Requests failed for {url}: {e}")

        # Attempt 2: Curl Fallback (often bypasses TLS fingerprinting blocks)
        try:
            import subprocess
            logger.info(f"Falling back to curl for {url}")
            cmd = [
                "curl", "-s", "-L",
                "-H", f"User-Agent: {self.DEFAULT_HEADERS['user-agent']}",
                "-H", f"Cookie: {self.cookie}",
                "-H", "Referer: https://www.rednote.com/",
                url
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            if result.returncode == 0 and "window.__INITIAL_STATE__" in result.stdout:
                return result.stdout
        except Exception as e:
            logger.error(f"Curl fallback failed for {url}: {e}")
            
        return None

    def fetch_user_notes(self, user_id: str) -> List[Dict]:
        """
        Fetch notes for a specific user from rednote.com.
        """
        url = f"https://www.rednote.com/user/profile/{user_id}"
        errors = []
        import time
        import random
        
        for attempt in range(3):
            if attempt > 0:
                time.sleep(random.uniform(2, 4))
            
            html = self._get_url(url)
            if html:
                notes = self._extract_notes_from_html(html, user_id)
                if notes:
                    return notes
            
            errors.append(f"Attempt {attempt+1} failed to find notes at {url}")
        
        logger.error(f"Failed to fetch notes for user {user_id}. Errors: {errors}")
        return []

    def fetch_note_content(self, note_id: str, xsec_token: str) -> str:
        """
        Fetch the full text content of a specific note.
        """
        url = f"https://www.rednote.com/explore/{note_id}?xsec_token={xsec_token}&xsec_source=pc_user"
        try:
            html = self._get_url(url)
            if not html:
                return ""
            
            # Extract INITIAL_STATE
            match = re.search(r'<script>window\.__INITIAL_STATE__=(.*?)</script>', html, re.S)
            if not match:
                return ""
            
            state_str = match.group(1).strip()
            if state_str.endswith(';'):
                state_str = state_str[:-1]
            state_str = state_str.replace('undefined', 'null')
            state = json.loads(state_str)
            
            # Navigate to note['noteDetailMap'][note_id]['note']['desc']
            note_detail_map = state.get('note', {}).get('noteDetailMap', {})
            note_data = note_detail_map.get(note_id, {}).get('note', {})
            desc = note_data.get('desc', '')
            
            return desc
        except Exception as e:
            logger.error(f"Error fetching note content: {e}")
            return ""

    def _extract_notes_from_html(self, html: str, user_id: str) -> List[Dict]:
        """
        Extract window.__INITIAL_STATE__ from HTML and parse notes.
        """
        # Match <script>window.__INITIAL_STATE__={...}</script>
        # Note: Sometimes it's window.__INITIAL_STATE__=JSON.parse("...")
        match = re.search(r'<script>window\.__INITIAL_STATE__=(.*?)</script>', html, re.S)
        if not match:
            return []
        
        state_str = match.group(1).strip()
        
        # Cleanup case where it might end with a semicolon or more JS
        if state_str.endswith(';'):
            state_str = state_str[:-1]
            
        try:
            state_str = state_str.replace('undefined', 'null')
            state = json.loads(state_str)
            
            # Navigate to state['user']['notes']
            # Based on reference/xhs_monitor/src/core/xhs/xhs-client.ts:198
            user_state = state.get('user', {})
            notes_data = user_state.get('notes', [])
            
            # Extract博主昵称 from userPageData or note
            user_page_data = user_state.get('userPageData', {})
            nickname = user_page_data.get('basicInfo', {}).get('nickname')
            
            # The structure for user profile notes is often a nested list [[note1, note2...]]
            # We flatten it.
            flattened_notes = []
            if isinstance(notes_data, list):
                for item in notes_data:
                    if isinstance(item, list):
                        flattened_notes.extend(item)
                    else:
                        flattened_notes.append(item)
            
            normalized_notes = []
            for note in flattened_notes:
                try:
                    norm = self._normalize_note(note, user_id, nickname)
                    if norm:
                        normalized_notes.append(norm)
                except Exception as e:
                    logger.warning(f"Failed to normalize note: {e}")
            
            if not normalized_notes and flattened_notes:
                logger.warning(f"Extracted {len(flattened_notes)} raw notes but none could be normalized for user {user_id}")
                    
            return normalized_notes
                    
        except Exception as e:
            logger.error(f"Failed to parse INITIAL_STATE for user {user_id}: {e}")
            return []

    def _normalize_note(self, note: Dict, fallback_user_id: str, nickname: Optional[str] = None) -> Optional[Dict]:
        """
        Filter and normalize note data.
        """
        # Common fields in both API and HTML state
        note_id = note.get('note_id') or note.get('noteId') or note.get('id')
        if not note_id:
            return None
        
        note_card = note.get('noteCard') or note.get('note_card') or {}
        user = note_card.get('user') or note.get('user') or {}
        
        # xsec_token is crucial for the URL
        xsec_token = note.get('xsecToken') or note.get('xsec_token') or note_card.get('xsecToken') or ""
        
        # Better title extraction: check multiple nested fields and case variations
        title = (
            note.get('displayTitle') or 
            note.get('display_title') or 
            note.get('title') or 
            note_card.get('displayTitle') or 
            note_card.get('display_title') or 
            note_card.get('title') or
            note.get('desc') or
            note_card.get('desc') or
            "Untitled"
        )
        
        # Clean up title (remove newlines/excess space)
        title = " ".join(title.split()).strip()
        if len(title) > 80:
            title = title[:77] + "..."

        # Image extraction
        cover = note_card.get('cover') or note.get('cover') or {}
        image_url = ""
        info_list = cover.get('infoList') or cover.get('info_list', [])
        if info_list and len(info_list) > 0:
            # Prefer first image in list
            image_url = info_list[0].get('url', '')
        if not image_url:
            image_url = cover.get('urlDefault') or cover.get('url_default') or cover.get('url', '')

        # User nickname
        author_name = nickname or user.get('nickname') or user.get('nickName') or fallback_user_id
        
        # URL construction
        base_url = "https://www.xiaohongshu.com/explore"
        url = f"{base_url}/{note_id}"
        if xsec_token:
            url += f"?xsec_token={xsec_token}&xsec_source=pc_user"
            
        return {
            "id": note_id,
            "user_id": user.get('userId') or user.get('user_id') or fallback_user_id,
            "author_name": author_name,
            "title": title,
            "url": url,
            "image_url": image_url,
            "type": note_card.get('type') or note.get('type', 'normal'),
            "xsec_token": xsec_token
        }

if __name__ == "__main__":
    # Quick standalone test
    import os
    from dotenv import load_dotenv
    
    logging.basicConfig(level=logging.INFO)
    load_dotenv()
    
    cookie = os.getenv("REDNOTE_COOKIE")
    user_ids = os.getenv("REDNOTE_MONITOR_ID_LISTS", "").split(",")
    
    if not cookie or not user_ids[0]:
        print("Missing REDNOTE_COOKIE or REDNOTE_MONITOR_ID_LISTS in .env")
    else:
        client = RednoteClient(cookie)
        for uid in user_ids:
            uid = uid.strip()
            if not uid: continue
            print(f"\n--- Testing User: {uid} ---")
            notes = client.fetch_user_notes(uid)
            print(f"Found {len(notes)} notes")
            for n in notes[:3]:
                print(f" - [{n['id']}] {n['title']} -> {n['url']}")
