"""Asks Gemma the 20 test questions and checks every number in its answers against the ward data.

    .venv\\Scripts\\python evaluation\\run_questions.py

Writes evaluation/results.csv. Fill in the swahili_quality column (1-5) by hand.
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from floodsense import alerts  # noqa: E402
from floodsense.agent import ask_gemma  # noqa: E402
from floodsense.alerts import numbers_in  # noqa: E402
from floodsense.wards import load_wards  # noqa: E402

HERE = Path(__file__).parent


def known_numbers() -> set[float]:
    known = {1, 2, 3, 4, 160, 1199, 2020, 2023, 2026}  # ranks, SMS limit, helpline, data years
    for value in load_wards().select_dtypes("number").to_numpy().ravel():
        known |= {float(value), float(round(value)), round(float(value), 1)}
    return known


def main():
    alerts.QUEUE = HERE / "eval_alerts.json"  # keep test drafts out of the real queue
    known = known_numbers()
    rows = []
    questions = [q for q in (HERE / "questions.txt").read_text(encoding="utf-8").splitlines() if q.strip()]
    for i, q in enumerate(questions, start=1):
        try:
            reply = ask_gemma(q)
            unknown = sorted({n for n in numbers_in(reply["answer"]) if n not in known})
            rows.append({"id": i, "question": q, "numbers_ok": "yes" if not unknown else "no",
                         "unknown_numbers": " ".join(f"{n:g}" for n in unknown),
                         "tools": " ".join(c["tool"] for c in reply["tool_calls"]),
                         "swahili_quality": "", "answer": reply["answer"], "error": ""})
        except Exception as exc:
            rows.append({"id": i, "question": q, "numbers_ok": "error", "unknown_numbers": "", "tools": "",
                         "swahili_quality": "", "answer": "", "error": str(exc)})
        print(f"{i:>2} {rows[-1]['numbers_ok']:>5}  {q}")

    with open(HERE / "results.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    ok = sum(r["numbers_ok"] == "yes" for r in rows)
    print(f"\nCorrect numbers: {ok}/{len(rows)}. Saved evaluation/results.csv")


if __name__ == "__main__":
    main()
