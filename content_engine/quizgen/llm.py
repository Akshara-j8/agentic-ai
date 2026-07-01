"""
LLM Quiz Generator Module

Uses OpenRouter via the OpenAI Python SDK to generate MCQ quizzes
from extracted PDF text.
"""

import os
import json
import re
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from .env
load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.2-3b-instruct:free")

if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY not found in .env")

# OpenRouter client using OpenAI-compatible SDK
client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1"
)


def preprocess_content(content: str) -> str:
    """
    Clean extracted PDF text by removing scanner artifacts, page numbers,
    repeated metadata, and noisy OCR lines.
    """
    if not content:
        return ""

    junk_patterns = [
        r"scanned with camscanner",
        r"camscanner",
        r"page\s+\d+",
        r"^\d+$",
        r"www\.[^\s]+",
        r"downloaded from.*",
        r"copyright.*",
        r"all rights reserved.*",
        r"^\s*[ivxlcdm]+\s*$",  # roman numeral page numbers
    ]

    cleaned_lines = []

    for line in content.splitlines():
        line = line.strip()

        # skip empty lines
        if not line:
            continue

        # skip very short junk lines
        if len(line) <= 2:
            continue

        # skip scanner / metadata / page number lines
        skip = False
        for pattern in junk_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                skip = True
                break

        if not skip:
            cleaned_lines.append(line)

    cleaned_text = "\n".join(cleaned_lines)

    # normalize repeated spaces/newlines
    cleaned_text = re.sub(r"\n{2,}", "\n", cleaned_text)
    cleaned_text = re.sub(r"[ \t]+", " ", cleaned_text)

    return cleaned_text.strip()


def build_quiz_prompt(content: str, question_count: int, difficulty: str) -> str:
    """
    Build the prompt for quiz generation.
    """
    return f"""
You are an expert educational quiz generator.

Your task is to create a quiz that tests students' understanding of the CONCEPTS, FACTS, and KNOWLEDGE presented in the study material below.

CRITICAL INSTRUCTIONS - READ CAREFULLY:
1. ONLY create questions about the EDUCATIONAL CONTENT and SUBJECT MATTER.
2. IGNORE any scanning artifacts, watermarks, page numbers, headers, footers, or metadata.
3. Focus on the CORE CONCEPTS, theories, definitions, explanations, and principles being taught.
4. DO NOT ask questions about:
   - document format, PDF structure, or scanning
   - page numbers, resolution, image quality, watermarks
   - how the file was created or scanned
   - metadata, OCR noise, or repeated junk text
5. ONLY ask questions about:
   - key concepts and definitions
   - important facts and principles
   - relationships between ideas
   - applications, uses, and examples
   - understanding of theories and subject content
6. If the material contains scanner text, page numbers, watermarks, or metadata, completely ignore them and generate questions only from the academic subject content.

STUDY MATERIAL:
{content}

TASK:
Generate exactly {question_count} multiple-choice questions at {difficulty} difficulty level.

DIFFICULTY GUIDELINES:
- Simple: basic definitions, direct facts, key concepts
- Medium: application of concepts, comparison, relationships, understanding
- Complex: deeper reasoning, analysis, synthesis, problem-solving

QUESTION REQUIREMENTS:
1. Questions must be based only on the STUDY TOPIC / SUBJECT CONTENT in the material.
2. Each question must have exactly 4 options.
3. Only ONE option must be correct.
4. Wrong options should be plausible but clearly incorrect.
5. Include a short explanation for the correct answer.
6. Questions should be clear, academic, and meaningful.

OUTPUT FORMAT:
Return ONLY valid JSON in this exact format.
Do NOT include markdown, code fences, or extra text.

[
  {{
    "id": 1,
    "question": "Question text",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "correct_answer": "Option A",
    "explanation": "Short explanation based on the study material"
  }}
]
"""


def clean_json_response(text: str) -> str:
    """
    Remove markdown code fences if the model accidentally includes them.
    """
    text = text.strip()

    if text.startswith("```json"):
        text = text.replace("```json", "", 1).strip()
    if text.startswith("```"):
        text = text.replace("```", "", 1).strip()
    if text.endswith("```"):
        text = text[:-3].strip()

    return text


def validate_quiz_data(quiz_data, question_count):
    """
    Validate the structure of quiz data returned by the model.
    """
    if not isinstance(quiz_data, list):
        raise ValueError("Quiz output is not a list.")

    if len(quiz_data) != question_count:
        raise ValueError(
            f"Expected {question_count} questions, but got {len(quiz_data)}."
        )

    for i, q in enumerate(quiz_data, start=1):
        if not isinstance(q, dict):
            raise ValueError(f"Question {i} is not a valid object.")

        required_fields = ["id", "question", "options", "correct_answer", "explanation"]
        for field in required_fields:
            if field not in q:
                raise ValueError(f"Question {i} is missing field: {field}")

        if not isinstance(q["options"], list) or len(q["options"]) != 4:
            raise ValueError(f"Question {i} must have exactly 4 options.")

        if q["correct_answer"] not in q["options"]:
            raise ValueError(
                f"Question {i} has correct_answer not present in options."
            )


def generate_quiz_from_text(content: str, question_count: int, difficulty: str):
    """
    Generate quiz questions from extracted PDF text using OpenRouter.

    Args:
        content (str): Extracted text from the PDF
        question_count (int): Number of questions (5–30)
        difficulty (str): Simple / Medium / Complex

    Returns:
        list: List of quiz question dictionaries
    """
    if not content or not content.strip():
        raise ValueError("No study material text found to generate quiz.")

    if not (5 <= question_count <= 30):
        raise ValueError("Question count must be between 5 and 30.")

    if difficulty not in ["Simple", "Medium", "Complex"]:
        raise ValueError("Difficulty must be Simple, Medium, or Complex.")

    # Clean the PDF text before sending to the model
    cleaned_content = preprocess_content(content)

    if not cleaned_content.strip():
        raise ValueError("No useful study content found in the PDF after cleaning.")

    prompt = build_quiz_prompt(cleaned_content, question_count, difficulty)

    try:
        response = client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You generate educational quizzes in strict JSON format. "
                        "Ignore PDF metadata, page numbers, watermarks, scanner text, "
                        "and formatting noise. Generate questions only from actual academic content."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.4
        )

        raw_output = response.choices[0].message.content
        cleaned_output = clean_json_response(raw_output)

        try:
            quiz_data = json.loads(cleaned_output)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Model returned invalid JSON.\nRaw output:\n{raw_output}\n\nError: {e}"
            )

        validate_quiz_data(quiz_data, question_count)
        return quiz_data

    except Exception as e:
        raise Exception(f"Quiz generation failed: {str(e)}")


if __name__ == "__main__":
    sample_text = """
    Scanned with CamScanner
    Machine learning is a branch of artificial intelligence.
    It allows systems to learn from data and improve over time.
    Supervised learning uses labeled data, while unsupervised learning works with unlabeled data.
    Page 1
    """

    try:
        quiz = generate_quiz_from_text(sample_text, 5, "Simple")
        print("\nGenerated Quiz:\n")
        print(json.dumps(quiz, indent=2))
    except Exception as e:
        print("Error:", e)