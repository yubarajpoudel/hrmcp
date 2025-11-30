import requests
import json
import re
from typing import Dict, Optional

class OllamaExtractor:
    def __init__(self, base_url="http://localhost:11434"):
        self.base_url = base_url
    
    def extract_data(self, prompt_text: str, model="phi3:mini"):
        response = requests.post(
            f"{self.base_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt_text,
                "stream": False,
                "options": {"temperature": 0.0}
            }
        )
        
        return clean_json_response(response.json()["response"])


def clean_json_response(response_text):
    """
    Clean and parse JSON from Ollama response
    """
    # Remove any code block markers
    cleaned = re.sub(r'```json\s*', '', response_text)
    cleaned = re.sub(r'\s*```', '', cleaned)
    
    # Remove any text before or after JSON
    json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if json_match:
        cleaned = json_match.group(0)
    
    # Clean common JSON issues
    cleaned = cleaned.replace('0.5,', '')  # Remove malformed line
    cleaned = cleaned.strip()
    
    decoder = json.JSONDecoder()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to fix trailing commas first
        cleaned = re.sub(r',\s*}', '}', cleaned)
        cleaned = re.sub(r',\s*]', ']', cleaned)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Attempt to locate the first JSON object inside the text
            for match in re.finditer(r'\{', cleaned):
                start = match.start()
                try:
                    obj, _ = decoder.raw_decode(cleaned[start:])
                    return obj
                except json.JSONDecodeError:
                    continue
            print("JSON parse error: Could not parse response")
            print(f"Raw response: {response_text=}")
            return response_text