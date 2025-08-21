import json
import os
from typing import Dict, List, Optional
from datetime import datetime

class MemoryService:
    def __init__(self, storage_path: str = "memory.json"):
        self.storage_path = storage_path
        self.memory = self._load_memory()
    
    def _load_memory(self) -> Dict:
        """Load memory from storage"""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "processed_emails": {},
            "conversations": {},
            "entities": {}
        }
    
    def _save_memory(self):
        """Save memory to storage"""
        try:
            with open(self.storage_path, 'w') as f:
                json.dump(self.memory, f, indent=2)
        except Exception as e:
            print(f"Error saving memory: {e}")
    
    def is_email_processed(self, email_id: str) -> bool:
        """Check if email has been processed"""
        return email_id in self.memory["processed_emails"]
    
    def mark_email_processed(self, email_id: str, thread_id: str):
        """Mark email as processed"""
        self.memory["processed_emails"][email_id] = {
            "processed_at": datetime.now().isoformat(),
            "thread_id": thread_id
        }
        self._save_memory()
    
    def get_conversation_context(self, thread_id: str) -> Optional[str]:
        """Get conversation context for a thread"""
        if thread_id in self.memory["conversations"]:
            conv = self.memory["conversations"][thread_id]
            return f"Previous conversation about: {conv.get('topic', 'unknown')}. Last interaction: {conv.get('last_interaction', 'unknown')}"
        return None
    
    def update_conversation(self, thread_id: str, email_content: str, response: str):
        """Update conversation history"""
        # Extract basic topic from email content
        topic = "general inquiry"
        if "meeting" in email_content.lower():
            topic = "scheduling"
        elif "question" in email_content.lower():
            topic = "questions"
        elif "project" in email_content.lower():
            topic = "project discussion"
        
        self.memory["conversations"][thread_id] = {
            "topic": topic,
            "last_interaction": datetime.now().isoformat(),
            "last_email_snippet": email_content[:100] + "..." if len(email_content) > 100 else email_content
        }
        self._save_memory()