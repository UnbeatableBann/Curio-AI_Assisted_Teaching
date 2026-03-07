from typing import Dict, Optional

from supabase import create_client, Client

from autonomous.config.settings import settings
from autonomous.config.logger import get_logger
from autonomous.brain.brain_state import BrainState

logger = get_logger("curio.brain.db")


class BrainDB:
    def __init__(self):
        self.client: Optional[Client] = None

        if settings.SUPABASE_URL and settings.SUPABASE_KEY:
            try:
                self.client = create_client(
                    settings.SUPABASE_URL, settings.SUPABASE_KEY
                )
            except Exception as e:
                logger.error(f"Failed to initialize Supabase client: {e}")
        else:
            logger.warning("Supabase URL or Key not found in settings.")

    def save_state(self, state: BrainState) -> Optional[Dict]:
        """
        Saves the current brain state to the Supabase 'brain_table'.
        Extracts specific fields as requested:
        current_transcript_summary, current_subtopic, current_topic,
        past_subtopics, past_topics, past_summaries.
        """
        if not self.client:
            logger.error("Supabase client not initialized. Cannot save state.")
            return None

        try:
            # Extract relevant fields
            current_context = state.context or {}

            response = (
                self.client.table("brain_memory")
                .insert(
                    {
                        "current_transcript_summary": current_context.get(
                            "current_transcript_summary"
                        ),
                        "current_subtopic": current_context.get("current_subtopic"),
                        "current_topic": current_context.get("current_topic"),
                        "past_subtopics": state.past_subtopics,
                        "past_topics": state.past_topics,
                        "past_summaries": state.past_summaries,
                    }
                )
                .execute()
            )

            # response.data contains the inserted row(s)
            if response.data:
                logger.info(
                    f"Saved brain state to Supabase: {len(response.data)} row(s)"
                )
                return response.data[0]
            else:
                logger.warning("Supabase insert returned no data.")
                return None

        except Exception as e:
            logger.error(f"Error saving state to Supabase: {e}")
            return None

    def get_latest_state(self) -> Optional[Dict]:
        """
        Fetches the latest brain state from Supabase.
        """
        if not self.client:
            return None
        try:
            # Assuming 'created_at' or similar timestamp exists.
            # If not, we rely on natural order or 'id' desc.
            response = (
                self.client.table("brain_memory")
                .select("*")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching latest state: {e}")
            return None


# Singleton instance
brain_db = BrainDB()
