"""The Gemma 4 agent. Gemma reads the ward data only through these tools,
explains which wards need help first, and drafts SMS alerts for officer approval.
"""

import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

from floodsense.alerts import add_draft, check_alert
from floodsense.wards import SOURCE, find_ward, load_wards

load_dotenv()
MODEL = os.getenv("GEMMA_MODEL", "gemma-4-26b-a4b-it")

RULES = """You are FloodSense, an assistant for county disaster officers in Budalangi, Busia County, Kenya.

Rules:
1. Only state numbers that a tool gave you. If you don't have a number, say so. Never guess.
2. Say once where the figures come from, using the "source" a tool gives you. They describe the
   April-May 2026 floods (a past event), not today's situation.
3. Alerts are only drafts. Never say an alert was sent; say it is waiting for the officer's approval.
4. Reply in the language the officer used (Kiswahili or English). Be short and clear.

For "which wards need action": call rank_wards, then explain the top 3 using their numbers.
To draft an alert, call draft_alert. An alert is one SMS under 160 characters: the ward name,
the danger in numbers from the tools, one clear action (move to high ground, collect children
early, do not cross flood water), and the Red Cross line 1199. Write natural Kenyan Kiswahili.
If draft_alert reports problems, fix them and try again.

Officer's message:
"""


def rank_wards(top_n: int = 3) -> dict:
    """Rank Budalangi's wards by flood risk, highest first.

    Args:
        top_n: How many wards to return.
    """
    df = load_wards().head(max(1, int(top_n)))
    cols = ["ward", "risk_score", "flooded_km2", "flooded_pct", "people_exposed",
            "schools_flooded", "clinics_flooded", "rain_vs_normal"]
    return {"wards": df[cols].to_dict(orient="records"), "source": SOURCE}


def ward_details(ward: str) -> dict:
    """Get all flood figures for one ward.

    Args:
        ward: Ward name, for example "Bunyala South".
    """
    row = find_ward(ward)
    if row is None:
        return {"error": f"No ward called '{ward}'. Known wards: {', '.join(load_wards()['ward'])}."}
    return {**row, "source": SOURCE}


def draft_alert(ward: str, language: str, text: str) -> dict:
    """Save an SMS alert draft for one ward. It waits for the officer's approval and is never sent automatically.

    Args:
        ward: Ward name.
        language: "sw" for Kiswahili or "en" for English.
        text: The alert, under 160 characters, using only numbers from the tools.
    """
    row = find_ward(ward)
    if row is None:
        return {"error": f"No ward called '{ward}'."}
    problems = check_alert(text, row)
    if problems:
        return {"rejected": True, "problems": problems}
    alert = add_draft(row["ward"], language, text)
    return {"saved": True, "status": "pending approval", "id": alert["id"]}


TOOLS = [rank_wards, ward_details, draft_alert]


def ask_gemma(message: str) -> dict:
    """Send the officer's message to Gemma 4 and return its answer plus the tool calls it made."""
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    response = client.models.generate_content(
        model=MODEL,
        contents=RULES + message,
        config=types.GenerateContentConfig(
            tools=TOOLS,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(maximum_remote_calls=12),
        ),
    )
    calls = []
    for content in response.automatic_function_calling_history or []:
        for part in content.parts or []:
            if part.function_call:
                calls.append({"tool": part.function_call.name, "args": dict(part.function_call.args or {})})
    return {"answer": response.text or "", "tool_calls": calls, "model": MODEL}


if __name__ == "__main__":
    import sys

    result = ask_gemma(" ".join(sys.argv[1:]) or "Which wards need action first?")
    for call in result["tool_calls"]:
        print(f"  tool: {call['tool']}({call['args']})")
    print(result["answer"])
