# DeepResearch AI Agent

An AI research assistant with a live dashboard. The backend (FastAPI) and the dashboard (static/index.html) run together from one folder.
It is completely free to run: it uses the Google Gemini free API and DuckDuckGo search.

## Folder structure

deepresearch-agent/
├── main.py
├── requirements.txt
├── .env
├── README.md
└── static/
    └── index.html

## Setup (one time only)

1. Install Python 3.10 or newer from python.org.
2. Open a terminal inside the project folder and run:

       python -m venv venv
       venv\Scripts\activate          (Mac/Linux: source venv/bin/activate)
       pip install -r requirements.txt

3. Create a file named `.env` in the project folder and add:

       GEMINI_API_KEY=your_free_key_here
       GEMINI_MODEL=gemini-2.5-flash

   Get a free key at https://aistudio.google.com/apikey
   (sign in with a Google account, no credit card needed).
   Search needs no key.

## Run

       uvicorn main:app --reload

Then open http://localhost:8000 in your browser.

## How it works

1. Planning: Gemini creates 7 search queries.
2. Searching: DuckDuckGo runs the web searches (free).
3. Reading: each page is downloaded and cleaned (trafilatura), then Gemini writes notes.
4. Summarizing: Gemini writes an executive summary.
5. Verifying: Gemini cross-checks the sources.
6. Writing: the final report is written with citations.

- Live updates: Server-Sent Events (SSE) update the dashboard in real time.
- History: saved in a local SQLite database (research.db).
- Downloads: Markdown (from the browser) and PDF (/api/report/ID/pdf).

## Troubleshooting

- "API keys missing": check your .env file, make sure the key is correct, and restart the server.
- "model not found": open aistudio.google.com, check the current model name, and update GEMINI_MODEL in .env.
- "Gemini free limit reached": the free plan has a per-minute limit. Wait a minute and try again. Use "Quick (4 sources)" depth.
- "No search results": DuckDuckGo sometimes rate limits. Wait a minute and try again.
- PDF export: non-Latin scripts such as Urdu need a custom font. English and Roman Urdu work fine.

## Files

- main.py            backend and agent pipeline
- static/index.html  the dashboard UI
- requirements.txt   Python packages
- .env               your API key (never share it)