import os, io, re, json, asyncio, sqlite3, datetime
from urllib.parse import urlparse

import httpx, trafilatura, markdown
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from xhtml2pdf import pisa

load_dotenv()


def clean(v: str) -> str:
    return (v or "").strip().strip('"').strip("'").strip()


# Protects against a .env where both settings were pasted on one line
_raw_key = clean(os.getenv("GEMINI_API_KEY", ""))
GEMINI_KEY = _raw_key.split()[0] if _raw_key else ""
MODEL = clean(os.getenv("GEMINI_MODEL", "")) or "gemini-2.5-flash"
TAVILY_KEY = clean(os.getenv("TAVILY_API_KEY", ""))  # optional, DuckDuckGo is used if empty

API = "https://generativelanguage.googleapis.com/v1beta"
_candidates: list = []   # models this key can use (filled automatically)
_tried: set = set()


async def list_models(h) -> list:
    r = await h.get(f"{API}/models", params={"key": GEMINI_KEY, "pageSize": 100})
    if r.status_code != 200:
        raise RuntimeError(f"Cannot list Gemini models (HTTP {r.status_code}). Check GEMINI_API_KEY in .env.")
    names = [m["name"].split("/")[-1] for m in r.json().get("models", [])
             if "generateContent" in m.get("supportedGenerationMethods", [])]
    bad = ("image", "tts", "live", "audio", "embedding", "thinking", "exp", "robotics", "computer", "vision")
    good = [n for n in names if "gemini" in n and not any(b in n for b in bad)]
    good.sort(key=lambda n: (0 if "flash" in n and "lite" not in n else 1 if "flash" in n else 2, n))
    return good or names


def err_text(r) -> str:
    try:
        return r.json()["error"]["message"][:250]
    except Exception:
        return r.text[:250]


async def ask(prompt: str, max_tokens: int = 1500) -> str:
    """Gemini free API: auto-picks a working model, retries on rate limits."""
    global MODEL, _candidates
    if not GEMINI_KEY:
        raise RuntimeError("GEMINI_API_KEY is missing. Put it in the .env file and restart the server.")
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens * 3}}
    last = ""
    for attempt in range(8):
        async with httpx.AsyncClient(timeout=120) as h:
            r = await h.post(f"{API}/models/{MODEL}:generateContent", params={"key": GEMINI_KEY}, json=body)
            if r.status_code == 404:  # this model is not available for the key: switch
                _tried.add(MODEL)
                if not _candidates:
                    _candidates = await list_models(h)
                nxt = [m for m in _candidates if m not in _tried]
                if not nxt:
                    raise RuntimeError("No usable Gemini model found for this key.")
                MODEL = nxt[0]
                continue
        if r.status_code in (429, 500, 503):
            last = err_text(r)
            await asyncio.sleep(8 * (attempt + 1))
            continue
        if r.status_code != 200:
            raise RuntimeError(f"Gemini error {r.status_code}: {err_text(r)}")
        try:
            parts = r.json()["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts).strip()
        except Exception:
            text = ""
        if text:
            return text
        last = "Empty answer from Gemini"
    raise RuntimeError(f"Gemini is busy or limit reached. {last}. Wait 1 minute and try again.")


def parse_json(t: str) -> dict:
    t = re.sub(r"```(?:json)?", "", t)
    try:
        return json.loads(t[t.index("{"): t.rindex("}") + 1])
    except Exception:
        raise RuntimeError("The AI returned an unexpected answer. Please try again.")


# ---------- database (research history) ----------
DB = "research.db"


def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


with db() as c:
    c.execute("""CREATE TABLE IF NOT EXISTS reports(
        id INTEGER PRIMARY KEY AUTOINCREMENT, topic TEXT, date TEXT,
        sources INTEGER, words INTEGER, summary TEXT, md TEXT)""")


# ---------- search + page reading ----------
async def search(query: str, n: int = 6):
    if TAVILY_KEY:
        try:
            async with httpx.AsyncClient(timeout=30) as h:
                r = await h.post("https://api.tavily.com/search",
                                 headers={"Authorization": f"Bearer {TAVILY_KEY}"},
                                 json={"query": query, "max_results": n})
                r.raise_for_status()
                return r.json().get("results", [])
        except Exception:
            pass
    try:  # free DuckDuckGo search, no key needed
        from ddgs import DDGS
        res = await asyncio.to_thread(lambda: list(DDGS().text(query, max_results=n)))
        return [{"title": x.get("title", ""), "url": x.get("href", ""), "content": x.get("body", "")} for x in res]
    except Exception:
        return []


async def fetch_text(src: dict) -> str:
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True,
                                     headers={"User-Agent": "Mozilla/5.0 DeepResearchBot"}) as h:
            r = await h.get(src["url"])
            text = await asyncio.to_thread(trafilatura.extract, r.text)
            if text and len(text) > 300:
                return text[:7000]
    except Exception:
        pass
    return src.get("snippet", "")[:3000]  # fallback: search snippet


# ---------- the 6-step agent pipeline ----------
def ev(**k):
    return f"data: {json.dumps(k, ensure_ascii=False)}\n\n"


async def pipeline(topic: str, depth: int, lang: str):
    today = datetime.date.today()
    today_s = f"{today:%B} {today.day}, {today.year}"
    try:
        yield ev(type="log", msg=f'Research task started: "{topic}"')

        # 1. Planning
        yield ev(type="step", i=0, status="pr", detail="Breaking the topic into focused search queries…")
        yield ev(type="log", msg="Agent is planning the research strategy…")
        plan = parse_json(await ask(
            f'Today is {today_s}. Topic: "{topic}". Create 7 distinct web search queries to research '
            f'this topic thoroughly. Return JSON only: {{"queries":["..."]}}', 600))
        queries = plan.get("queries", [topic])[:7]
        yield ev(type="step", i=0, status="ok")

        # 2. Searching
        yield ev(type="step", i=1, status="pr", detail="Finding relevant, credible sources…")
        yield ev(type="log", msg=f"Searching for relevant sources ({len(queries)} queries)…")
        results = await asyncio.gather(*[search(q) for q in queries])
        seen, sources = set(), []
        for rank in range(10):
            for res in results:
                if rank < len(res) and len(sources) < depth:
                    x = res[rank]
                    dom = urlparse(x["url"]).netloc.replace("www.", "")
                    if dom not in seen:
                        seen.add(dom)
                        sources.append({"title": x.get("title") or dom, "site": dom,
                                        "url": x["url"], "snippet": x.get("content", "")})
        if not sources:
            raise RuntimeError("No search results. Wait a minute and try again (DuckDuckGo may be rate limiting).")
        yield ev(type="log", msg=f"Found {len(sources)} relevant sources")
        yield ev(type="sources", sources=[{"title": s["title"], "site": s["site"], "url": s["url"]} for s in sources])
        yield ev(type="step", i=1, status="ok")

        # 3. Reading sources
        yield ev(type="step", i=2, status="pr", detail="Fetching and analyzing content from multiple web sources…")
        for i, s in enumerate(sources):
            yield ev(type="source", i=i, status="pr")
            yield ev(type="log", msg=f"Reading and analyzing source {i+1}/{len(sources)} ({s['site']})…")
            try:
                text = await fetch_text(s)
                s["note"] = await ask(
                    f'Topic: "{topic}". From the page text below, write 3-4 sentences of key facts and '
                    f'findings relevant to the topic. Only use the text; do not invent anything. '
                    f'Write in {lang}.\n\nTITLE: {s["title"]}\nTEXT:\n{text}', 500)
            except Exception:
                s["note"] = "Could not read this source."
            yield ev(type="source", i=i, status="ok", note=s["note"])
        yield ev(type="step", i=2, status="ok")

        notes = "\n".join(f"[{i+1}] {s['title']} ({s['url']}): {s['note']}" for i, s in enumerate(sources))

        # 4. Summarizing
        yield ev(type="step", i=3, status="pr", detail="Condensing findings into key insights…")
        yield ev(type="log", msg="Processing content and extracting key information…")
        summary = await ask(
            f'Topic: "{topic}". Source notes:\n{notes}\n\nWrite an Executive Summary of 4-5 sentences '
            f'in {lang}. Plain text only, no headings.', 600)
        yield ev(type="step", i=3, status="ok")

        # 5. Verifying
        yield ev(type="step", i=4, status="pr", detail="Cross-checking claims across sources…")
        yield ev(type="log", msg="Verifying claims across sources…")
        try:
            ver = parse_json(await ask(
                f'Review these notes on "{topic}":\n{notes}\n\nFind claims that conflict between sources '
                f'or look unsupported. Return JSON only: {{"confidence":"High|Medium|Low","flags":["short caveat"]}}', 500))
        except Exception:
            ver = {"confidence": "Medium", "flags": []}
        yield ev(type="step", i=4, status="ok")

        # 6. Writing
        yield ev(type="step", i=5, status="pr", detail="Writing the final report with citations…")
        yield ev(type="log", msg="Writing the final report…")
        body = await ask(
            f'Write a well-structured research report in Markdown in {lang} on: "{topic}". Today is {today_s}.\n'
            f'Use ONLY these source notes and cite them inline like [1], [2]:\n{notes}\n\n'
            f'Structure: # title, ## Executive Summary, ## Key Findings, ## Benefits, '
            f'## Challenges and Risks, ## Future Outlook, ## Conclusion. About 800-1000 words. '
            f'Do not invent statistics. Do not add a sources list.', 3500)
        full = (body + "\n\n## Verification\nConfidence: **" + ver.get("confidence", "Medium") + "**\n"
                + "\n".join("- " + f for f in ver.get("flags", []))
                + "\n\n## Sources\n"
                + "\n".join(f"- [{i+1}] [{s['title']}]({s['url']})" for i, s in enumerate(sources)))
        words = len(body.split())
        date = f"{today:%B} {today.day}, {today.year}"
        with db() as c:
            cur = c.execute("INSERT INTO reports(topic,date,sources,words,summary,md) VALUES(?,?,?,?,?,?)",
                            (topic, date, len(sources), words, summary, full))
            rid = cur.lastrowid
        yield ev(type="step", i=5, status="ok")
        yield ev(type="log", msg="Report ready ✓")
        yield ev(type="done", report={"id": rid, "topic": topic, "date": date, "sources": len(sources),
                                      "words": words, "summary": summary, "md": full})
    except Exception as e:
        yield ev(type="error", msg=str(e))


# ---------- API ----------
app = FastAPI()


@app.get("/api/health")
def health():
    return {"ok": bool(GEMINI_KEY)}


@app.get("/api/research")
async def research(topic: str, depth: int = 8, lang: str = "the same language as the topic"):
    depth = max(2, min(depth, 12))
    return StreamingResponse(pipeline(topic.strip()[:300], depth, lang),
                             media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/history")
def history():
    with db() as c:
        return [dict(r) for r in c.execute("SELECT * FROM reports ORDER BY id DESC LIMIT 50")]


@app.delete("/api/history")
def clear_history():
    with db() as c:
        c.execute("DELETE FROM reports")
    return {"ok": True}


@app.get("/api/report/{rid}/pdf")
def report_pdf(rid: int):
    with db() as c:
        r = c.execute("SELECT * FROM reports WHERE id=?", (rid,)).fetchone()
    if not r:
        raise HTTPException(404, "Not found")
    html = "<html><body style='font-family:Helvetica'>" + markdown.markdown(r["md"], extensions=["extra"]) + "</body></html>"
    buf = io.BytesIO()
    pisa.CreatePDF(html, dest=buf)
    return Response(buf.getvalue(), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="report_{rid}.pdf"'})


app.mount("/", StaticFiles(directory="static", html=True), name="static")