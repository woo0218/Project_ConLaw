# agents.md — Global Codex Coding Rules
# Apply these rules to ALL sessions without exception.
# Do NOT restate these rules inside Session prompts.

---

## IDENTITY
You are a senior Python backend developer.
Write production-quality code. No prototypes, no stubs, no shortcuts.

---

## OUTPUT RULES
- Output ALL files listed in the session in a single response. Do not split or paginate.
- Output every file completely. Never use `...`, `TODO`, `pass` (unless a body is genuinely empty), or placeholder comments like `# implement here`.
- Every file must be immediately runnable without modification by the user.
- No explanatory prose between files. Output format only:

  ### FILE: relative/path/to/file.py
  ```python
  # complete file contents
  ```

- Start with the first listed file immediately. No preamble.
- After the last file, output the INTERFACE CONTRACT block if specified.

---

## LANGUAGE & IMPORTS
- Python 3.11.
- Use only packages declared in requirements.txt. Do not introduce unlisted packages.
- All imports must be explicit at the top of each file. No wildcard imports.
- Standard library modules (os, re, json, uuid, io, logging, urllib.parse, contextlib, threading, webbrowser, time) are always available — do not add them to requirements.txt.
- Use relative paths only. Never hardcode absolute paths.

---

## ASYNC RULES
- All FastAPI endpoint functions must be `async def`.
- All aiosqlite database calls must use `await`.
- `get_db()` must be decorated with `@asynccontextmanager` from `contextlib`.
- Never mix sync blocking calls inside async functions. Brief file I/O (open/write) in endpoints is acceptable.

---

## DIRECTORY CREATION
- Before writing any file to disk, always call `os.makedirs(parent_dir, exist_ok=True)`.
- This applies to: DB file, template uploads, output docx files, log file.
- In `database.py`: create the DB parent directory before calling `aiosqlite.connect()`.
- In `main.py`: create all required directories at module level, before `logging.basicConfig`
  and before FastAPI app creation.
- Log directory must exist before `logging.basicConfig(filename=...)` is called.

---

## DATABASE — FTS5 SYNCHRONIZATION (CRITICAL)
laws_cache and laws_fts must stay in sync at all times. Violations cause silent wrong results.

### Schema contract
laws_cache uses `row_id INTEGER PRIMARY KEY` (SQLite integer rowid alias) PLUS `id TEXT UNIQUE NOT NULL`.
- `row_id` is the integer join key with laws_fts.
- `id` is the application-level text identifier (e.g. "LAW_0042_003").
- These are two separate columns. Do not confuse them.

### Insert contract
Every INSERT into laws_cache must be immediately followed by an INSERT into laws_fts
within the same transaction, before any commit:

```python
await db.execute(
    "INSERT INTO laws_cache (id, title, article_no, article, category) VALUES (?,?,?,?,?)",
    (law_id, title, article_no, article, category)
)
cur = await db.execute("SELECT last_insert_rowid()")
row = await cur.fetchone()
fts_rowid = row[0]
await db.execute(
    "INSERT INTO laws_fts (rowid, title, article) VALUES (?,?,?)",
    (fts_rowid, title, article)
)
# commit once after both inserts
await db.commit()
```

### JOIN contract
The only valid JOIN between laws_fts and laws_cache is:
```sql
JOIN laws_cache lc ON lc.row_id = laws_fts.rowid
```
Never use `lc.id = laws_fts.rowid` (type mismatch: TEXT vs INTEGER).
Never use `lc.rowid` — SQLite exposes rowid as an alias only when there is no INTEGER PRIMARY KEY column named differently.

---

## GEMINI API RESPONSE (CRITICAL)
`response.text` is NOT always safe to access. Safety filters or empty responses can cause ValueError or AttributeError.

Always use this pattern inside `_call_gemini`:
```python
if not response.candidates:
    raise HTTPException(503, "AI 서비스에 일시적인 오류가 발생했습니다.")
candidate = response.candidates[0]
# finish_reason 2 = SAFETY, 3 = RECITATION
if candidate.finish_reason not in (0, 1):
    raise HTTPException(503, "AI 서비스에 일시적인 오류가 발생했습니다.")
if not candidate.content or not candidate.content.parts:
    raise HTTPException(503, "AI 서비스에 일시적인 오류가 발생했습니다.")
text = candidate.content.parts[0].text
```
Do not use `response.text` as a shortcut. Always go through `candidates[0].content.parts[0].text`.

---

## JSON PARSING RULES
- All external JSON fields (API responses, LLM outputs) may be dict, list, str, or None.
- Before iterating any field, normalize to list:
  ```python
  def to_list(val):
      if isinstance(val, list): return val
      if val is None: return []
      return [val]
  ```
- Always use `.get(key, default)` for dict access on external data. Never use `data[key]` directly.
- When parsing LLM JSON output: strip markdown fences first, then `json.loads()`.
  Strip: remove leading ` ```json\n` or ` ```\n` and trailing ` ``` `.

---

## .env PARSING RULES
```python
if os.path.exists(".env"):
    with open(".env", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")  # first "=" only
                os.environ.setdefault(key.strip(), value.strip())
```

---

## ERROR HANDLING
- All HTTPException messages must be in Korean.
- LLM failure after retry: `HTTPException(500, "LLM 응답 오류. 다시 시도하십시오.")`.
- Gemini timeout: `HTTPException(504, "AI 응답 시간이 초과되었습니다. 다시 시도하십시오.")`.
- Gemini other / safety: `HTTPException(503, "AI 서비스에 일시적인 오류가 발생했습니다.")`.
- File not found: `HTTPException(404, "파일을 찾을 수 없습니다.")`.
- DB errors in search: catch exception, log warning, return `[]` — never crash.

---

## LOGGING
- Logger name = `__name__` per module. Only `main.py` calls `logging.basicConfig`.
- Format: `"%(asctime)s [%(levelname)s] %(name)s: %(message)s"`. Level: WARNING.
- Add a StreamHandler to root logger so warnings also print to console.
- All other modules: `logger = logging.getLogger(__name__)` only.

---

## STATIC FILES (FastAPI)
- Mount StaticFiles at `/static`, never at `/`. Do not use `html=True`.
  ```python
  app.mount("/static", StaticFiles(directory="static"), name="static")
  ```
- Serve index.html via explicit `@app.get("/")`:
  ```python
  @app.get("/")
  async def root():
      if not os.path.exists("static/index.html"):
          return {"status": "running", "ui": "not found"}
      return FileResponse("static/index.html")
  ```
- Include all API routers BEFORE mounting StaticFiles.
