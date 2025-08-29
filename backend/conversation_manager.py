from typing import Dict, Any, List

class ConversationManager:
    def __init__(self):
        self.chat_history = []
        print("Conversation Manager initialized - STATELESS MODE")
    
    def add_exchange(self, user_message: str, bot_response: str, parsed_query: Dict[str, Any]):
        """Log exchange for debugging only"""
        print(f"Query processed: '{user_message[:50]}...' -> Response generated ({len(bot_response)} chars)")
    
    def get_conversation_context(self) -> List[Dict[str, Any]]:
        """Return empty context - stateless operation"""
        return []
    
    def get_recent_ingredients_mentioned(self) -> List[str]:
        """Return empty list - stateless operation"""
        return []
    
    def has_recent_analysis(self) -> bool:
        """Return False - stateless operation"""
        return False
    
    def clear_history(self):
        """Clear history - no-op since stateless"""
        self.chat_history = []
        print("History cleared")