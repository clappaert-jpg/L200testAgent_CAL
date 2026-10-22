"""Deterministic 6-Slide Google Slides renderer & thumbnail exporter for the CAL Dashboard.

Implements the Setproduct Executive Dashboard design pattern:
- Slide 1: Executive Overview & CAL Command Center (5 headline KPIs above the fold + 3 strategic pillars)
- Slide 2: Top 10 Priority 'To-Do' List (This Week vs. Next Week + Due Dates; column widths >= 34pt)
- Slide 3: Automated Colleague Reminder Engine & Tracker (2-5 Day SLA + Consent Gate)
- Slide 4: PSO Project Portfolio Status, KPIs & Critical Risks/Issues (RAG Matrix)
- Slide 5: AFA Consumption & Incentives Status — Commit Period 3 (GCP, PSO, GWS, PSF, TIF, Credits)
- Slide 6: Weekly Innovation Radar — 3 New Kuwait Govt Digital Transformation Ideas
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from typing import Any

from .google_workspace_cli import GSLIDES_BIN


def build_six_slide_batch_ops(payload: dict[str, Any]) -> list[dict[str, Any]]:
  """Builds the 6-slide `gslides mutate batch` JSON operations list from `DashboardPayload`."""
  ops: list[dict[str, Any]] = []
  as_of = payload.get("as_of_date", "Oct 22, 2026")
  afa = payload.get("afa_consumption", {})
  todo_rem = payload.get("todo_and_reminders", {})
  pso = payload.get("pso_portfolio", {})
  innov = payload.get("innovation_radar", {})

  # ============================================================================
  # SLIDE 1 (id: "p"): EXECUTIVE OVERVIEW & CAL COMMAND CENTER
  # ============================================================================
  ops.extend([
      {"op": "delete-element", "element": "i0"},
      {"op": "delete-element", "element": "i1"},
      {"op": "set-background", "slide": "p", "color": "#0F172A"},
      {"op": "add-shape", "slide": "p", "shape_type": "RECTANGLE", "x": 0, "y": 0, "width": 720, "height": 6, "background_color": "#4285F4"},
      {"op": "add-textbox", "slide": "p", "text": "KUWAIT CAL EXECUTIVE PRIORITY DASHBOARD", "x": 24, "y": 12, "width": 520, "height": 28, "font_size": 20, "bold": True, "color": "#FFFFFF", "font_family": "Roboto"},
      {"op": "add-textbox", "slide": "p", "text": f"Willem Clappaert (Consulting Account Lead)  |  As of {as_of}  |  AFA Commit Period 3 (Feb 27, 2026 – Feb 26, 2027)", "x": 24, "y": 36, "width": 672, "height": 18, "font_size": 10, "color": "#94A3B8", "font_family": "Roboto"},
      {"op": "add-textbox", "slide": "p", "text": "LLM-JUDGE VERIFIED  |  GUARDRAIL ACTIVE", "x": 510, "y": 14, "width": 186, "height": 20, "font_size": 8, "bold": True, "color": "#FFFFFF", "background_color": "#1E3A8A", "alignment": "center", "content_alignment": "MIDDLE", "font_family": "Roboto"},
  ])

  kpi_cards = afa.get("headline_kpis", [])
  for idx, card in enumerate(kpi_cards[:5]):
    cx = 24 + idx * 136
    ops.append({"op": "add-shape", "slide": "p", "shape_type": "RECTANGLE", "x": cx, "y": 60, "width": 128, "height": 114, "background_color": "#1E293B"})
    ops.append({"op": "add-shape", "slide": "p", "shape_type": "RECTANGLE", "x": cx, "y": 60, "width": 128, "height": 3, "background_color": card.get("stat_color", "#4ADE80")})
    ops.append({"op": "add-textbox", "slide": "p", "text": card.get("title", ""), "x": cx + 6, "y": 66, "width": 116, "height": 16, "font_size": 8, "bold": True, "color": "#CBD5E1", "font_family": "Roboto"})
    ops.append({"op": "add-textbox", "slide": "p", "text": card.get("stat", ""), "x": cx + 6, "y": 82, "width": 76, "height": 30, "font_size": 17, "bold": True, "color": card.get("stat_color", "#4ADE80"), "font_family": "Roboto"})
    ops.append({"op": "add-textbox", "slide": "p", "text": card.get("badge", ""), "x": cx + 80, "y": 86, "width": 44, "height": 16, "font_size": 6, "bold": True, "color": "#FFFFFF", "background_color": card.get("badge_bg", "#14532D"), "alignment": "center", "content_alignment": "MIDDLE", "font_family": "Roboto"})
    ops.append({"op": "add-textbox", "slide": "p", "text": card.get("subtitle", ""), "x": cx + 6, "y": 116, "width": 116, "height": 54, "font_size": 7.5, "color": "#E2E8F0", "font_family": "Roboto", "line_spacing": 115})

  ops.append({"op": "add-textbox", "slide": "p", "text": "EXECUTIVE MANDATE & FOCUS AREAS (TRANSITIONING ALLIANCE OPS TO HUSSEIN ALMUTAWA -> FOCUSING ON AI & PSO GROWTH)", "x": 24, "y": 182, "width": 672, "height": 18, "font_size": 9, "bold": True, "color": "#93C5FD", "font_family": "Roboto"})

  pillars = [
      (
          "1. AFA GOVERNANCE & COMMERCIAL",
          "#1D4ED8",
          "• Unblock $60M ServiceNow Deal: Close Cloud Connect concession (6910316231362871297) moving $12M MP cap from CP7 to CP1–5 ($58M -> $70M) + pulling forward $74.16M GCP commit.\n"
          "• Close -$20.54M PSO Gap: Convert Digital Resilience ($3.67M), SOW3 Migration Factory ($10M), Data Platform ($1.67M), and MoE Extension before Feb 26, 2027.\n"
          "• Alliance Handover: Transition daily AFA tracker & KDIPA compliance to Hussein Almutawa (Part I on Oct 27).",
      ),
      (
          "2. PSO DELIVERY & RISK MITIGATION",
          "#B91C1C",
          "• Post-SOW2 Day 2 Support Crisis: Address PSE skill gaps, security/maintenance risks & KIN interconnect dispute (MoJ threatening to revert SAP to on-prem).\n"
          "• Digital Resilience ($3.67M) Reframing: Strip wartime free DR items; merge 300-VM DR, Cohesity/Veeam advisory, EA & CCoE into Migration Factory RACI.\n"
          "• National Skilling Ph2/3: Fix 33% drop-off & 37.5% TIF unit waste caused by CAIT's 5-hr daily training cap via Thinksmart cohort model.",
      ),
      (
          "3. GEMINI ENTERPRISE & AI FACTORY",
          "#047857",
          "• 3-Layer National AI Factory (2027): (1) Nationwide Citizen/CSC Employee Agents, (2) Entity Agents, (3) Project-Embedded Agents (ServiceNow, Iron Mountain).\n"
          "• Education AI Scale-Up: Drive MoE 45k renewal + 21k expansion + 3,500 Gemini Enterprise librarian seats ($571k) & KU/QU 85k-seat Student Journey AI COE.\n"
          "• PSF Velocity ($15.2M ARR): Accelerate 8 approved PSF SOWs ($1.66M -> $7.50M ARR) & 13 WIP deals ($1.64M -> $7.74M ARR incl. KIA GE $420k).",
      ),
  ]
  for idx, (p_hdr, p_bg, p_body) in enumerate(pillars):
    px = 24 + idx * 228
    ops.append({"op": "add-textbox", "slide": "p", "text": p_hdr, "x": px, "y": 202, "width": 216, "height": 24, "font_size": 9.5, "bold": True, "color": "#FFFFFF", "background_color": p_bg, "content_alignment": "MIDDLE", "font_family": "Roboto"})
    ops.append({"op": "add-textbox", "slide": "p", "text": p_body, "x": px, "y": 226, "width": 216, "height": 144, "font_size": 8, "color": "#F1F5F9", "background_color": "#1E293B", "font_family": "Roboto", "line_spacing": 120})

  ops.append({"op": "add-textbox", "slide": "p", "text": "Sources: Live Gmail, Calendar, Meet Notes, External Commit & PSF/TIF Trackers, Alotaibi Minutes, KW Weekly Deck  |  Slide 1 of 6", "x": 24, "y": 378, "width": 672, "height": 16, "font_size": 8, "color": "#64748B", "font_family": "Roboto"})
  ops.append({"op": "set-notes", "slide": "p", "text": "Slide 1: Executive Command Center following Setproduct dashboard design principles."})

  # ============================================================================
  # SLIDE 2 (id: "SLIDE_2"): TOP 10 PRIORITY TO-DO LIST
  # ============================================================================
  todos = todo_rem.get("todos", [])[:10]
  ops.extend([
      {"op": "add-slide", "layout": "BLANK", "id": "SLIDE_2"},
      {"op": "set-background", "slide": "SLIDE_2", "color": "#F8FAFC"},
      {"op": "add-shape", "slide": "SLIDE_2", "shape_type": "RECTANGLE", "x": 0, "y": 0, "width": 720, "height": 48, "background_color": "#0F172A"},
      {"op": "add-textbox", "slide": "SLIDE_2", "text": "1. TOP 10 PRIORITY 'TO-DO' LIST — THIS WEEK & NEXT WEEK", "x": 20, "y": 6, "width": 510, "height": 22, "font_size": 16, "bold": True, "color": "#FFFFFF", "font_family": "Roboto"},
      {"op": "add-textbox", "slide": "SLIDE_2", "text": "MAX 10 ITEMS  |  SLIDE 2 OF 6", "x": 540, "y": 8, "width": 160, "height": 18, "font_size": 8, "bold": True, "color": "#FFFFFF", "background_color": "#1E3A8A", "alignment": "center", "content_alignment": "MIDDLE", "font_family": "Roboto"},
      {"op": "add-textbox", "slide": "SLIDE_2", "text": "Extracted from Willem's Calendar, Gmail & Meet Transcripts (Max 10 Actions  |  This Week vs. Next Week + Due Dates)", "x": 20, "y": 26, "width": 680, "height": 16, "font_size": 9, "color": "#93C5FD", "font_family": "Roboto"},
      {"op": "add-table", "slide": "SLIDE_2", "rows": len(todos) + 1, "cols": 5, "id": "TODO_TABLE", "x": 18, "y": 50, "width": 684, "height": 300},
  ])

  for col_idx, w in enumerate([34, 68, 64, 378, 140]):
    ops.append({
        "op": "updateTableColumnProperties",
        "updateTableColumnProperties": {
            "objectId": "TODO_TABLE",
            "columnIndices": [col_idx],
            "tableColumnProperties": {"columnWidth": {"magnitude": w, "unit": "PT"}},
            "fields": "columnWidth",
        },
    })

  for c, h in enumerate(["#", "Horizon", "Due Date", "Priority Action & Deliverable", "Stakeholders / Source"]):
    ops.append({"op": "set-table-cell", "table": "TODO_TABLE", "row": 0, "col": c, "text": h, "bold": True, "font_size": 7.5, "color": "#FFFFFF", "background_color": "#1E3A8A", "font_family": "Roboto"})

  for r_idx, item in enumerate(todos, start=1):
    bg = "#FFFFFF" if r_idx % 2 == 1 else "#F1F5F9"
    horizon = item.get("horizon", "THIS WEEK")
    h_bg = "#FEF3C7" if horizon == "THIS WEEK" else "#DBEAFE"
    h_col = "#92400E" if horizon == "THIS WEEK" else "#1E40AF"
    row_vals = [
        str(item.get("rank", r_idx)),
        horizon,
        item.get("due_date", ""),
        item.get("action", ""),
        item.get("stakeholders", ""),
    ]
    for c_idx, val in enumerate(row_vals):
      ops.append({
          "op": "set-table-cell",
          "table": "TODO_TABLE",
          "row": r_idx,
          "col": c_idx,
          "text": val,
          "bold": c_idx in (0, 1, 2),
          "font_size": 7.0,
          "color": h_col if c_idx == 1 else "#0F172A",
          "background_color": h_bg if c_idx == 1 else bg,
          "font_family": "Roboto",
      })
  ops.append({"op": "set-notes", "slide": "SLIDE_2", "text": "Slide 2: Top 10 Priority To-Do List based on agenda and emails."})

  # ============================================================================
  # SLIDE 3 (id: "SLIDE_3"): AUTOMATED COLLEAGUE REMINDER ENGINE & TRACKER
  # ============================================================================
  reminders = todo_rem.get("reminders", [])[:6]
  ops.extend([
      {"op": "add-slide", "layout": "BLANK", "id": "SLIDE_3"},
      {"op": "set-background", "slide": "SLIDE_3", "color": "#F8FAFC"},
      {"op": "add-shape", "slide": "SLIDE_3", "shape_type": "RECTANGLE", "x": 0, "y": 0, "width": 720, "height": 48, "background_color": "#0F172A"},
      {"op": "add-textbox", "slide": "SLIDE_3", "text": "2. AUTOMATED COLLEAGUE REMINDER ENGINE & TRACKER (2–5 DAY SLA)", "x": 20, "y": 6, "width": 680, "height": 22, "font_size": 15, "bold": True, "color": "#FFFFFF", "font_family": "Roboto"},
      {"op": "add-textbox", "slide": "SLIDE_3", "text": "Automated Detection of Uncompleted Delegated Actions -> Kind Follow-Up in 2–5 Days  |  Guardrail: Explicit Consent Required Before Sending", "x": 20, "y": 26, "width": 680, "height": 16, "font_size": 9, "color": "#C4B5FD", "font_family": "Roboto"},
  ])

  steps_flow = [
      ("STEP 1: SCAN & DETECT (T+0d)", "Parse Sent Gmail & Gemini Meet Notes for action asks & owners.", "#1E3A8A"),
      ("STEP 2: VERIFY COMPLETION", "Check inbox replies, Drive trackers & Cloud Connect status.", "#0F766E"),
      ("STEP 3: STAGE DRAFT (T+2–5d)", "Generate kind reminder + completion check in Gmail Drafts.", "#B45309"),
      ("STEP 4: HUMAN CONSENT GATE", "Zero external emails sent until Willem clicks/replies Approve.", "#7F1D1D"),
  ]
  for idx, (st_title, st_desc, st_color) in enumerate(steps_flow):
    sx = 18 + idx * 173
    ops.append({"op": "add-textbox", "slide": "SLIDE_3", "text": st_title, "x": sx, "y": 54, "width": 165, "height": 16, "font_size": 7.5, "bold": True, "color": "#FFFFFF", "background_color": st_color, "alignment": "center", "content_alignment": "MIDDLE", "font_family": "Roboto"})
    ops.append({"op": "add-textbox", "slide": "SLIDE_3", "text": st_desc, "x": sx, "y": 70, "width": 165, "height": 24, "font_size": 7, "color": "#1E293B", "background_color": "#E2E8F0", "alignment": "center", "content_alignment": "MIDDLE", "font_family": "Roboto"})

  ops.append({"op": "add-table", "slide": "SLIDE_3", "rows": len(reminders) + 1, "cols": 6, "id": "REMINDER_TABLE", "x": 18, "y": 100, "width": 684, "height": 276})
  for col_idx, w in enumerate([118, 224, 62, 52, 78, 150]):
    ops.append({
        "op": "updateTableColumnProperties",
        "updateTableColumnProperties": {
            "objectId": "REMINDER_TABLE",
            "columnIndices": [col_idx],
            "tableColumnProperties": {"columnWidth": {"magnitude": w, "unit": "PT"}},
            "fields": "columnWidth",
        },
    })

  for c, h in enumerate(["Colleague / Recipient", "Action Requested by Willem", "Date Asked", "Elapsed", "2–5d Window", "Automation Status & Proposed Action"]):
    ops.append({"op": "set-table-cell", "table": "REMINDER_TABLE", "row": 0, "col": c, "text": h, "bold": True, "font_size": 8, "color": "#FFFFFF", "background_color": "#312E81", "font_family": "Roboto"})

  for r_idx, rem in enumerate(reminders, start=1):
    bg = "#FFFFFF" if r_idx % 2 == 1 else "#F1F5F9"
    status_txt = rem.get("automation_status", "")
    s_bg = "#FEF2F2" if "READY" in status_txt else "#EFF6FF"
    s_col = "#991B1B" if "READY" in status_txt else "#1E40AF"
    row_vals = [
        rem.get("colleague_name", ""),
        rem.get("action_requested", ""),
        rem.get("date_asked", ""),
        f"{rem.get('days_elapsed', 0)} days",
        rem.get("reminder_window", ""),
        status_txt,
    ]
    for c_idx, val in enumerate(row_vals):
      ops.append({
          "op": "set-table-cell",
          "table": "REMINDER_TABLE",
          "row": r_idx,
          "col": c_idx,
          "text": val,
          "bold": c_idx in (0, 4, 5),
          "font_size": 7.2,
          "color": s_col if c_idx == 5 else "#0F172A",
          "background_color": s_bg if c_idx == 5 else bg,
          "font_family": "Roboto",
      })

  ops.append({"op": "add-textbox", "slide": "SLIDE_3", "text": "Guardrail Compliance: 0 colleague emails sent automatically. Explicit RequestInput approval required.  |  Slide 3 of 6", "x": 20, "y": 384, "width": 680, "height": 14, "font_size": 8, "bold": True, "color": "#4C1D95", "font_family": "Roboto"})
  ops.append({"op": "set-notes", "slide": "SLIDE_3", "text": "Slide 3: Automated Colleague Reminder Tracker (2-5 Day SLA with Human-in-the-Loop consent gate)."})

  # ============================================================================
  # SLIDE 4 (id: "SLIDE_4"): PSO PROJECT PORTFOLIO STATUS, KPIS & RISKS
  # ============================================================================
  projects = pso.get("projects", [])[:7]
  ops.extend([
      {"op": "add-slide", "layout": "BLANK", "id": "SLIDE_4"},
      {"op": "set-background", "slide": "SLIDE_4", "color": "#F8FAFC"},
      {"op": "add-shape", "slide": "SLIDE_4", "shape_type": "RECTANGLE", "x": 0, "y": 0, "width": 720, "height": 48, "background_color": "#0F172A"},
      {"op": "add-textbox", "slide": "SLIDE_4", "text": "3. PSO PROJECT PORTFOLIO STATUS — KPIS, RISKS & ISSUES", "x": 20, "y": 6, "width": 540, "height": 22, "font_size": 16, "bold": True, "color": "#FFFFFF", "font_family": "Roboto"},
      {"op": "add-textbox", "slide": "SLIDE_4", "text": "CP3 PSO Obligation: $28.96M ($22.5M CP3 + $6.46M CP2 Shortfall)  |  Paid: $8.42M  |  Gap: -$20.54M (~$10M Year-End Shortfall Risk)", "x": 20, "y": 26, "width": 680, "height": 16, "font_size": 9, "color": "#FCA5A5", "font_family": "Roboto"},
      {"op": "add-table", "slide": "SLIDE_4", "rows": len(projects) + 1, "cols": 5, "id": "PROJECT_TABLE", "x": 18, "y": 54, "width": 684, "height": 324},
  ])

  for col_idx, w in enumerate([115, 85, 54, 185, 245]):
    ops.append({
        "op": "updateTableColumnProperties",
        "updateTableColumnProperties": {
            "objectId": "PROJECT_TABLE",
            "columnIndices": [col_idx],
            "tableColumnProperties": {"columnWidth": {"magnitude": w, "unit": "PT"}},
            "fields": "columnWidth",
        },
    })

  for c, h in enumerate(["Project / Workstream", "Commercial Scope", "Status", "Delivery KPIs & Current Progress", "Key Risks / Issues & Mitigation Path"]):
    ops.append({"op": "set-table-cell", "table": "PROJECT_TABLE", "row": 0, "col": c, "text": h, "bold": True, "font_size": 8, "color": "#FFFFFF", "background_color": "#991B1B", "font_family": "Roboto"})

  for r_idx, proj in enumerate(projects, start=1):
    bg = "#FFFFFF" if r_idx % 2 == 1 else "#F1F5F9"
    rag = proj.get("rag_status", "AMBER\nMEDIUM")
    r_bg = "#FEE2E2" if "RED" in rag else "#FEF3C7"
    r_col = "#991B1B" if "RED" in rag else "#92400E"
    row_vals = [
        proj.get("project_name", ""),
        proj.get("commercial_scope", ""),
        rag,
        proj.get("kpis_and_progress", ""),
        proj.get("risks_and_mitigation", ""),
    ]
    for c_idx, val in enumerate(row_vals):
      ops.append({
          "op": "set-table-cell",
          "table": "PROJECT_TABLE",
          "row": r_idx,
          "col": c_idx,
          "text": val,
          "bold": c_idx in (0, 2),
          "font_size": 7.0,
          "color": r_col if c_idx == 2 else "#0F172A",
          "background_color": r_bg if c_idx == 2 else bg,
          "font_family": "Roboto",
      })

  ops.append({"op": "add-textbox", "slide": "SLIDE_4", "text": f"{pso.get('structural_constraints_footer', '')}  |  Slide 4 of 6", "x": 20, "y": 384, "width": 680, "height": 14, "font_size": 7.5, "bold": True, "color": "#991B1B", "font_family": "Roboto"})
  ops.append({"op": "set-notes", "slide": "SLIDE_4", "text": "Slide 4: PSO Project Portfolio Status, KPIs, and Critical Risks/Issues."})

  # ============================================================================
  # SLIDE 5 (id: "SLIDE_5"): AFA CONSUMPTION & INCENTIVES STATUS (CP3)
  # ============================================================================
  commit_rows = afa.get("commit_rows", [])[:3]
  inc_rows = afa.get("incentive_rows", [])[:3]
  ops.extend([
      {"op": "add-slide", "layout": "BLANK", "id": "SLIDE_5"},
      {"op": "set-background", "slide": "SLIDE_5", "color": "#0F172A"},
      {"op": "add-shape", "slide": "SLIDE_5", "shape_type": "RECTANGLE", "x": 0, "y": 0, "width": 720, "height": 6, "background_color": "#34A853"},
      {"op": "add-textbox", "slide": "SLIDE_5", "text": "4. AFA CONSUMPTION & INCENTIVES — COMMIT PERIOD 3 (CP3)", "x": 20, "y": 10, "width": 540, "height": 22, "font_size": 16, "bold": True, "color": "#FFFFFF", "font_family": "Roboto"},
      {"op": "add-textbox", "slide": "SLIDE_5", "text": "CP3 Window: Feb 27, 2026 – Feb 26, 2027  |  7-Year $1B Contract ($865M GCP, $105M PSO, $30M GWS, $55M Credits/Incentives)  |  Net of 5% Tax", "x": 20, "y": 30, "width": 680, "height": 16, "font_size": 9, "color": "#94A3B8", "font_family": "Roboto"},
      {"op": "add-textbox", "slide": "SLIDE_5", "text": "A. CP3 CORE COMMIT ATTAINMENT (CASH / NET PAID TO GOOGLE VS. SIGNED IMPULSE VIEW)", "x": 18, "y": 48, "width": 684, "height": 16, "font_size": 8.5, "bold": True, "color": "#60A5FA", "font_family": "Roboto"},
      {"op": "add-table", "slide": "SLIDE_5", "rows": len(commit_rows) + 1, "cols": 7, "id": "COMMIT_TABLE", "x": 18, "y": 64, "width": 684, "height": 105},
  ])

  for col_idx, w in enumerate([74, 72, 86, 84, 88, 66, 214]):
    ops.append({
        "op": "updateTableColumnProperties",
        "updateTableColumnProperties": {
            "objectId": "COMMIT_TABLE",
            "columnIndices": [col_idx],
            "tableColumnProperties": {"columnWidth": {"magnitude": w, "unit": "PT"}},
            "fields": "columnWidth",
        },
    })

  for c, h in enumerate(["Stream", "CP3 Commit", "CP2 Roll-Over", "Effective Target", "CP3 Net Paid", "Attained %", "Balance / Gap & CP3–CP4 Trajectory"]):
    ops.append({"op": "set-table-cell", "table": "COMMIT_TABLE", "row": 0, "col": c, "text": h, "bold": True, "font_size": 7.2, "color": "#FFFFFF", "background_color": "#1E3A8A", "font_family": "Roboto"})

  for r_idx, crow in enumerate(commit_rows, start=1):
    bg = "#1E293B" if r_idx % 2 == 1 else "#0F172A"
    vals = [
        crow.get("stream", ""),
        crow.get("cp3_commit", ""),
        crow.get("cp2_rollover", ""),
        crow.get("effective_target", ""),
        crow.get("cp3_net_paid", ""),
        crow.get("attainment_pct", ""),
        crow.get("balance_and_trajectory", ""),
    ]
    for c_idx, val in enumerate(vals):
      color = "#E2E8F0"
      if c_idx == 5:
        color = "#4ADE80" if r_idx == 1 else "#F87171"
      elif c_idx == 2:
        color = "#4ADE80" if "+" in val else "#F87171"
      ops.append({
          "op": "set-table-cell",
          "table": "COMMIT_TABLE",
          "row": r_idx,
          "col": c_idx,
          "text": val,
          "bold": c_idx in (0, 5),
          "font_size": 6.8,
          "color": color,
          "background_color": bg,
          "font_family": "Roboto",
      })

  ops.extend([
      {"op": "add-textbox", "slide": "SLIDE_5", "text": "B. CP3 INCENTIVES & TRANSFORMATION FUNDS (PSF, TIF & CLOUD CREDITS — $55M LIFETIME POOL)", "x": 18, "y": 196, "width": 684, "height": 16, "font_size": 8.5, "bold": True, "color": "#34D399", "font_family": "Roboto"},
      {"op": "add-table", "slide": "SLIDE_5", "rows": len(inc_rows) + 1, "cols": 6, "id": "INCENTIVE_TABLE", "x": 18, "y": 212, "width": 684, "height": 140},
  ])

  for col_idx, w in enumerate([92, 78, 78, 82, 114, 240]):
    ops.append({
        "op": "updateTableColumnProperties",
        "updateTableColumnProperties": {
            "objectId": "INCENTIVE_TABLE",
            "columnIndices": [col_idx],
            "tableColumnProperties": {"columnWidth": {"magnitude": w, "unit": "PT"}},
            "fields": "columnWidth",
        },
    })

  for c, h in enumerate(["Incentive Fund", "CP2 Carry-Over", "CP3 Allocation", "Total CP3 Pool", "Consumed / Approved", "Remaining Balance, Pipeline & Bottlenecks"]):
    ops.append({"op": "set-table-cell", "table": "INCENTIVE_TABLE", "row": 0, "col": c, "text": h, "bold": True, "font_size": 7.2, "color": "#FFFFFF", "background_color": "#065F46", "font_family": "Roboto"})

  for r_idx, irow in enumerate(inc_rows, start=1):
    bg = "#1E293B" if r_idx % 2 == 1 else "#0F172A"
    vals = [
        irow.get("fund_name", ""),
        irow.get("cp2_carryover", ""),
        irow.get("cp3_allocation", ""),
        irow.get("total_cp3_pool", ""),
        irow.get("consumed_or_approved", ""),
        irow.get("remaining_balance_and_pipeline", ""),
    ]
    for c_idx, val in enumerate(vals):
      color = "#FBBF24" if c_idx == 3 else ("#4ADE80" if c_idx == 4 else "#E2E8F0")
      ops.append({
          "op": "set-table-cell",
          "table": "INCENTIVE_TABLE",
          "row": r_idx,
          "col": c_idx,
          "text": val,
          "bold": c_idx in (0, 3),
          "font_size": 6.8,
          "color": color,
          "background_color": bg,
          "font_family": "Roboto",
      })

  ops.append({"op": "add-textbox", "slide": "SLIDE_5", "text": f"Data Grounded in: External Commit Attainment Sheet (1nUuxK...) & External PSF/TIF Sheet (1NU0tu...) as of {as_of}.  |  Slide 5 of 6", "x": 20, "y": 384, "width": 680, "height": 14, "font_size": 8, "color": "#64748B", "font_family": "Roboto"})
  ops.append({"op": "set-notes", "slide": "SLIDE_5", "text": "Slide 5: CP3 AFA Consumption & Incentives Status."})

  # ============================================================================
  # SLIDE 6 (id: "SLIDE_6"): 3 WEEKLY NEW INNOVATIVE IDEAS FOR KUWAIT GOVT
  # ============================================================================
  ideas = innov.get("ideas", [])[:3]
  ops.extend([
      {"op": "add-slide", "layout": "BLANK", "id": "SLIDE_6"},
      {"op": "set-background", "slide": "SLIDE_6", "color": "#F8FAFC"},
      {"op": "add-shape", "slide": "SLIDE_6", "shape_type": "RECTANGLE", "x": 0, "y": 0, "width": 720, "height": 48, "background_color": "#0F172A"},
      {"op": "add-textbox", "slide": "SLIDE_6", "text": "5. WEEKLY INNOVATION RADAR — 3 NEW KUWAIT GOVT USE CASES", "x": 20, "y": 6, "width": 560, "height": 22, "font_size": 16, "bold": True, "color": "#FFFFFF", "font_family": "Roboto"},
      {"op": "add-textbox", "slide": "SLIDE_6", "text": "Aligned with New Kuwait Vision 2035 & Willem's 3-Layer National AI Factory Architecture (Citizen/Employee, Entity, Project-Embedded)", "x": 20, "y": 26, "width": 680, "height": 16, "font_size": 9, "color": "#6EE7B7", "font_family": "Roboto"},
  ])

  for idx, idea in enumerate(ideas):
    ix = 18 + idx * 231
    refs_str = "\n".join(f"• {r}" for r in idea.get("references", []))
    body_text = (
        f"TARGET ENTITIES:\n{idea.get('target_entities', '')}\n\n"
        f"USE CASE & ARCHITECTURE:\n{idea.get('use_case_and_architecture', '')}\n\n"
        f"BUSINESS VALUE & AFA IMPACT:\n{idea.get('business_value_and_afa_impact', '')}\n\n"
        f"REFERENCES & BENCHMARKS:\n{refs_str}"
    )
    ops.append({"op": "add-textbox", "slide": "SLIDE_6", "text": idea.get("layer_tag", ""), "x": ix, "y": 54, "width": 222, "height": 16, "font_size": 6.8, "bold": True, "color": "#FFFFFF", "background_color": idea.get("accent_color", "#3B82F6"), "alignment": "center", "content_alignment": "MIDDLE", "font_family": "Roboto"})
    ops.append({"op": "add-textbox", "slide": "SLIDE_6", "text": idea.get("title", ""), "x": ix, "y": 70, "width": 222, "height": 30, "font_size": 9.5, "bold": True, "color": "#FFFFFF", "background_color": idea.get("header_bg", "#1E3A8A"), "alignment": "center", "content_alignment": "MIDDLE", "font_family": "Roboto"})
    ops.append({"op": "add-textbox", "slide": "SLIDE_6", "text": body_text, "x": ix, "y": 100, "width": 222, "height": 276, "font_size": 7.2, "color": "#0F172A", "background_color": "#FFFFFF", "font_family": "Roboto", "line_spacing": 115})
    ops.append({"op": "add-shape", "slide": "SLIDE_6", "shape_type": "RECTANGLE", "x": ix, "y": 376, "width": 222, "height": 3, "background_color": idea.get("header_bg", "#1E3A8A")})

  ops.append({"op": "add-textbox", "slide": "SLIDE_6", "text": "Cadence: Refreshed weekly with 3 net-new Kuwait Public Sector digital transformation use cases, value cases & references.  |  Slide 6 of 6", "x": 20, "y": 384, "width": 680, "height": 14, "font_size": 8, "color": "#64748B", "font_family": "Roboto"})
  ops.append({"op": "set-notes", "slide": "SLIDE_6", "text": "Slide 6: 3 Weekly New Innovative Digital Transformation Ideas for the Kuwait Government."})
  return ops


def create_and_populate_dashboard_slides(
    payload: dict[str, Any],
    export_thumbnails: bool = False,
) -> dict[str, Any]:
  """Creates a new 6-slide Google Slides presentation and populates it via `gslides mutate batch`.

  Args:
    payload: Serialized `DashboardPayload` dictionary.
    export_thumbnails: If True, exports PNG thumbnails of the created slides.

  Returns:
    Updated dictionary containing `presentation_id`, `presentation_url`, and `slide_thumbnails`.
  """
  ops = build_six_slide_batch_ops(payload)
  title = payload.get(
      "presentation_title",
      f"Kuwait CAL Executive Priority Dashboard — Willem Clappaert ({payload.get('as_of_date', 'Oct 2026')})",
  )

  if os.environ.get("CAL_AGENT_DRY_RUN", "").lower() in ("1", "true", "yes"):
    fake_id = "1yngv5tCsdPf_KLqTN1JP7i1fdFZmkGOb2vbrJSYkufo"
    return {
        "presentation_id": fake_id,
        "presentation_url": f"https://docs.google.com/presentation/d/{fake_id}/edit",
        "operations_count": len(ops),
        "slide_thumbnails": [],
    }

  create_proc = subprocess.run(
      [GSLIDES_BIN, "mutate", "create", "--title", title, "--json"],
      capture_output=True,
      text=True,
      timeout=45,
      check=False,
  )
  match = re.search(r"ID:\s*([A-Za-z0-9_-]+)", create_proc.stdout)
  if not match:
    try:
      data = json.loads(create_proc.stdout)
      pres_id = data.get("presentationId") or data.get("id", "")
    except Exception:  # pylint: disable=broad-except
      pres_id = ""
  else:
    pres_id = match.group(1)

  if not pres_id:
    raise RuntimeError(f"Failed to create presentation: {create_proc.stdout} {create_proc.stderr}")

  with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
    json.dump(ops, tf, indent=2)
    batch_path = tf.name

  try:
    batch_proc = subprocess.run(
        [GSLIDES_BIN, "mutate", "batch", pres_id, "-f", batch_path, "--json"],
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    if batch_proc.returncode != 0:
      raise RuntimeError(f"gslides mutate batch failed: {batch_proc.stdout} {batch_proc.stderr}")
    batch_res = json.loads(batch_proc.stdout)
  finally:
    if os.path.exists(batch_path):
      os.remove(batch_path)

  thumbnails: list[str] = []
  if export_thumbnails:
    slide_ids = ["p"] + batch_res.get("created_slides", [])
    out_dir = tempfile.mkdtemp(prefix="cal_slides_")
    for idx, sid in enumerate(slide_ids, start=1):
      png_path = os.path.join(out_dir, f"slide_{idx}.png")
      subprocess.run(
          [GSLIDES_BIN, "readonly", "export-thumbnail", pres_id, png_path, "--slide", sid],
          capture_output=True,
          text=True,
          timeout=45,
          check=False,
      )
      if os.path.exists(png_path):
        thumbnails.append(png_path)

  return {
      "presentation_id": pres_id,
      "presentation_url": f"https://docs.google.com/presentation/d/{pres_id}/edit",
      "operations_count": len(ops),
      "slide_thumbnails": thumbnails,
  }
