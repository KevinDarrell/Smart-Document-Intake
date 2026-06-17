# Full-Stack Engineer Take-Home — Smart Document Intake

You're starting from a small, **working** full-stack app (`backend/` FastAPI + `frontend/` Next.js): add documents → an LLM summarizes + extracts fields → ask questions answered only from your documents, with citations, refusing when the answer isn't there. Get it running (see `README.md`), click around, and read the code.

**Timebox ~8 hours (a weekend). Completion is NOT expected — we grade prioritization and effectiveness, not how much you cram. A rock-solid Part 1 beats a broad, shallow pile.**

## Part 1 — the core challenge
**First, write a short ranked audit** (a few bullets in `SOLUTION.md`): the top production risks you'd fix before real users hit this app, most serious first.

**Then improve `/ask` for this reality:** users are on **flaky mobile connections**, sometimes **double-tap** submit, and often **navigate away mid-answer and come back**. It should:
- **stream** the answer as it's generated (not one long wait, then a dump),
- **survive interruption** — a dropped connection or navigating away mid-answer must not lose the result; coming back recovers it,
- never **duplicate work** on a double-submit.

How you achieve this is entirely your call — there's no single right answer, and we care most about *how you reason about it*.

## Part 2 — audio
Turn a short multi-turn dialogue (a 6–10 turn, two-speaker roleplay — sample in `sample_dialogue.json`) into audio that **starts playing fast** (low time-to-first-sound) and plays smoothly through every turn in **distinct voices**. [uses the Gemini key]

Submit **either** a thin working slice **or** a one-page design note (how you'd hit low latency, what's finicky, how you'd validate it). **A strong design note beats a fragile demo** — we're after your reasoning about latency, ordering, buffering, and partial failure, not a polished codec wrestle.

## Deliverables
Code (Git repo link or zip) + a short **`SOLUTION.md`** containing:
- your **Part 1 audit** (ranked risks),
- how to run your version,
- **what you prioritized, what you cut, and why,**
- **what failure modes still remain** and what you'd do next,
- your **Part 2** slice or design note.

**Don't commit the API keys** — read them from environment variables. Questions any time. Good luck!
