import json
import os
import requests
import random

class QuizService:
    def __init__(self):
        # Ollama local endpoint
        # Ollama remote endpoint (User provided)
        self.api_url = os.environ.get("OLLAMA_API_URL", "https://unsanguine-rosette-impressibly.ngrok-free.dev/api/generate")
        self.model = "llama3.2" # Using the user-approved small model

    def generate_quiz(self, movie_title, movie_overview):
        print(f"DEBUG: Generating quiz for '{movie_title}' using Ollama ({self.model})...")

        prompt = f"""
        Read the movie description below and generate 1 TRICKY and INTELLECTUAL multiple-choice question based ONLY on it.
        
        MOVIE DESCRIPTION:
        "{movie_overview}"
        
        REQUIREMENTS:
        1. Question MUST be based on the specific plot details, not generic tropes.
        2. Make it challenging. Ask about a specific event, a character's motive, or a plot twist.
        3. 4 options (1 correct, 3 plausible but wrong).
        
        JSON FORMAT ONLY:
        {{
            "question": "Question text here",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "correct_answer": "Option A"
        }}
        IMPORTANT: "correct_answer" MUST be one of the exact strings from "options".
        """

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.3, # Low temperature for factual accuracy (less hallucination)
                "num_predict": 150, # Limit output tokens for SPEED
                "top_k": 20,
                "top_p": 0.9
            }
        }

        try:
            # High timeout because remote inference can be slow
            # Add header to skip ngrok browser warning
            headers = {"ngrok-skip-browser-warning": "true"}
            response = requests.post(self.api_url, json=payload, headers=headers, timeout=180)
            response.raise_for_status()
            
            data = response.json()
            text_content = data.get('response', '')
            
            print(f"DEBUG: Raw Ollama response: {text_content[:200]}...") # Log first 200 chars

            # Parse JSON
            try:
                quiz_data = json.loads(text_content)
                
                # Normalize response to a list of questions
                if isinstance(quiz_data, dict):
                    # Check if it has "question" key directly
                    if "question" in quiz_data:
                        quiz_data = [quiz_data]
                    # Check if it has "questions" key (list or dict)
                    elif "questions" in quiz_data:
                        if isinstance(quiz_data["questions"], list):
                            quiz_data = quiz_data["questions"]
                        elif isinstance(quiz_data["questions"], dict):
                            quiz_data = [quiz_data["questions"]]
                    # Handle "question1", "question2" pattern
                    elif any(k.startswith("question") for k in quiz_data.keys()):
                        # Try to extract values that look like question objects
                        temp_list = []
                        for k, v in quiz_data.items():
                            if isinstance(v, dict) and "question" in v:
                                temp_list.append(v)
                            elif isinstance(v, str) and k.startswith("question"):
                                # If flat structure like {"question1": "Text", "options1": ...} - too complex, assume object
                                pass
                        if temp_list:
                            quiz_data = temp_list
                        else:
                             # Last resort: just wrap the whole dict if it looks reasonable? 
                             # No, safer to fail to backup if fuzzy.
                             pass

                if not isinstance(quiz_data, list):
                    print("DEBUG: Ollama returned invalid JSON structure (not a list).")
                    return None
                
                # FIX: Convert letter/number answers to actual text
                for q in quiz_data:
                    correct = q.get('correct_answer', '')
                    options = q.get('options', [])
                    
                    # Check if answer is a letter (A, B, C, D) or number (0, 1, 2, 3)
                    if correct in ['A', 'B', 'C', 'D']:
                        idx = ord(correct) - ord('A')
                        if 0 <= idx < len(options):
                            q['correct_answer'] = options[idx]
                            print(f"DEBUG: Converted '{correct}' to '{options[idx]}'")
                    elif correct.isdigit():
                        idx = int(correct)
                        if 0 <= idx < len(options):
                            q['correct_answer'] = options[idx]
                            print(f"DEBUG: Converted '{correct}' to '{options[idx]}'")
                    
                return quiz_data
                
            except json.JSONDecodeError as e:
                print(f"DEBUG: Failed to parse JSON from Ollama: {e}")
                return None

        except requests.exceptions.ConnectionError:
            print("DEBUG: Could not connect to Ollama. Is it running? (ollama serve)")
            return None
        except Exception as e:
            print(f"DEBUG: Ollama generation failed: {e}")
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
