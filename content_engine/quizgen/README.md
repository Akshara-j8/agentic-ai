# 📘 AI-Powered Quiz Generator

An AI-powered quiz generator that converts PDF study materials into interactive multiple-choice quizzes.

## Features

- 📄 **PDF Upload**: Upload any PDF study material
- 🤖 **AI Quiz Generation**: Automatically generates questions using AI (via OpenRouter)
- ⚙️ **Customizable**: Choose 5-30 questions with Simple/Medium/Complex difficulty
- 📝 **Interactive Quiz**: Answer questions one by one with navigation
- 🎯 **Smart Scoring**: Get instant results with explanations for wrong answers
- ✅ **Learning Mode**: Review all answers with explanations

## Installation

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up your API key:**
   - Your OpenRouter API key is already configured in `.env`
   - If you need to change it, edit the `.env` file:
     ```
     OPENROUTER_API_KEY=your_key_here
     ```

## Usage

1. **Run the application:**
   ```bash
   streamlit run app.py
   ```

2. **Use the app:**
   - Upload a PDF file
   - View extracted text preview
   - Select number of questions (5-30)
   - Choose difficulty level
   - Click "Generate Quiz"
   - Answer questions one by one
   - Review your results with explanations

## Project Structure

```
quizgen/
├── app.py              # Main Streamlit application
├── pdf_parser.py       # PDF text extraction module
├── llm.py             # AI quiz generation module (OpenRouter)
├── requirements.txt    # Python dependencies
├── .env               # API keys (keep secret!)
└── README.md          # This file
```

## How It Works

1. **PDF Parsing** (`pdf_parser.py`):
   - Extracts text from uploaded PDF using `pypdf`
   - Handles errors gracefully (empty files, corrupted PDFs, etc.)
   - Returns structured data with page-by-page text

2. **Quiz Generation** (`llm.py`):
   - Sends extracted text to OpenRouter's AI models
   - Generates questions based on content, count, and difficulty
   - Validates AI output format
   - Returns structured quiz data

3. **Interactive Interface** (`app.py`):
   - Upload and preview PDF files
   - Configure quiz settings
   - Take quiz with navigation (Previous/Next)
   - View results with scoring and explanations
   - Retake or upload new content

## Error Handling

- ✅ Empty or corrupted PDF files
- ✅ Invalid API responses
- ✅ Network failures
- ✅ Malformed quiz data
- ✅ Image-based PDFs (warning message)

## Requirements

- Python 3.8+
- Streamlit
- pypdf
- OpenAI SDK (for OpenRouter)
- python-dotenv

## Notes

- PDFs must contain extractable text (not scanned images)
- Quiz quality depends on the quality of study material
- API calls may take a few seconds depending on content length
- Your API key is stored locally in `.env` (never commit this file!)

## Troubleshooting

**"No text could be extracted":**
- Your PDF might be image-based or scanned
- Try a different PDF with selectable text

**"API Error":**
- Check your internet connection
- Verify your OpenRouter API key is valid
- Check OpenRouter service status

**"Model returned invalid JSON":**
- Try reducing question count
- Try a simpler difficulty level
- The AI model might be having issues - retry

## License

Free to use and modify for educational purposes.
