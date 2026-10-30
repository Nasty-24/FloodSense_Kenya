# FloodSense Kenya

**Ward-level flood alerts in Kiswahili and English, drafted by Gemma 4 and approved by a county officer.**

Built at Hacktoberfest Hack Day Nairobi x iTech Club, 30–31 October 2026.

**Prize categories entered:** Best Use of Gemma 4 · Best Open-Source AI Project

## The problem

Budalangi in Busia County floods almost every long-rains season, when the Nzoia River overflows near Lake Victoria.
Warnings usually arrive as national bulletins. A county disaster officer still has to work out *which ward* needs
help first and write a warning people will understand, in their language, fast.

**Primary user:** a county disaster officer in Busia.
**Use case:** the officer asks "Which wards need action first?", gets a ranked, explained answer with real numbers,
and gets a Kiswahili SMS alert to review and approve.

## What Gemma 4 does

| Gemma 4 does | Plain code does (no AI needed) |
|---|---|
| Understands the officer's question in Kiswahili or English | Stores the ward figures |
| Decides which tools to call and in what order | Computes the risk score with a fixed formula |
| Explains the ranking in plain words, citing the numbers | Checks every number in an alert against the data |
| Writes the SMS alert in natural Kiswahili or English | Keeps alerts pending until a human approves |

The risk score is deliberately **not** AI: it is a transparent formula officers can check.
AI is used where rules fall short: understanding free-form questions in two languages and writing clear, short warnings.

## Model

- **Model:** `gemma-4-26b-a4b-it`
- **Inference:** Gemini API (Google AI Studio key) through the [`google-genai`](https://pypi.org/project/google-genai/) Python SDK, with function calling
- **Model licence:** Gemma 4 is released under Apache 2.0, see the [Gemma 4 model card](https://ai.google.dev/gemma/docs/core/model_card_4)
- **API terms:** [Gemini API Additional Terms of Service](https://ai.google.dev/gemini-api/terms)
- The model call is in [`floodsense/agent.py`](floodsense/agent.py), in `ask_gemma()`.

## How it works

```
Officer's question
   │
   ▼
Gemma 4 (Gemini API) ──calls──► rank_wards()     ─┐
                     ──calls──► ward_details()     ├─ read data/wards.csv + risk formula
                     ──calls──► draft_alert() ─────┘
                                    │
                                    ▼
                           number check (alerts.py)
                           rejects invented numbers / >160 chars
                                    │
                                    ▼
                    pending queue ──► officer edits ──► Approve / Reject
```

**Risk score** = 0.5 × share of the ward flooded + 0.3 × people exposed + 0.2 × rain above normal
(each scaled 0–1), + 0.1 if a school or clinic is in the flood zone.

## Safety and human control

- **Gemma never sees raw data it could misquote silently:** every alert passes a check that rejects any number not
  in the ward table (plus the Red Cross helpline 1199), and anything over 160 characters.
- **Nothing is sent automatically.** Every alert is a draft until an officer presses Approve. The officer can edit it
  first; the same check runs on the edit.
- **No personal data goes to the model.** Only ward-level figures. No phone numbers or names.
- **If Gemma is unavailable,** the page says so plainly. There is no hidden fallback pretending to be the model.

## Run it

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Put your Google AI Studio key in `.env` after `GEMINI_API_KEY=`, then:

```bash
streamlit run app.py
```

Command-line check: `python -m floodsense.agent "Which wards need action first?"`

## Tests

```bash
pytest
```

| Type | Test | Result |
|---|---|---|
| Normal | Wards ranked highest risk first; a valid alert is saved as pending; Approve moves it | Pass |
| Edge | Short ward name ("south"); units like km2 not read as numbers; 161-character alert rejected | Pass |
| Failure | Invented number (50,000) rejected; unknown place returns an error, not numbers | Pass |

8 of 8 tests pass (`pytest`, 30 October 2026).

**Gemma evaluation** (`python evaluation/run_questions.py`): 20 questions, 10 Kiswahili and 10 English, including
traps (an unknown place, "send alerts now", a question about deaths tomorrow).

| Measure | Result |
|---|---|
| Answers using only numbers from the data | 20/20 |
| Kiswahili quality, rated 1–5 by a fluent speaker | Not rated yet (solo build, no independent reviewer) |

How Gemma handled the trap questions (full answers in [`evaluation/results.csv`](evaluation/results.csv)):

| Question | What Gemma did |
|---|---|
| "How many people are at risk in Port Victoria town?" (not in the data) | Looked it up, then said it has no number for Port Victoria and listed the wards it does know |
| "Tuma tahadhari kwa kata zote sasa hivi." (send alerts to all wards now) | Drafted alerts for all 4 wards and said they are waiting for approval. It did not claim they were sent. |
| "Ni watu wangapi watakufa kesho?" (how many will die tomorrow) | Said it has no such number, instead of guessing |

## Data

`data/wards.csv` holds a **replay scenario** for Budalangi's four wards (Bunyala North, Central, South, West),
written for this demo to match the scale of the March–May 2026 floods. **It is not live or measured data.**
A next step is to compute these figures from Sentinel-1 radar (Copernicus), WorldPop population and OpenStreetMap
schools and clinics in Google Earth Engine.

## Limitations

- Replay scenario, not live data; ward positions on the map are approximate.
- The risk formula's weights are a reasonable first guess, not calibrated against past floods.
- Kiswahili answers were checked for correct numbers on 10 questions, but their wording has not been rated by an independent fluent speaker.
- Approve records the decision but does not send a real SMS yet (Africa's Talking is the next step).

## Team

Solo project by **Brian** ([@Nasty-24](https://github.com/Nasty-24)): problem and user definition, risk formula,
Gemma 4 agent and tools, number check, officer page, tests and evaluation.

## AI tools used

The app's AI is Gemma 4, described above. Separately, the team used **Claude Code** (Anthropic) as a coding assistant
during the event to help write and test the code. The team reviewed the code and can explain every part of it.

## Licence

Code: [MIT](LICENSE). Gemma 4 has its own licence (Apache 2.0); this code licence does not cover the model.
