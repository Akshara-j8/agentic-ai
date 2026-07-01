Here is my project. Write a short, clean `specs.md` file in markdown for it.

# Project

AI-Powered Quiz Generator Application

# Goal

Build a Streamlit app that accepts a `.pptx` file, extracts slide text, sends the content to an LLM through OpenRouter, and generates an interactive multiple-choice quiz with scoring and explanations.

# Input

* a PowerPoint file (`.pptx`)
* number of questions (5 to 30)
* difficulty level:

  * Simple
  * Medium
  * Complex

# Output

## Parsed PPT Output

* file name
* slide count
* extracted slide text / preview

## Quiz Output (per question)

* question text
* 4 options
* correct answer
* explanation

## Final Results Output

* score
* percentage
* selected answer vs correct answer
* explanation for wrong answers

# Functional Requirements

FR-1 Accept a `.pptx` upload in Streamlit
FR-2 Extract text from all slides
FR-3 Show slide count and preview
FR-4 Let user choose question count (5–30)
FR-5 Let user choose difficulty (Simple / Medium / Complex)
FR-6 Generate quiz questions using OpenRouter
FR-7 Show one question at a time with selectable options
FR-8 Score quiz answers
FR-9 Show correct answers and explanations
FR-10 Handle file/API errors gracefully

# Constraints

* use Streamlit for frontend
* use OpenRouter API for LLM access
* use `.env` for secrets
* use Python
* first version should be small and readable

# Done when

* I can upload a PPT and see parsed text preview
* I can generate a quiz from the PPT
* I can answer the quiz in Streamlit
* I can see score and explanations
* invalid file/API errors do not crash the app
* API key is not hardcoded

Write the final `specs.md` in the same short clean style as a software build spec, not as a long essay.
