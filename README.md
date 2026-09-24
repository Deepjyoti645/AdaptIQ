AdaptIQ - Smart AI Tutor & Learning Platform
​Project Overview
​AdaptIQ is an AI-driven, highly personalized EdTech platform designed to transform how students learn, practice, and resolve doubts. Built using Flask (Python) and a responsive web interface, the system features AI-based personalized mock tests, instant doubt resolution, and intelligent streak tracking. The platform dynamically adapts content based on the user's grade level, curriculum context, and past performance history.
​Author & Development Story
​Developer Age: 14 Years Old
​Development Environment: Developed and coded entirely on a mobile phone within an Android / Termux environment.
​Motivation: To bridge the gap between modern AI mentorship and daily school learning, making personalized education accessible to students through affordable technology.
​Key Features
​1. Personalized AI Test Generator (/api/generate-test)
​Dynamic Quiz Generation: Generates targeted multiple-choice questions (MCQs) using Google Gemini AI, customized to the student's class grade, subject, and chosen topics.
​Weak Topic Focus: Automatically integrates topics where the student previously struggled to ensure focused revision.
​Multiple Test Modes:
​Custom Test: Allows selection of specific sub-topics and tags.
​Chapter Wise Test: Enables targeted practice structured around specific textbook chapters.
​Previous Year Questions (PYQs): Provides practice aligned with past examination patterns.
​Parsing & Validation: Filters and validates raw AI outputs to prevent interface errors and ensure stable UI rendering.
​2. AdaptIQ AI Tutor Bot (/api/chat)
​Context-Aware Mentorship: Tailors explanations by accounting for the user's age, grade, country, topic proficiencies, and past test history.
​Curriculum-Aligned Explanations: Delivers step-by-step breakdowns appropriate for specific student grade levels.
​Encouraging Interaction: Functions as an interactive learning companion to support students throughout their study routine.
​3. Smart Analytics & Performance Tracker (/api/performance)
​7-Day Rolling Analytics: Computes a 7-day rolling average for accuracy, total questions attempted, and completed tests.
​Topic-Level Classification: Automatically categorizes subjects into 'strong' or 'weak' in the database based on accuracy metrics.
​Dynamic Feedback & Insights: Generates performance insights and actionable feedback after every test completion.
​4. Daily Streak & Re-engagement System (/api/streak)
​Gamified Consistency: Monitors daily usage and increments streak counts for consecutive logins.
​Inactivity Alerts & Push Notifications: Dispatches scheduled push notifications using PyWebPush (VAPID):
​3 Days Inactive: Sends a study reminder.
​5-7 Days Inactive: Sends re-engagement notifications linked with mascot status updates (Little_Sad, Very_Sad).
​Post-Test Alerts: Sends instant feedback based on performance outcomes (Very_Happy, Normal, Little_Sad).
​5. Mobile-First Responsive UI / PWA Design
​Touch & Gesture Controls: Implements responsive swipe and touch navigation optimized for mobile screens.
​Interactive Mascot: Features an interactive visual mascot and entry UI components.
​Local Data Management: Provides fallback file path handling for local storage systems (/storage/emulated/0/Download/AdaptIQ/).
​Target Audience
​K-12 Students (Grades 1 to 12):
Students seeking step-by-step doubt resolution and practice matching their specific school syllabus.
​Competitive & School Exam Aspirants:
Learners who need customized mock tests focused on weak areas and examination patterns.
​Self-Paced Learners:
Students who prefer structured self-study supported by streak tracking and AI guidance.
​Real-World Applications & Impact
​Automated Self-Study Assistant: Provides 24/7 step-by-step academic support for homework and topic revisions.
​Adaptive Learning: Replaces generic quizzes with targeted practice focused on areas needing improvement.
​Low-Resource Compatibility: Operates efficiently within lightweight Python environments, allowing deployment on standard mobile devices.
​Tech Stack & Architecture
​Backend: Python 3, Flask, CORS, SQLite3
​AI Integration: Google Gemini AI (gemini-3.6-flash, gemini-3.5-flash-lite, gemini-3.1-pro-preview)
​Push Notifications: PyWebPush (VAPID Keys), Web Service Workers
​Frontend: HTML5, CSS3, JavaScript (ES6)
​Environment Support: Mobile Python / Termux via python-dotenv
​Setup & Installation
​Clone the Repository:
git clone https://github.com/your-username/AdaptIQ.git
cd AdaptIQ
​Install Dependencies:
pip install flask flask-cors pywebpush python-dotenv
​Configure Environment Variables (.env):
Create a .env file in the project root directory and add the required credentials:
GEMINI_API_KEY=your_gemini_api_key_here
VAPID_PUBLIC_KEY=your_vapid_public_key
VAPID_PRIVATE_KEY=your_vapid_private_key
​Run the Application:
python app.py
​Access Application:
Open http://localhost:5000 in your browser.
