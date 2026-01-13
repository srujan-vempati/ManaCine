import os
import json
import requests
import random

class QuizService:
    def __init__(self):
        self.api_key = os.environ.get('GEMINI_API_KEY')
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.api_key}"

    def generate_quiz(self, movie_title, movie_overview):
        if not self.api_key:
            print("DEBUG: GEMINI_API_KEY is missing!")
            return None
        print(f"DEBUG: Using API Key starting with: {self.api_key[:5]}...")

        prompt = f"""
        Generate 2 HARD, UNIQUE multiple-choice questions about the PLOT of the movie "{movie_title}".
        Context: {movie_overview}
        
        RULES:
        1. Questions must be about specific STORY events, CLIMAX details, or CHARACTER decisions.
        2. DO NOT ask about Release Year, Actors, Directors, or Box Office.
        3. The goal is to verify if the user has TRULY watched the movie.
        4. Provide 4 options for each question (1 correct, 3 plausible but wrong).
        
        Return ONLY a raw JSON object with this structure:
        [
            {{
                "question": "Specific question about a scene?",
                "options": ["Option A", "Option B", "Option C", "Option D"],
                "correct_answer": "Option A"
            }},
            ...
        ]
        """

        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }

        # Try multiple models to avoid Rate Limits (429)
        models = [
            "gemini-2.0-flash",
            "gemini-2.5-flash",
            "gemini-flash-latest", 
            "gemini-pro"
        ]
        
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        session = requests.Session()
        retries = Retry(total=2, backoff_factor=1, status_forcelist=[500, 502, 503])
        session.mount('https://', HTTPAdapter(max_retries=retries))

        data = None
        for model in models:
            try:
                print(f"DEBUG: Trying model {model}...")
                current_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
                timeout = 10 if model != models[-1] else 20
                
                response = session.post(current_url, json=payload, timeout=timeout)
                
                if response.status_code == 429:
                    print(f"DEBUG: Model {model} hit Rate Limit (429). Switching...")
                    continue 
                
                response.raise_for_status()
                data = response.json()
                break # Success
                
            except Exception as e:
                print(f"DEBUG: Model {model} failed: {e}")
                if model == models[-1]:
                    # All failed
                    return None
        
        if not data:
            return None

        try:
            # Extract text from Gemini response
            text_content = data['candidates'][0]['content']['parts'][0]['text']
            print(f"DEBUG: Raw Gemini response: {text_content}") 
            
            # Robust JSON extraction
            import re
            json_match = re.search(r'\[.*\]', text_content, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                quiz_data = json.loads(json_str)
                return quiz_data
            else:
                quiz_data = json.loads(text_content.strip())
                return quiz_data
            
        except Exception as e:
            print(f"Error parsing quiz: {e}")
            return None

    def generate_backup_quiz(self, movie):
        """Generates a quiz based on metadata if AI fails."""
        import random
        
        quiz = []
        
        # Q1: Director
        directors = movie.get('directors', [])
        if directors:
            director_name = directors[0]['name']
            fakes = ["S.S. Rajamouli", "Trivikram Srinivas", "Sukumar", "Nag Aswin", "Puri Jagannadh"]
            fakes = [f for f in fakes if f != director_name]
            if len(fakes) >= 3:
                options = [director_name] + random.sample(fakes, 3)
            else:
                options = [director_name] + fakes 
            random.shuffle(options)
            
            quiz.append({
                "question": f"Who directed '{movie['title']}'?",
                "options": options,
                "correct_answer": director_name
            })
            
        # Q2: Release Year
        year = movie.get('release_date', '')[:4]
        if year and year.isdigit():
            y = int(year)
            options = [str(y), str(y+1), str(y-2), str(y+3)]
            random.shuffle(options)
            
            quiz.append({
                "question": f"In which year was '{movie['title']}' released?",
                "options": options,
                "correct_answer": str(y)
            })
            
        return quiz
