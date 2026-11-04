🤖 DeepResearch AI Agent

Smarter Research. Stronger Insights.

DeepResearch AI Agent is an AI-powered research assistant that automates web research, analyzes multiple sources, verifies information, and generates structured research reports with citations.

✨ Features

- AI-powered research using Google Gemini.
- Free web searching with DuckDuckGo.
- Automated research planning and source analysis.
- AI summarization and source verification.
- Six-stage research workflow with live progress tracking.
- Real-time activity updates using SSE.
- Research history stored in SQLite.
- Download reports in PDF and Markdown formats.
- Modern dark-themed interactive dashboard.

🛠️ Technologies Used

- Python
- FastAPI
- Google Gemini AI
- DuckDuckGo Search
- Trafilatura
- SQLite
- HTML, CSS, JavaScript
- Server-Sent Events (SSE)
- Uvicorn

📸 Screenshots

Dashboard

"Dashboard" (screenshots/dashboard-home.png)

Research Completed

"Research Complete" (screenshots/research-complete.png)

Full Research Report

"Full Report" (screenshots/full-report.png)

Research History

"Research History" (screenshots/research-history.png)

Generated Reports

"Generated Reports" (screenshots/generated-reports.png)

📁 Project Structure

DeepResearch-AI-Agent/
│
├── main.py
├── requirements.txt
├── README.md
├── .gitignore
│
├── static/
│   └── index.html
│
└── screenshots/
    ├── dashboard-home.png
    ├── full-report.png
    ├── generated-reports.png
    ├── research-complete.png
    └── research-history.png

⚙️ Installation & Setup

1. Clone the repository

git clone YOUR_GITHUB_REPOSITORY_URL
cd DeepResearch-AI-Agent

2. Create and activate virtual environment

python -m venv venv
venv\Scripts\activate

3. Install dependencies

pip install -r requirements.txt

4. Configure API key

Create a ".env" file in the project folder:

GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-2.5-flash

Get your free API key: https://aistudio.google.com/apikey

5. Run the application

uvicorn main:app --reload

Open in your browser:

"http://localhost:8000"

🔄 Research Workflow

1. Planning
2. Searching
3. Reading Sources
4. Summarizing
5. Verifying
6. Writing Report

📄 Export Options

- PDF Research Reports
- Markdown Research Reports

💡 Notes

- Gemini API free-tier quotas and limits apply.
- DuckDuckGo search requires no API key.
- Keep your ".env" file private.
- Research history is stored locally in SQLite.

👩‍💻 Author

Maria Zafar

Computer Science Student | AI & Machine Learning Enthusiast

GitHub: "MariaZafar22" (https://github.com/MariaZafar22)

---

⭐ If you find this project useful, don't forget to give it a star!

Built with Python, FastAPI, and Google Gemini AI.
