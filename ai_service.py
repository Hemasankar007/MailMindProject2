import os
import requests
import json
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import time

load_dotenv()

class AIService:
    def __init__(self):
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "your_gemini_api_key_here")
        self.preferred_model = "gemini-1.5-flash"
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_expiry = 3600  # Cache expires after 1 hour

    def set_api_keys(self, gemini_key: str):
        self.gemini_api_key = gemini_key
        print(f"DEBUG: AIService API keys updated. Gemini: {'Yes' if self.gemini_api_key else 'No'}")

    def analyze_email(self, email_content: str, context: Optional[str] = None, response_style: str = "Professional") -> Dict[str, Any]:
        """
        Analyzes an email to generate a summary, score, reply suggestion, and a draft response
        in a single API call.
        """
        # Check cache first
        if email_content in self.cache and (time.time() - self.cache[email_content]['timestamp']) < self.cache_expiry:
            print("DEBUG: Returning cached analysis.")
            return self.cache[email_content]['data']

        prompt = f"""Analyze the following email and provide a structured JSON response with the following fields:
- "summary": A concise summary of the email.
- "score": An integer score from 1 to 10 for importance and urgency.
- "reply_needed": A boolean indicating if a reply is needed.
- "response": A suggested response in a {response_style} tone.

Email content:
{email_content}

Conversation context:
{context if context else "None"}

JSON response:
"""
        
        if self.gemini_api_key and self.gemini_api_key != "your_gemini_api_key_here":
            try:
                raw_response = self._generate_with_gemini(prompt)
                # Clean the response to ensure it's valid JSON
                cleaned_response = raw_response.strip().replace("```json", "").replace("```", "")
                analysis = json.loads(cleaned_response)
                # Cache the result
                self.cache[email_content] = {'timestamp': time.time(), 'data': analysis}
                return analysis
            except Exception as e:
                print(f"Error analyzing email with Gemini: {e}")
                return self._generate_fallback_analysis()
        else:
            return self._generate_fallback_analysis()

    def _generate_with_gemini(self, prompt: str) -> str:
        """Generate response using Gemini API."""
        try:
            print("DEBUG: Attempting Gemini API call.")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.preferred_model}:generateContent?key={self.gemini_api_key}"
            
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.7,
                    "topK": 40,
                    "topP": 0.95,
                    "maxOutputTokens": 2048,
                }
            }
            
            response = requests.post(url, json=payload, timeout=30.0)
            response.raise_for_status()
            
            result = response.json()
            return result['candidates'][0]['content']['parts'][0]['text']
                
        except Exception as e:
            print(f"Gemini API error: {e}")
            # Reraise the exception to be caught by the calling method
            raise

    def _generate_fallback_analysis(self) -> Dict[str, Any]:
        """Generate a fallback analysis when AI services are unavailable."""
        return {
            "summary": "Could not generate summary due to technical limitations.",
            "score": 5,
            "reply_needed": False,
            "response": "Thank you for your email. I will get back to you shortly."
        }

    def summarize_attachment(self, attachment_content: str) -> str:
        """Summarize the content of an attachment using AI."""
        prompt = f"""Please provide a concise summary of the following document content.
        Focus on the main points, key information, and any conclusions or action items.

        Document content:
        {attachment_content}

        Summary:"""
        
        if self.gemini_api_key and self.gemini_api_key != "your_gemini_api_key_here":
            try:
                return self._generate_with_gemini(prompt)
            except Exception as e:
                print(f"Error summarizing attachment: {e}")
                return "AI service not available to summarize attachment."
        else:
            return "AI service not available to summarize attachment."
