# Kuwait CAL Executive Priority Dashboard Agent (`google-adk` 2.x)

Automated **Google Agent Development Kit (ADK)** Python agent for **Willem Clappaert** (`clappaert@google.com`, Consulting Account Lead, Google Cloud Kuwait).

Every **Sunday at 6:00 AM (`Asia/Kuwait` time)**, this agent:
1. **Ingests Live Google Workspace Context in Parallel (`JoinNode`)**:
   - Google Calendar (`gcalendar readonly list`)
   - Gmail Inbox, Sent Mail & Gemini Meeting Notes (`gmail readonly search` / `read`)
   - Commit Period 3 (CP3) External Commit Attainment & PSF/TIF Google Sheets (`gsheets readonly read`)
   - Go Links, CAL Overview Doc, Alotaibi Rolling Minutes, Kuwait Weekly Deck & PSO Delivery Board (`gdocs` / `gslides readonly read`)
2. **Synthesizes 4 Domain Pillars via Pydantic-Validated `LlmAgent` Nodes**:
   - `todo_and_reminders_agent`: Top 10 Priority To-Do List (`THIS WEEK` vs. `NEXT WEEK` + `Due Date`) & 2–5 Day Colleague Action Reminder Tracker.
   - `pso_risks_agent`: PSO Project Portfolio Status, KPIs & RAG Risks/Issues across ServiceNow (`$60M` MP Cap), SOW3 Migration Factory, Digital Resilience (`$3.67M`), National Skilling (`37.5%` TIF waste), GovShield, MoE, Apigee Ph2, and Data Platform.
   - `afa_financials_agent`: CP3 Attainment, Roll-Overs/Shortfalls, Consumed/Approved, WIP Pipelines & Gaps across **GCP, PSO, Workspace, PSF, TIF, and Cloud Credits**.
   - `innovation_radar_agent`: 3 Weekly Net-New Digital Transformation & Gemini Enterprise Ideas for the Kuwait Government (Use Cases, Business Value & Public Sector References).
3. **Renders a 6-Slide Google Slides Executive Dashboard**:
   - Follows Setproduct Executive Dashboard design principles (5 headline KPIs above the fold, RAG status badges, dark-light-dark sandwich palette, zero text overlap).
4. **Verifies Quality & Guardrails via an Independent `llm_judge_agent` Loop**:
   - Audits the presentation across a 6-point rubric (`overall_score >= 9.0` required; routes to `revise_dashboard_agent` if any criterion fails).
5. **Emails the Presentation Link to Willem & Enforces the Colleague Consent Gate**:
   - Automatically sends the weekly digest & Google Slides link **only to `clappaert@google.com`**.
   - Uses ADK's `RequestInput` Human-in-the-Loop interrupt for colleague reminders so **zero external/colleague emails are ever sent without explicit approval**.

---

## Quick Start

### 1. Run with Google ADK CLI (`adk run` / `adk web`)
```bash
uv venv --python python3.11 .venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Run in terminal or launch the ADK Web UI:
adk run kuwait_cal_agent
adk web kuwait_cal_agent
```

### 2. Run Directly via Python CLI (`--once`, `--interactive`, `--daemon`)
```bash
# Execute one unattended Sunday 6am run (creates 6-slide deck, runs Judge, emails link to clappaert@google.com):
python3 run_sunday_dashboard.py --once

# Execute a dry run (validates the full 5-stage ADK Workflow graph without external mutations):
python3 run_sunday_dashboard.py --once --dry-run

# Run interactively (pauses at the RequestInput consent gate for 2-5d colleague reminders):
python3 run_sunday_dashboard.py --interactive

# Run the continuous Sunday 06:00 Asia/Kuwait scheduler daemon:
python3 run_sunday_dashboard.py --daemon
```

### 3. Run Unit & Workflow Integration Tests
```bash
python3 -m unittest discover -s tests -v
# Or with pytest:
pytest
```
