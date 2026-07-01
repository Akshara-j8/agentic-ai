import streamlit as st
from pdf_parser import extract_pdf_text
from llm import generate_quiz_from_text
from datetime import datetime
import time


# -----------------------------
# Streamlit page config
# -----------------------------
st.set_page_config(
    page_title="AI Quiz Generator",
    layout="centered",
    initial_sidebar_state="collapsed"
)


# -----------------------------
# Session state initialization
# -----------------------------
if "app_step" not in st.session_state:
    st.session_state.app_step = "upload"

if "pdf_data" not in st.session_state:
    st.session_state.pdf_data = None

if "quiz" not in st.session_state:
    st.session_state.quiz = []

if "current_question" not in st.session_state:
    st.session_state.current_question = 0

if "answers" not in st.session_state:
    st.session_state.answers = {}

if "score" not in st.session_state:
    st.session_state.score = 0

if "theme" not in st.session_state:
    st.session_state.theme = "dark"

if "quiz_history" not in st.session_state:
    st.session_state.quiz_history = []

if "timed_mode" not in st.session_state:
    st.session_state.timed_mode = False

if "quiz_start_time" not in st.session_state:
    st.session_state.quiz_start_time = None

if "time_per_question" not in st.session_state:
    st.session_state.time_per_question = 60  # seconds

if "last_quiz_config" not in st.session_state:
    st.session_state.last_quiz_config = None


# -----------------------------
# Custom CSS for beautiful styling
# -----------------------------
def apply_theme():
    if st.session_state.theme == "dark":
        st.markdown("""
        <style>
            /* Dark Theme */
            .stApp {
                background: linear-gradient(135deg, #1e1e2e 0%, #2d2d44 100%);
            }
            
            .main-title {
                text-align: center;
                font-size: 3.5rem;
                font-weight: 800;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 0.5rem;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
            }
            
            .subtitle {
                text-align: center;
                color: #a0aec0;
                font-size: 1.1rem;
                margin-bottom: 2rem;
            }
            
            .success-box {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 1.5rem;
                border-radius: 15px;
                text-align: center;
                color: white;
                font-size: 1.2rem;
                font-weight: 600;
                margin: 2rem 0;
                box-shadow: 0 10px 25px rgba(102, 126, 234, 0.3);
            }
            
            .stButton>button {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 10px;
                padding: 0.75rem 2rem;
                font-weight: 600;
                font-size: 1rem;
                box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
                transition: all 0.3s ease;
            }
            
            .stButton>button:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
            }
            
            div[data-testid="stFileUploader"] {
                background: rgba(255, 255, 255, 0.05);
                border: 2px dashed #667eea;
                border-radius: 15px;
                padding: 2rem;
            }
            
            .quiz-question {
                background: rgba(255, 255, 255, 0.05);
                padding: 2rem;
                border-radius: 15px;
                border-left: 5px solid #667eea;
                margin: 1.5rem 0;
            }
            
            .score-display {
                text-align: center;
                font-size: 2.5rem;
                font-weight: 800;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin: 2rem 0;
            }
            
            .timer {
                position: fixed;
                top: 1rem;
                left: 1rem;
                background: rgba(255, 0, 0, 0.8);
                color: white;
                padding: 0.75rem 1.5rem;
                border-radius: 10px;
                font-size: 1.2rem;
                font-weight: 700;
                z-index: 999;
                box-shadow: 0 4px 15px rgba(255, 0, 0, 0.4);
            }
            
            .weak-topic-box {
                background: rgba(255, 100, 100, 0.1);
                border-left: 5px solid #ff6b6b;
                padding: 1rem;
                border-radius: 10px;
                margin: 1rem 0;
            }
        </style>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <style>
            /* Light Theme */
            .stApp {
                background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%);
            }
            
            .main-title {
                text-align: center;
                font-size: 3.5rem;
                font-weight: 800;
                background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 0.5rem;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
            }
            
            .subtitle {
                text-align: center;
                color: #744210;
                font-size: 1.1rem;
                margin-bottom: 2rem;
                font-weight: 500;
            }
            
            .success-box {
                background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
                padding: 1.5rem;
                border-radius: 15px;
                text-align: center;
                color: white;
                font-size: 1.2rem;
                font-weight: 600;
                margin: 2rem 0;
                box-shadow: 0 10px 25px rgba(250, 112, 154, 0.3);
            }
            
            .stButton>button {
                background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
                color: white;
                border: none;
                border-radius: 10px;
                padding: 0.75rem 2rem;
                font-weight: 600;
                font-size: 1rem;
                box-shadow: 0 4px 15px rgba(250, 112, 154, 0.4);
                transition: all 0.3s ease;
            }
            
            .stButton>button:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(250, 112, 154, 0.6);
            }
            
            div[data-testid="stFileUploader"] {
                background: rgba(255, 255, 255, 0.6);
                border: 2px dashed #fa709a;
                border-radius: 15px;
                padding: 2rem;
            }
            
            .quiz-question {
                background: rgba(255, 255, 255, 0.6);
                padding: 2rem;
                border-radius: 15px;
                border-left: 5px solid #fa709a;
                margin: 1.5rem 0;
            }
            
            .score-display {
                text-align: center;
                font-size: 2.5rem;
                font-weight: 800;
                background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin: 2rem 0;
            }
            
            .timer {
                position: fixed;
                top: 1rem;
                left: 1rem;
                background: rgba(255, 100, 100, 0.9);
                color: white;
                padding: 0.75rem 1.5rem;
                border-radius: 10px;
                font-size: 1.2rem;
                font-weight: 700;
                z-index: 999;
                box-shadow: 0 4px 15px rgba(255, 100, 100, 0.4);
            }
            
            .weak-topic-box {
                background: rgba(255, 100, 100, 0.15);
                border-left: 5px solid #fa709a;
                padding: 1rem;
                border-radius: 10px;
                margin: 1rem 0;
            }
            
            /* Light theme text adjustments */
            .stMarkdown, .stText, label {
                color: #2d3748 !important;
            }
        </style>
        """, unsafe_allow_html=True)

apply_theme()


# -----------------------------
# Theme Toggle & History Button
# -----------------------------
col1, col2, col3 = st.columns([4.5, 1, 1])
with col2:
    if st.button("📊 History", key="history_btn", help="View all quiz attempts"):
        st.session_state.show_history = not st.session_state.get("show_history", False)
with col3:
    if st.button("🌓" if st.session_state.theme == "dark" else "☀️", key="theme_toggle"):
        st.session_state.theme = "light" if st.session_state.theme == "dark" else "dark"
        st.rerun()


# -----------------------------
# Title
# -----------------------------
st.markdown('<h1 class="main-title">📘 AI Quiz Generator</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Transform your study materials into interactive quizzes powered by AI</p>', unsafe_allow_html=True)


# -----------------------------
# Quiz History Modal (if toggled)
# -----------------------------
if st.session_state.get("show_history", False) and st.session_state.quiz_history:
    with st.expander("📊 Complete Quiz History (All Attempts)", expanded=True):
        st.markdown("### All Your Quiz Attempts")
        
        total_attempts = len(st.session_state.quiz_history)
        if total_attempts > 0:
            avg_score = sum(r['percentage'] for r in st.session_state.quiz_history) / total_attempts
            st.info(f"**Total Attempts:** {total_attempts} | **Average Score:** {avg_score:.1f}%")
        
        # Show all history in reverse chronological order
        for i, result in enumerate(reversed(st.session_state.quiz_history), 1):
            time_str = f" ⏱️ {result['time_taken']}" if result.get('time_taken') else ""
            
            if result['percentage'] >= 80:
                emoji = "🌟"
                badge_color = "🟢"
            elif result['percentage'] >= 60:
                emoji = "👍"
                badge_color = "🟡"
            else:
                emoji = "📚"
                badge_color = "🔴"
            
            st.markdown(f"{badge_color} {emoji} **Attempt {total_attempts - i + 1}:** {result['date']} - Score: **{result['score']}/{result['total']}** ({result['percentage']:.1f}%){time_str}")
        
        if st.button("❌ Close History"):
            st.session_state.show_history = False
            st.rerun()


# -----------------------------
# Helper functions
# -----------------------------
def reset_all():
    """Reset the whole app state."""
    st.session_state.app_step = "upload"
    st.session_state.pdf_data = None
    st.session_state.quiz = []
    st.session_state.current_question = 0
    st.session_state.answers = {}
    st.session_state.score = 0
    st.session_state.quiz_start_time = None


def reset_quiz():
    """Retake same quiz."""
    st.session_state.app_step = "quiz"
    st.session_state.current_question = 0
    st.session_state.answers = {}
    st.session_state.score = 0
    st.session_state.quiz_start_time = time.time() if st.session_state.timed_mode else None


def calculate_score():
    """Calculate quiz score."""
    score = 0
    for q in st.session_state.quiz:
        qid = q["id"]
        selected = st.session_state.answers.get(qid)
        if selected == q["correct_answer"]:
            score += 1
    return score


def analyze_weak_topics():
    """Analyze which questions were answered incorrectly."""
    weak_questions = []
    for q in st.session_state.quiz:
        qid = q["id"]
        selected = st.session_state.answers.get(qid)
        if selected != q["correct_answer"]:
            weak_questions.append({
                "question": q["question"],
                "correct_answer": q["correct_answer"],
                "your_answer": selected,
                "explanation": q["explanation"]
            })
    return weak_questions


def save_quiz_result(score, total, time_taken=None):
    """Save quiz result to history."""
    result = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "score": score,
        "total": total,
        "percentage": (score / total * 100) if total > 0 else 0,
        "time_taken": time_taken
    }
    st.session_state.quiz_history.append(result)


# -----------------------------
# STEP 1: Upload PDF + generate quiz
# -----------------------------
if st.session_state.app_step == "upload":
    st.markdown("### 📤 Upload Your Study Material")
    
    uploaded_file = st.file_uploader("Choose a PDF file", type=["pdf"], label_visibility="collapsed")

    if uploaded_file is not None:
        try:
            pdf_data = extract_pdf_text(uploaded_file)
            st.session_state.pdf_data = pdf_data

            # Only show success message
            st.markdown(f'<div class="success-box">✅ PDF uploaded successfully! ({pdf_data["page_count"]} pages)</div>', unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("### ⚙️ Configure Your Quiz")
            
            col1, col2 = st.columns(2)
            with col1:
                question_count = st.slider("📊 Number of Questions", 5, 30, 10, help="Choose between 5 and 30 questions")
            with col2:
                difficulty = st.selectbox("🎯 Difficulty Level", ["Simple", "Medium", "Complex"], index=1)

            # Advanced options
            with st.expander("⚙️ Advanced Options"):
                timed_mode = st.checkbox("⏱️ Timed Mode", value=False, help="Enable timer for exam-style practice")
                if timed_mode:
                    total_minutes = st.slider("⏰ Total Quiz Time (minutes)", 5, 60, 15, step=5, 
                                             help="Total time for entire quiz")
                    st.session_state.quiz_time_limit = total_minutes * 60  # Convert to seconds
                    st.session_state.timed_mode = True
                else:
                    st.session_state.timed_mode = False

            st.markdown("<br>", unsafe_allow_html=True)
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("🚀 Generate Quiz", use_container_width=True):
                    with st.spinner("🤖 AI is generating your quiz..."):
                        try:
                            quiz = generate_quiz_from_text(
                                content=pdf_data["combined_text"],
                                question_count=question_count,
                                difficulty=difficulty
                            )

                            st.session_state.quiz = quiz
                            st.session_state.current_question = 0
                            st.session_state.answers = {}
                            st.session_state.app_step = "quiz"
                            st.session_state.last_quiz_config = {
                                "question_count": question_count,
                                "difficulty": difficulty
                            }
                            if st.session_state.timed_mode:
                                st.session_state.quiz_start_time = time.time()
                            st.rerun()
                        except Exception as quiz_error:
                            st.error(f"❌ Quiz generation failed: {quiz_error}")

        except Exception as e:
            st.error(f"❌ Error processing PDF: {e}")

    # Show quiz history if exists
    if st.session_state.quiz_history:
        st.markdown("---")
        st.markdown("### 📊 Your Quiz History (Last 5 Attempts)")
        st.info("💡 Track your progress over time!")
        
        # Create a nice table-like display
        for i, result in enumerate(reversed(st.session_state.quiz_history[-5:]), 1):
            time_str = f" ⏱️ Time: {result['time_taken']}" if result.get('time_taken') else ""
            
            # Color based on percentage
            if result['percentage'] >= 80:
                emoji = "🌟"
            elif result['percentage'] >= 60:
                emoji = "👍"
            else:
                emoji = "📚"
            
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"{emoji} **{result['date']}** - Score: **{result['score']}/{result['total']}** ({result['percentage']:.1f}%){time_str}")
            with col2:
                if result['percentage'] >= 80:
                    st.success("Excellent!")
                elif result['percentage'] >= 60:
                    st.info("Good")
                else:
                    st.warning("Keep trying")


# -----------------------------
# STEP 2: Quiz screen
# -----------------------------
elif st.session_state.app_step == "quiz":
    quiz = st.session_state.quiz
    idx = st.session_state.current_question
    question = quiz[idx]

    # Timer display at the top
    if st.session_state.timed_mode and st.session_state.quiz_start_time:
        elapsed = time.time() - st.session_state.quiz_start_time
        total_time = st.session_state.get('quiz_time_limit', 900)  # Default 15 minutes
        remaining = max(0, total_time - elapsed)
        
        mins = int(remaining // 60)
        secs = int(remaining % 60)
        
        # Display timer prominently
        timer_col1, timer_col2, timer_col3 = st.columns([1, 2, 1])
        with timer_col2:
            if remaining < 60:
                st.error(f"⏰ Time Remaining: {mins:02d}:{secs:02d} ⚠️ HURRY!")
            elif remaining < 300:  # Less than 5 minutes
                st.warning(f"⏰ Time Remaining: {mins:02d}:{secs:02d}")
            else:
                st.info(f"⏰ Total Quiz Time: {mins:02d}:{secs:02d}")
        
        # Check if time is up
        if remaining <= 0:
            st.session_state.score = calculate_score()
            st.session_state.app_step = "results"
            time_taken = f"{int(elapsed // 60)}m {int(elapsed % 60)}s"
            save_quiz_result(st.session_state.score, len(quiz), time_taken)
            st.rerun()

    # Progress bar
    progress = (idx + 1) / len(quiz)
    st.progress(progress)
    
    st.markdown(f'<div class="quiz-question">', unsafe_allow_html=True)
    st.markdown(f"### Question {idx + 1} of {len(quiz)}")
    st.markdown(f"**{question['question']}**")
    st.markdown('</div>', unsafe_allow_html=True)

    # Previously selected answer if exists
    previous_answer = st.session_state.answers.get(question["id"], None)

    selected = st.radio(
        "Choose your answer:",
        question["options"],
        index=question["options"].index(previous_answer) if previous_answer in question["options"] else None,
        label_visibility="collapsed"
    )

    if selected:
        st.session_state.answers[question["id"]] = selected

    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        if idx > 0:
            if st.button("⬅️ Previous", use_container_width=True):
                st.session_state.current_question -= 1
                st.rerun()

    with col2:
        if idx < len(quiz) - 1:
            if st.button("Next ➡️", use_container_width=True):
                st.session_state.current_question += 1
                st.rerun()

    with col3:
        if idx == len(quiz) - 1:
            if st.button("✅ Submit Quiz", use_container_width=True):
                st.session_state.score = calculate_score()
                st.session_state.app_step = "results"
                if st.session_state.quiz_start_time:
                    elapsed = time.time() - st.session_state.quiz_start_time
                    time_taken = f"{int(elapsed // 60)}m {int(elapsed % 60)}s"
                    save_quiz_result(st.session_state.score, len(quiz), time_taken)
                else:
                    save_quiz_result(st.session_state.score, len(quiz))
                st.rerun()


# -----------------------------
# STEP 3: Results screen
# -----------------------------
elif st.session_state.app_step == "results":
    score = st.session_state.score
    total = len(st.session_state.quiz)
    percent = (score / total) * 100 if total > 0 else 0

    st.markdown("### 🎯 Quiz Results")
    st.markdown(f'<div class="score-display">Score: {score}/{total} ({percent:.1f}%)</div>', unsafe_allow_html=True)
    
    if percent >= 80:
        st.balloons()
        st.success("🌟 Excellent work! You've mastered this material!")
    elif percent >= 60:
        st.success("👍 Good job! You have a solid understanding!")
    else:
        st.info("📚 Keep studying! Review the explanations below.")

    # Weak topic analysis
    weak_questions = analyze_weak_topics()
    if weak_questions:
        st.markdown("---")
        st.markdown("### 📉 Areas for Improvement")
        st.markdown(f'<div class="weak-topic-box">', unsafe_allow_html=True)
        st.write(f"**You got {len(weak_questions)} question(s) wrong. Focus on these topics:**")
        for i, wq in enumerate(weak_questions[:3], 1):
            st.write(f"{i}. {wq['question'][:80]}...")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📋 Review Your Answers")

    for q in st.session_state.quiz:
        selected = st.session_state.answers.get(q["id"], "Not answered")
        correct = q["correct_answer"]

        # Show full question in expander
        is_correct = selected == correct
        status_icon = "✅" if is_correct else "❌"
        
        with st.expander(f"{status_icon} Q{q['id']}: {q['question']}"):
            st.markdown(f"**Your Answer:** {selected}")
            st.markdown(f"**Correct Answer:** {correct}")

            if is_correct:
                st.success("✅ Correct!")
            else:
                st.error("❌ Incorrect")
                st.info(f"💡 **Explanation:** {q['explanation']}")

    st.markdown("<br>", unsafe_allow_html=True)
    
    # Action buttons
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🔄 Retake Quiz", use_container_width=True):
            reset_quiz()
            st.rerun()

    with col2:
        if st.button("🔁 Regenerate Quiz", use_container_width=True, help="Generate a new quiz with same settings"):
            if st.session_state.last_quiz_config:
                with st.spinner("🤖 Generating new quiz..."):
                    try:
                        quiz = generate_quiz_from_text(
                            content=st.session_state.pdf_data["combined_text"],
                            question_count=st.session_state.last_quiz_config["question_count"],
                            difficulty=st.session_state.last_quiz_config["difficulty"]
                        )
                        st.session_state.quiz = quiz
                        st.session_state.current_question = 0
                        st.session_state.answers = {}
                        st.session_state.app_step = "quiz"
                        if st.session_state.timed_mode:
                            st.session_state.quiz_start_time = time.time()
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Failed to regenerate: {e}")

    with col3:
        if st.button("📂 Upload New PDF", use_container_width=True):
            reset_all()
            st.rerun()
