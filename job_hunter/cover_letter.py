"""A cover letter written for one job, from the same facts as your resume."""

from __future__ import annotations

import json
from datetime import date

import anthropic
from pydantic import BaseModel, Field

from .resume import FALLBACK_BETA, MODEL, _NUMBER, _norm_number, job_prompt


class CoverLetter(BaseModel):
    greeting: str = Field(description="e.g. 'Dear Hiring Manager,' or 'Dear <named person>,' only if the posting names one")
    paragraphs: list[str] = Field(description="3 or 4 paragraphs")
    closing: str = Field(description="e.g. 'Sincerely,'")


SYSTEM = """You write a cover letter for one job posting from the job seeker's own resume.

Rules:
- Use only facts in the resume provided. Never invent employers, titles, tools, certifications, numbers or results.
- 3 or 4 short paragraphs, under 350 words in total, in plain confident first person. No cliches such as "I am writing to express my interest".
- Paragraph 1: the role and the single strongest reason they fit it. Paragraph 2-3: two or three concrete accomplishments from the resume that match what the posting asks for, using its vocabulary where it truthfully applies. Last paragraph: availability and a short close.
- If the posting values a security clearance, mention the clearance. If the person is transitioning from the military, frame it as an asset in one sentence, not an apology.
- Do not mention skills the resume lacks, and do not apologize for gaps.
- Address the hiring manager by name only if the posting names one; otherwise use "Dear Hiring Manager,"."""


def write(resume: dict, job: dict, client: anthropic.Anthropic | None = None, model: str = MODEL,
          effort: str = "high") -> CoverLetter:
    """Write a cover letter for `job` from `resume` (the tailored one if you have it)."""
    client = client or anthropic.Anthropic()
    resume_for_model = {k: v for k, v in resume.items() if k != "contact"}
    response = client.beta.messages.parse(
        model=model,
        max_tokens=16000,
        betas=[FALLBACK_BETA],
        fallbacks="default",
        output_config={"effort": effort},
        output_format=CoverLetter,
        system=[{"type": "text", "text": SYSTEM}],
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "Resume (JSON):\n" + json.dumps(resume_for_model, indent=1)},
                {"type": "text", "text": job_prompt(job)},
            ],
        }],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined to write this cover letter. Try again or edit the posting text.")
    if response.stop_reason == "max_tokens" or response.parsed_output is None:
        raise RuntimeError("Claude's answer was cut off before the letter was complete. Try again.")
    return response.parsed_output


def check_facts(master: dict, letter: CoverLetter) -> list[str]:
    source_numbers = {_norm_number(n) for n in _NUMBER.findall(json.dumps(master, ensure_ascii=False))}
    warnings = []
    for paragraph in letter.paragraphs:
        for number in _NUMBER.findall(paragraph):
            if _norm_number(number) not in source_numbers:
                warnings.append(f"Check the number {number!r} in: {paragraph[:120]}...")
    return warnings


def as_document(letter: CoverLetter, contact: dict, job: dict, today: date | None = None) -> dict:
    """Everything the exporters need, with the letterhead and date filled in."""
    return {
        "contact": contact,
        "date": (today or date.today()).strftime("%B %d, %Y").replace(" 0", " "),
        "recipient": [job.get("company", ""), job.get("location", "")],
        "subject": f"Re: {job['title']}",
        "greeting": letter.greeting,
        "paragraphs": letter.paragraphs,
        "closing": letter.closing,
        "signature": contact["name"],
    }


def as_text(document: dict) -> str:
    lines = [document["date"], "", *[x for x in document["recipient"] if x], "", document["subject"], "",
             document["greeting"], ""]
    for paragraph in document["paragraphs"]:
        lines += [paragraph, ""]
    lines += [document["closing"], document["signature"]]
    return "\n".join(lines)
