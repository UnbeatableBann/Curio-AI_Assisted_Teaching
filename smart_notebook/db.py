from typing import List, Optional, Dict
from supabase import create_client, Client
from autonomous.config.settings import settings
from autonomous.config.logger import get_logger


logger = get_logger("curio.smart_notebook.db")


class SmartNotebookDB:
    def __init__(self):
        self.client: Optional[Client] = None
        if settings.SUPABASE_URL and settings.SUPABASE_KEY:
            try:
                self.client = create_client(
                    settings.SUPABASE_URL, settings.SUPABASE_KEY
                )
            except Exception as e:
                logger.error(f"Failed to initialize Supabase client for Notebook: {e}")
        else:
            logger.warning("Supabase URL or Key not found in settings for Notebook.")

    def save_note(self, note: Dict) -> Optional[Dict]:
        if not self.client:
            return None
        try:
            # Assuming table name 'smart_notes'
            response = self.client.table("smart_notes").insert(note).execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error saving note: {e}")
            return None

    def get_all_notes(self) -> List[Dict]:
        if not self.client:
            return []
        try:
            response = (
                self.client.table("smart_notes")
                .select("*")
                .order("created_at", desc=False)
                .execute()
            )
            return response.data if response.data else []
        except Exception as e:
            logger.error(f"Error fetching notes: {e}")
            return []


notebook_db = SmartNotebookDB()
