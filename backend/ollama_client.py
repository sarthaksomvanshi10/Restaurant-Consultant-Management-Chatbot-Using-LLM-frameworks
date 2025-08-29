import httpx
import json
from typing import Dict, Any, List

class OllamaClient:
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.client = httpx.AsyncClient(timeout=30.0)
        print(f"Ollama LLM Parser initialized with {self.model}")
    
    async def parse_query(self, user_input: str, conversation_history: List[Dict]) -> Dict[str, Any]:
        """Parse natural language query using Ollama LLM as required"""
        try:
            prompt = self._create_parsing_prompt(user_input)
            response = await self._call_ollama(prompt)
            parsed_data = self._extract_json_from_response(response)
            return parsed_data
            
        except Exception as e:
            print(f"Error parsing query with Ollama: {e}")
            return self._create_default_response()
    
    def _create_parsing_prompt(self, user_input: str) -> str:
        """Create parsing prompt for Ollama LLM"""
        return f"""Parse restaurant query into JSON.

Query: "{user_input}"

Classification rules:
- If query mentions "delayed", "late", "shipment", "delivery" → query_type is "delay"
- If query mentions "increased", "price up", "cost more" → query_type is "price_shock" 
- If query asks about category breakdown → query_type is "category_query"

Ingredient mapping:
- "tomatoes" or "tomato" → "tomato_sauce"
- "flour" → "00_flour" 
- "mozzarella" → "mozzarella_fior_di_latte"
- "prosciutto" → "prosciutto_crudo"

JSON format:
{{
  "price_shocks": [{{"ingredient": "name", "pct": number}}],
  "delays": [{{"ingredient": "name", "extra_days": number}}],
  "assumptions": {{"lead_time_threshold_days": 5}},
  "query_type": "price_shock" | "delay" | "category_query" | "general",
  "category_filter": "pasta" | "pinsa" | "salad" | null,
  "user_intent": "brief description"
}}"""
    
    async def _call_ollama(self, prompt: str) -> str:
        """Call Ollama API"""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
                "num_predict": 200
            }
        }
        
        response = await self.client.post(
            f"{self.base_url}/api/generate",
            json=payload
        )
        response.raise_for_status()
        
        result = response.json()
        return result.get("response", "")
    
    def _extract_json_from_response(self, response: str) -> Dict[str, Any]:
        """Extract JSON from LLM response"""
        try:
            # Find JSON in response
            start_idx = response.find('{')
            end_idx = response.rfind('}')
            
            if start_idx != -1 and end_idx != -1:
                json_str = response[start_idx:end_idx+1]
                parsed = json.loads(json_str)
                
                # Validate structure
                if self._validate_structure(parsed):
                    print(f"Successfully parsed: {parsed}")
                    return parsed
            
            # If parsing fails, return default
            return self._create_default_response()
            
        except json.JSONDecodeError:
            print(f"JSON decode error from response: {response}")
            return self._create_default_response()
    
    def _validate_structure(self, data: Dict[str, Any]) -> bool:
        """Validate parsed JSON structure"""
        required_keys = ["price_shocks", "delays", "assumptions", "query_type"]
        return all(key in data for key in required_keys)
    
    def _create_default_response(self) -> Dict[str, Any]:
        """Default response when parsing fails"""
        return {
            "price_shocks": [],
            "delays": [],
            "assumptions": {"lead_time_threshold_days": 5},
            "query_type": "general",
            "category_filter": None,
            "user_intent": "general query"
        }
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()