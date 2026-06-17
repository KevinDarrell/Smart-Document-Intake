import json

from fastapi import HTTPException

from . import config


def build_answer_prompt(question: str, context: str):
    return (
        "Answer the question using ONLY the documents below. Cite the doc ids you used. "
        "If the answer is not in the documents, say you don't know. "
        "Do not use outside knowledge. Keep citations inline like [doc 1].\n\n"
        f"{context}\n\nQUESTION: {question}"
    )


def summarize_document(title: str, body: str):
    try:
        config.require_deepseek_key()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    prompt = (
        "Summarize the document in one sentence and extract exactly 3 key facts. "
        'Return JSON: {"summary": string, "facts": [string, string, string]}.\n\n'
        f"TITLE: {title}\n\nBODY:\n{body}"
    )
    try:
        resp = config.client.chat.completions.create(
            model=config.MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="The document summary response was not valid JSON. Please retry.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Document summarization failed: {exc}")


def stream_answer(prompt: str):
    config.require_deepseek_key()
    return config.client.chat.completions.create(
        model=config.MODEL,
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )
