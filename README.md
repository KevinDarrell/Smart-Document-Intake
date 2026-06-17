# Full-Stack Engineer Take-Home

Hi Kevin — thanks for making time. Everything you need is in this folder; the task is in **TAKEHOME.md**.

## API keys
Set the provided API keys in your local environment before running the app. Do **not** commit API keys or local `.env` files.

- **DeepSeek** (the core app, Part 1): `DEEPSEEK_API_KEY`
- **Gemini** (Part 2 — audio): `GEMINI_API_KEY`

DeepSeek is OpenAI-compatible (base URL `https://api.deepseek.com`, model `deepseek-chat`). Gemini uses Google AI Studio (e.g. model `gemini-2.5-flash`; confirm current names at https://ai.google.dev).

## Run the baseline
**Backend** (FastAPI):

    cd backend
    python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    export DEEPSEEK_API_KEY=your_deepseek_api_key                            # Windows PowerShell: $env:DEEPSEEK_API_KEY="your_deepseek_api_key"
    uvicorn main:app --reload --port 8000

**Frontend** (Next.js, separate terminal):

    cd frontend
    npm install
    printf "NEXT_PUBLIC_BACKEND_URL=http://localhost:8000\n" > .env.local
    npm run dev                                             # open http://localhost:3000

Add a couple of documents (samples in `sample_documents.json`), then try **Ask**.

> If the frontend baseline gives you any trouble, feel free to scaffold your own with `create-next-app` — what we care about is the behaviour described in TAKEHOME.md, not our scaffold.

## Submit
Push to a Git repo and share the link (or zip it back), including your **SOLUTION.md** (Part 1 audit + run steps + what you prioritized/cut + remaining failure modes + your Part 2 slice or design note). Don't include the keys.

Good luck — we're excited to see how you think.
