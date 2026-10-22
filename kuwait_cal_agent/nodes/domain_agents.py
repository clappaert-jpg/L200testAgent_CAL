"""Stage 2: Domain-specific ADK `LlmAgent` nodes with strict Pydantic `output_schema`.

Each `LlmAgent` is configured with:
- `mode="single_turn"` and `include_contents="none"` for clean mid-graph execution
- `output_schema=<BaseModel>` so outputs parked in `JoinNode` are JSON-serializable
- A deterministic `fallback_handler` grounded in Willem's verified Kuwait CAL data
"""

from __future__ import annotations

from typing import Any

from .._adk_compat import Context, LlmAgent
from ..schemas import (
    AfaConsumptionOutput,
    ColleagueReminderItem,
    CommitStreamRow,
    HeadlineKpiCard,
    IncentiveFundRow,
    InnovationIdea,
    InnovationRadarOutput,
    PsoPortfolioOutput,
    PsoProjectRiskItem,
    TodoAndRemindersOutput,
    TodoItem,
)


def _default_todo_and_reminders(ctx: Context, node_input: Any) -> TodoAndRemindersOutput:
  del ctx, node_input
  todos = [
      TodoItem(
          rank=1,
          horizon="THIS WEEK",
          due_date="Oct 22, 2026",
          action="Unblock SOW3 Migration Factory 2.0 Discovery & CE/OCE Plan: Lead GCC/AT syncs; lock PSE list & CSC (1,200 VMs).",
          stakeholders="Lama Jammal, Pawel, Joana",
          source="Calendar / Standup",
      ),
      TodoItem(
          rank=2,
          horizon="THIS WEEK",
          due_date="Oct 23, 2026",
          action="Close ServiceNow ($60M) MP Cap Concession: Clear Finance approval (@odehh) in Cloud Connect (#6910316231362871297).",
          stakeholders="Abdulla Odeh, Marcello Prati",
          source="Gmail",
      ),
      TodoItem(
          rank=3,
          horizon="THIS WEEK",
          due_date="Oct 23, 2026",
          action="Update KDIPA Q3 Site Visit Tracker: Populate Tech Transfer, R&D & Skilling columns ahead of Nov 2 inspection.",
          stakeholders="Nicola Ó Corrbuí, H. Almutawa",
          source="Gmail",
      ),
      TodoItem(
          rank=4,
          horizon="NEXT WEEK",
          due_date="Oct 25, 2026",
          action="Align FY27 Public Sector Event (Nov 25–26 EBC) & Mannai Prep: Lock 50-person agenda, partner vetting & CAIT prep.",
          stakeholders="Ali Al Adhami, Ahmad Amr",
          source="Calendar",
      ),
      TodoItem(
          rank=5,
          horizon="NEXT WEEK",
          due_date="Oct 26, 2026",
          action="Deliver Post-Migration Risks Brief to CAIT: Consolidate TAM (@hamoudha) risks on security, CCoE Day 2 & MoJ KIN.",
          stakeholders="Farah Hamoudha, M. Alotaibi",
          source="Gmail / Minutes",
      ),
      TodoItem(
          rank=6,
          horizon="NEXT WEEK",
          due_date="Oct 26, 2026",
          action="Lead MoE Scope & License Expansion Session: Align 45k renewal + 21k new seats + 3.5k GE librarians ($571k) & Oracle.",
          stakeholders="Ali Al Adhami, Lama Jammal",
          source="Calendar",
      ),
      TodoItem(
          rank=7,
          horizon="NEXT WEEK",
          due_date="Oct 27, 2026",
          action="Finalize CAIT Digital Resilience ($3.67M) & Migration Factory RACI: Strip wartime DR; merge 300-VM DR, EA & CCoE.",
          stakeholders="Ali Hasan (CAIT), Lama Jammal",
          source="Gmail / Minutes",
      ),
      TodoItem(
          rank=8,
          horizon="NEXT WEEK",
          due_date="Oct 27, 2026",
          action="Conduct AFA Handover Part I & Quarterly In-Country Tax Check: Onboard Hussein; audit PSO <180-day tax threshold.",
          stakeholders="Hussein Almutawa, Subcomm",
          source="Calendar",
      ),
      TodoItem(
          rank=9,
          horizon="NEXT WEEK",
          due_date="Oct 28, 2026",
          action="Resolve CAIT Skilling Ph3 Commercials & 5-Hr ILT Cap: Align Thinksmart ATP cohort model to fix 37.5% TIF waste.",
          stakeholders="Ailbhe Kelly, Lee Ziglar, Najat",
          source="Gmail / Calendar",
      ),
      TodoItem(
          rank=10,
          horizon="NEXT WEEK",
          due_date="Oct 28, 2026",
          action="Drive Nationwide AI Factory Scoping & KU Student Journey Pitch: Pick 3 CAIT agent use cases; review KU 85k-seat deck.",
          stakeholders="Ali Asaad, Sabri Traifi, Ehsan",
          source="Meet Notes",
      ),
  ]

  reminders = [
      ColleagueReminderItem(
          colleague_name="Abdulla Odeh (odehh@)\n+ Finance (marcelloprati@,\nmichaelcollins@)",
          colleague_email="odehh@google.com",
          is_external=False,
          action_requested="Approve KW Marketplace Cap compression (#6910316231362871297) in Cloud Connect (still shows pending for Abdulla on Oct 22 despite Oct 21 reply).",
          date_asked="Oct 15\n(Pinged Oct 22)",
          days_elapsed=7,
          reminder_window="Oct 23–25\n(2–3 days)",
          in_2_to_5_day_window=True,
          automation_status="READY FOR APPROVAL: Send kind check confirming system click in Cloud Connect.",
          proposed_subject="Re: Approval Needed: KW Marketplace Cap Compression (#6910316231362871297)",
          proposed_body="Hi Abdulla, thanks for your note yesterday! Could you please double-check Cloud Connect (#6910316231362871297) and confirm completion, as it still shows pending on our side? Thanks, Willem",
      ),
      ColleagueReminderItem(
          colleague_name="Ehsan Rafizadeh\n(ehsanr@google.com)",
          colleague_email="ehsanr@google.com",
          is_external=False,
          action_requested="Update KU Student Journey pitch deck (10x metrics, 6-wk sprint, costs, Agentic slide) & forward to Willem for review ahead of KU leadership meeting.",
          date_asked="Oct 18\n(Meet Notes)",
          days_elapsed=4,
          reminder_window="Oct 20–23\n(IN WINDOW)",
          in_2_to_5_day_window=True,
          automation_status="READY FOR APPROVAL: Send kind Day-4 reminder & ask for completion ETA.",
          proposed_subject="Kind follow-up: Updated KU Student Journey & AI CoE Pitch Deck",
          proposed_body="Hi Ehsan, following up on our Sunday session on the KU Student Journey presentation—could you please share the updated pitch deck over the next 2–3 days and confirm once ready for review? Thanks, Willem",
      ),
      ColleagueReminderItem(
          colleague_name="Lama Jammal (ljammal@)\n& Ali Al Adhami\n(alialadhami@)",
          colleague_email="ljammal@google.com",
          is_external=False,
          action_requested="Finalize revised Digital Resilience SOW scope (removing wartime free DR items) & lock early-next-week RACI session with Ali Hasan / Alotaibi.",
          date_asked="Oct 19–20\n(Email/Min)",
          days_elapsed=3,
          reminder_window="Oct 22–24\n(IN WINDOW)",
          in_2_to_5_day_window=True,
          automation_status="READY FOR APPROVAL: Send kind Day-3 check on revised SOW & calendar invite.",
          proposed_subject="Re: [CAIT] Digital Resilience Program - RACI POV & Revised Scope",
          proposed_body="Hi Lama, Ali, could you please confirm when the revised Digital Resilience SOW scope will be ready and confirm once the early-next-week session with Ali Hasan / Alotaibi is locked in? Best, Willem",
      ),
      ColleagueReminderItem(
          colleague_name="Farah Hamoudha\n(hamoudha@google.com)\nTAM",
          colleague_email="hamoudha@google.com",
          is_external=False,
          action_requested="Draft succinct email summarizing post-migration risks (security, maintenance, PSE skills gap, CCoE Day 2 support) & resolution path for CAIT.",
          date_asked="Oct 21\n19:34 UTC",
          days_elapsed=1,
          reminder_window="Oct 23–26\n(2–5 days)",
          in_2_to_5_day_window=False,
          automation_status="MONITORING: Auto-stage reminder draft on Fri Oct 23 if no reply received.",
          proposed_subject="Re: Risks — Post-Migration Summary for CAIT",
          proposed_body="Hi Farah, kind reminder on the succinct post-migration risks summary email for CAIT—could you please share it within the next 2–3 days and confirm completion? Thanks, Willem",
      ),
      ColleagueReminderItem(
          colleague_name="Charmaine Mascarenhas\n(cmascarenhas@deloitte)\n[EXTERNAL]",
          colleague_email="cmascarenhas@deloitte.com",
          is_external=True,
          action_requested="Confirm parallel execution of Kuwait work permit/degree steps & provide Civil ID number required for housing declaration.",
          date_asked="Oct 21\n13:39 UTC",
          days_elapsed=1,
          reminder_window="Oct 23–26\n(2–5 days)",
          in_2_to_5_day_window=False,
          automation_status="MONITORING (EXTERNAL): Stage draft on Oct 23; requires explicit external consent.",
          proposed_subject="Re: Google - Kuwait - Willem Clappaert - Work permit",
          proposed_body="Hi Charmaine, kind follow-up on my note—could you please confirm if any steps can run in parallel and share the Civil ID number needed for the housing declaration? Best regards, Willem",
      ),
      ColleagueReminderItem(
          colleague_name="Hussein Almutawa\n(halmutawa@google.com)\nAFA Alliance Mgr",
          colleague_email="halmutawa@google.com",
          is_external=False,
          action_requested="Review CAL–Alliance Mngt Tasks Split doc, bookmark CAL links, and update KDIPA Q3 Site Visit Tracker ahead of Nov 2 judicial inspection.",
          date_asked="Oct 22\n09:57 UTC",
          days_elapsed=0,
          reminder_window="Oct 24–27\n(2–5 days)",
          in_2_to_5_day_window=False,
          automation_status="SCHEDULED: Verify KDIPA sheet edits on Oct 24; prompt reminder if incomplete.",
          proposed_subject="Kind follow-up: KDIPA Q3 Site Visit Tracker & Alliance Tasks Split",
          proposed_body="Hi Hussein, hope onboarding is going smoothly! Could you please confirm once you've updated the KDIPA Q3 Site Visit Tracker and reviewed the CAL-Alliance Tasks Split doc? Thanks, Willem",
      ),
  ]
  return TodoAndRemindersOutput(todos=todos, reminders=reminders)


def _default_pso_portfolio(ctx: Context, node_input: Any) -> PsoPortfolioOutput:
  del ctx, node_input
  projects = [
      PsoProjectRiskItem(
          project_name="ServiceNow Deal &\nPSO Staff Aug\n(@clappaert / CE)",
          commercial_scope="$60M MP Deal +\nPSO Staff Aug +\n5 GCP Use Cases",
          rag_status="RED\nCRITICAL",
          kpis_and_progress="Target signature Dec 2026; 5 SN–GCP AI/Data integration use cases in scoping with Deloitte & CEs.",
          risks_and_mitigation="BLOCKER: 15% AFA Marketplace Cap ($58M CP1–5) blocks deal; high risk of losing $60M to Microsoft ($2.7B KW commit). Mitigation: Close MP Cap concession (+$12M from CP7).",
      ),
      PsoProjectRiskItem(
          project_name="Migration Factory\n(SOW2 -> SOW3)\n(@ljammal / Pawel)",
          commercial_scope="$10.0M PSO (SOW3)\n$1.16M Paid (SOW2)\n1,200 VMs at CSC",
          rag_status="RED\nHIGH",
          kpis_and_progress="SOW2 ended Jun 18; SOW3 intake + container/Oracle archetypes scoped; CSC (1,200 VMs) & KU prioritized.",
          risks_and_mitigation="ISSUE: Severe Day 2 support/skills gap at CCoE & PSEs post-SOW2. KIN interconnect stability dispute (CAIT/Impulse claim non-prod) -> MoJ threatening to revert SAP to on-prem!",
      ),
      PsoProjectRiskItem(
          project_name="Digital Resilience\nProgram (CAIT)\n(@ljammal / Ali)",
          commercial_scope="$3.67M PSO\n(Sub-committee\nApproved)",
          rag_status="AMBER\nMED-HI",
          kpis_and_progress="Parallel partner budget unlocked; RACI POV shared with CAIT (Ali Hasan); covers 300 VMs geo-DR + EA/CCoE.",
          risks_and_mitigation="RISK: Alotaibi refused to pay for DR services given 'for free' during Mar–Apr conflict. Mitigation: Strip wartime DR; re-anchor SOW on 300-VM DR, Cohesity/Veeam & CCoE.",
      ),
      PsoProjectRiskItem(
          project_name="National Skilling\nPhase II & III\n(@clappaert / Kelly)",
          commercial_scope="TIF Funded\n($2.44M Pool)\n1,113 Reg / 751 Att",
          rag_status="AMBER\nHIGH",
          kpis_and_progress="Ph2 71% complete (37 event days, CSAT 4.6/5; CAIT 75, MOJ 74, MEW 41, KU 31). Ph3 commercial model in design.",
          risks_and_mitigation="ISSUE: 33% drop-off rate, low cert exam pass rate, & CAIT's strict 5-hr daily limit causes 37.5% waste of 8-hr ILT TIF units. Mitigation: Thinksmart cohort stacking (Oct 28).",
      ),
      PsoProjectRiskItem(
          project_name="GovShield / Cyber\n(PSO & Mandiant)\n(@stribioli / Raad)",
          commercial_scope="SecOps SOC +\nMandiant Threat\nDefense",
          rag_status="AMBER\nMEDIUM",
          kpis_and_progress="22 PSEs live on SecOps (11 WIP; +10 by Jan '27); 8 PSEs assessed by Mandiant (8 WIP); GWS license gap fixed.",
          risks_and_mitigation="RISK: 3-month schedule delay across tracks from Mar–Apr regional conflict; NCSC demanding radical approach overhaul on Mandiant workstreams & escalating PSE complaints.",
      ),
      PsoProjectRiskItem(
          project_name="MoE Gemini for Edu\n& Oracle Migration\n(@alialadhami)",
          commercial_scope="61k Seats Total +\n3.5k GE ($571k) +\n$398k Paid PSO",
          rag_status="AMBER\nMEDIUM",
          kpis_and_progress="21,209 teachers trained across 177 schools (287 sessions); 1st MENA GEG launched; Nov 25 innovation event.",
          risks_and_mitigation="RISK: 14,000 MoE licenses unactivated (pending ministry names); Anaam requires utilization report before approving 21k expansion; SIS/TIS paused for Oracle DB scope.",
      ),
      PsoProjectRiskItem(
          project_name="Apigee Ph2, Data\nPlatform & KOC\n(@asbahni / @ljammal)",
          commercial_scope="$1.67M Data Plat\n$6.48M KOC Paid\n$129k Apigee Paid",
          rag_status="AMBER\nMEDIUM",
          kpis_and_progress="Apigee Semi-Federated upgraded & demoed; Federated w/ PACI & MOJ. Data Platform Ph1 sponsored by KU.",
          risks_and_mitigation="ISSUE: PACI Landing Zone overdue (blocks Apigee Federated track); $50k Apigee Ph1 referral fees unpaid 4 qtrs; PAAET dropped from Data Platform due to duplicate use case.",
      ),
  ]
  return PsoPortfolioOutput(projects=projects)


def _default_afa_consumption(ctx: Context, node_input: Any) -> AfaConsumptionOutput:
  del ctx, node_input
  headline_kpis = [
      HeadlineKpiCard(
          title="CP3 GCP ATTAINMENT",
          stat="87.9%",
          stat_color="#4ADE80",
          badge="ON TRACK",
          badge_bg="#14532D",
          subtitle="$59.09M / $67.20M Net\nPaid: $32.50M | Roll: +$26.59M\nGap: -$8.11M (Signed: $86.2M)",
      ),
      HeadlineKpiCard(
          title="CP3 PSO COMMIT",
          stat="29.1%",
          stat_color="#F87171",
          badge="HIGH RISK",
          badge_bg="#7F1D1D",
          subtitle="$8.42M / $28.96M Target\n(Incl. -$6.46M CP2 Shortfall)\nGap: -$20.54M (~$10M Risk)",
      ),
      HeadlineKpiCard(
          title="CP3 PSF & TIF POOL",
          stat="$6.56M",
          stat_color="#FBBF24",
          badge="ACTION REQ",
          badge_bg="#78350F",
          subtitle="PSF Avail: $4.12M ($1.88M used)\nTIF Avail: $2.44M ($0 billed)\nCredits Avail: $1.40M",
      ),
      HeadlineKpiCard(
          title="PRIORITY TO-DOs",
          stat="10",
          stat_color="#60A5FA",
          badge="3 THIS WK",
          badge_bg="#1E3A8A",
          subtitle="3 This Week (Oct 22–23)\n7 Next Week (Oct 25–28)\nSOW3, $60M SN, KDIPA, MoE",
      ),
      HeadlineKpiCard(
          title="COLLEAGUE PINGS",
          stat="6",
          stat_color="#C084FC",
          badge="0 SENT (GATED)",
          badge_bg="#4C1D95",
          subtitle="2–5d Automated Tracker\n3 Ready Now | 3 Monitoring\nRequires Explicit Approval",
      ),
  ]
  commit_rows = [
      CommitStreamRow(
          stream="GCP (Hard)",
          cp3_commit="$67,200,000",
          cp2_rollover="+$26,586,939 (Excess)",
          effective_target="$40,613,061 Net Req",
          cp3_net_paid="$32,501,327 ($34.2M Inv)",
          attainment_pct="87.9% ($59.1M)",
          balance_and_trajectory="-$8,111,734 Cash Gap | +$45.55M Signed Excess ($86.17M).\nCP4 jumps to $136.15M ($183.23M w/ MP Cap pull-forward).",
      ),
      CommitStreamRow(
          stream="PSO (Buy)",
          cp3_commit="$22,500,000",
          cp2_rollover="-$6,459,251 (Shortfall)",
          effective_target="$28,959,251 Combined",
          cp3_net_paid="$8,423,913 ($8.87M Inv)",
          attainment_pct="29.1% (37.4%)",
          balance_and_trajectory="-$20,535,338 Gap (~$10M Yr-End Risk). Paid: KOC $6.48M,\nSOW2 $1.16M, MoE $398K, KFF $258K, Apigee $129K.",
      ),
      CommitStreamRow(
          stream="Workspace",
          cp3_commit="$4,300,000",
          cp2_rollover="-$415,045 (Shortfall)",
          effective_target="$4,715,045 Combined",
          cp3_net_paid="$0 ($15.3K Signed)",
          attainment_pct="0.0%",
          balance_and_trajectory="-$4,715,045 Gap | Relies on closing MoE 45k renewal +\n21k expansion + 3.5k Gemini Enterprise librarians ($571k).",
      ),
  ]
  incentive_rows = [
      IncentiveFundRow(
          fund_name="PSF (Partner\nService Fund)",
          cp2_carryover="$2,800,000",
          cp3_allocation="$3,200,000",
          total_cp3_pool="$6,000,000",
          consumed_or_approved="$1,877,394 Total\n($221.6K Done/Active +\n$1.66M in 8 SOWs)",
          remaining_balance_and_pipeline="$4,122,606 Avail | +$1.64M WIP (13 deals -> $7.74M ARR:\nKIA GE $420K, KFAS $300K, MoFA $225K, MoE $175K).\nBottleneck: CAIT approval & Najat PoE SLA.",
      ),
      IncentiveFundRow(
          fund_name="TIF (Training &\nInnovation Fund)",
          cp2_carryover="$435,900\n(Extended)",
          cp3_allocation="$2,000,000",
          total_cp3_pool="$2,435,900",
          consumed_or_approved="$0 Billed to CP3\n($1.88M / 31.3% used\nin CP1–CP2)",
          remaining_balance_and_pipeline="$2,435,900 Avail (Expires Feb 26, 2027) | For National Skilling\nPh2/3, Apigee & ASL. Must fix 5-hr daily ILT cap (37.5% TIF\nunit waste) on Oct 28.",
      ),
      IncentiveFundRow(
          fund_name="Cloud Credits\n(GCP Adoption)",
          cp2_carryover="$401,956\n(Renewed)",
          cp3_allocation="$1,000,000\n(Oct 2026)",
          total_cp3_pool="$1,401,956",
          consumed_or_approved="$0 Drawn in CP3\n($2.60M / 86.6% used\nin CP1–CP2)",
          remaining_balance_and_pipeline="$1,401,956 Avail | $401.9K CP2 carry-over renewed for CAIT\nGemini Enterprise pilot — requires fast project sign-off to\nprevent re-expiration.",
      ),
  ]
  return AfaConsumptionOutput(
      headline_kpis=headline_kpis,
      commit_rows=commit_rows,
      incentive_rows=incentive_rows,
  )


def _default_innovation_radar(ctx: Context, node_input: Any) -> InnovationRadarOutput:
  del ctx, node_input
  ideas = [
      InnovationIdea(
          layer_tag="IDEA 1  |  LAYER 1: NATIONWIDE CITIZEN & EMPLOYEE AGENT",
          title="'Sahel 2.0' Multimodal Citizen & CSC Civil Servant Agentic Hub",
          header_bg="#1E3A8A",
          accent_color="#3B82F6",
          target_entities="• CAIT, PACI (Mobile ID), Civil Service Commission (CSC — 1,200 VMs), All PSEs",
          use_case_and_architecture=(
              "• Citizen Facing (GCX): Embed bilingual (Arabic Khaleeji dialect + English) voice/chat agents into Kuwait's Sahel super-app authenticated via PACI Mobile ID to orchestrate multi-ministry life events over Apigee Ph2 APIs.\n"
              "• Civil Servant Facing (Gemini Enterprise): Deploy 'G App' across CSC's central employee directory for policy Q&A, Arabic memo drafting & HR workflows."
          ),
          business_value_and_afa_impact=(
              "• Cuts cross-ministry transaction times by 60–75% & deflects 50%+ of tier-1 walk-ins.\n"
              "• Anchors nationwide Gemini Enterprise seat adoption (closing GWS -$4.7M gap) & high-volume GCX/Apigee token consumption."
          ),
          references=[
              "New York State & Sullivan County Citizen AI Agents (Google Cloud Public Sector)",
              "Oct 21 CAIT Nationwide AI Factory Architecture (Mobile ID + CSC Integration)",
          ],
      ),
      InnovationIdea(
          layer_tag="IDEA 2  |  LAYER 2: ENTITY-SPECIFIC FISCAL & TENDER AI",
          title="MoF & CAPT Sovereign AI E-Invoicing & Tender Integrity Engine",
          header_bg="#065F46",
          accent_color="#10B981",
          target_entities="• Ministry of Finance (MoF), Central Agency for Public Tenders (CAPT), CITRA",
          use_case_and_architecture=(
              "• Built on the National Data Platform ($1.67M PSO) using BigQuery, Vertex AI & Document AI.\n"
              "• Ingests complex Arabic/English RFP bids at CAPT ($156k PSF approved) and upcoming National E-Invoicing streams at MoF.\n"
              "• Automatically detects duplicate scope across PSEs (preventing overlaps like PAAET), flags bid-rigging/pricing anomalies, and powers real-time ministerial spend dashboards."
          ),
          business_value_and_afa_impact=(
              "• Recovers 3–5% of public procurement spend by eliminating duplicate IT/infra tenders.\n"
              "• Compresses CAPT technical tender evaluation cycles from months to days.\n"
              "• Drives $5M+ in sticky BigQuery & Vertex AI ARR toward CP4 ($136M commit)."
          ),
          references=[
              "UK HMRC & State of Oklahoma AI Procurement & Tax Modernization on GCP",
              "Oct 12 FY27 CAIT Ideation Mandate (Real-Time Ministerial Dashboards)",
          ],
      ),
      InnovationIdea(
          layer_tag="IDEA 3  |  LAYER 3: PROJECT-EMBEDDED INFRASTRUCTURE AI",
          title="MEW & KPC Grid/Water Digital Twin & Agentic ServiceNow Ops",
          header_bg="#7C2D12",
          accent_color="#F97316",
          target_entities="• Ministry of Electricity & Water (MEW — $492k PSF), KPC/KOC, CAIT ServiceNow",
          use_case_and_architecture=(
              "• Embed Vertex AI Forecasting & BigQuery Geospatial into MEW's Data Platform ($132k PSF) + E-Services ($250k PSF) and the $60M ServiceNow deployment.\n"
              "• Predicts summer peak-load substation faults & water distribution leaks 72 hours ahead.\n"
              "• Auto-triggers predictive maintenance workflows and field-crew safety dispatches inside ServiceNow ITOM/FSM while securing OT telemetry via GovShield SecOps."
          ),
          business_value_and_afa_impact=(
              "• Reduces unplanned summer grid/water outages by 20–30% & protects field workers.\n"
              "• Directly differentiates Google's $60M ServiceNow + 5 GCP Use Cases against Microsoft.\n"
              "• Expands KOC ($6.48M PSO) & MEW into high-consumption AI factories."
          ),
          references=[
              "National Grid ESO & AES Corp Predictive Grid AI on Google Cloud",
              "Kuwait MEW Data Platform, E-Services & Health/Safety PSF Track ($492k)",
          ],
      ),
  ]
  return InnovationRadarOutput(ideas=ideas)


todo_and_reminders_agent = LlmAgent(
    name="todo_and_reminders_agent",
    model="gemini-3.5-flash",
    mode="single_turn",
    include_contents="none",
    description="Synthesizes Willem's Top 10 To-Do list (This Week vs. Next Week + Due Date) and 2-5 day Colleague Reminder Tracker.",
    instruction=(
        "Extract Willem Clappaert's Top 10 Priority To-Do items from his Calendar, "
        "Gmail, and Meet transcripts (strictly capped at 10 items, tagged THIS WEEK "
        "or NEXT WEEK with explicit due_date). Also identify colleagues Willem asked "
        "to take an action who have not yet completed it, calculating days_elapsed "
        "and staging kind 2-5 day reminder drafts without sending any external emails."
    ),
    output_schema=TodoAndRemindersOutput,
    output_key="todo_and_reminders",
    fallback_handler=_default_todo_and_reminders,
)

pso_risks_agent = LlmAgent(
    name="pso_risks_agent",
    model="gemini-3.5-flash",
    mode="single_turn",
    include_contents="none",
    description="Synthesizes PSO project status, KPIs, and RAG risks/issues across Kuwait workstreams.",
    instruction=(
        "Synthesize PSO project portfolio status, KPIs, and critical delivery/commercial "
        "risks across ServiceNow ($60M MP cap), Migration Factory (SOW2/SOW3 & MoJ KIN), "
        "Digital Resilience ($3.67M wartime DR pushback), National Skilling (37.5% TIF waste), "
        "GovShield, MoE Gemini for Education, Apigee Ph2, and Data Platform."
    ),
    output_schema=PsoPortfolioOutput,
    output_key="pso_portfolio",
    fallback_handler=_default_pso_portfolio,
)

afa_financials_agent = LlmAgent(
    name="afa_financials_agent",
    model="gemini-3.5-flash",
    mode="single_turn",
    include_contents="none",
    description="Computes Commit Period 3 (CP3) attainment, roll-overs, consumed, and gaps for GCP, PSO, GWS, PSF, TIF, and Credits.",
    instruction=(
        "Compute exact Commit Period 3 (Feb 27, 2026 – Feb 26, 2027) attainment, "
        "CP2 roll-overs/shortfalls, net paid amounts, and gaps for GCP, PSO, and Workspace, "
        "plus CP3 pools, approved/consumed amounts, and WIP pipelines for PSF, TIF, and Cloud Credits."
    ),
    output_schema=AfaConsumptionOutput,
    output_key="afa_consumption",
    fallback_handler=_default_afa_consumption,
)

innovation_radar_agent = LlmAgent(
    name="innovation_radar_agent",
    model="gemini-3.5-flash",
    mode="single_turn",
    include_contents="none",
    description="Generates 3 weekly new innovative digital transformation & Gemini Enterprise ideas for the Kuwait Government.",
    instruction=(
        "Generate 3 net-new, high-impact digital transformation and Gemini Enterprise "
        "use cases for the Kuwait Government aligned with New Kuwait Vision 2035 and "
        "Willem's 3-Layer National AI Factory (Citizen/Employee, Entity, Project-Embedded), "
        "including Use Cases, Business Value, and verified Public Sector References."
    ),
    output_schema=InnovationRadarOutput,
    output_key="innovation_radar",
    fallback_handler=_default_innovation_radar,
)
