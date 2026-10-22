"""Stage 3: Deck Builder FunctionNode that creates & populates the 6-slide presentation."""

from __future__ import annotations

from typing import Any

from .._adk_compat import Context, Event, node
from ..schemas import DashboardPayload
from ..tools.slides_renderer import create_and_populate_dashboard_slides


@node(name="build_slides_deck_node")
def build_slides_deck_node(ctx: Context, node_input: dict[str, Any]) -> Event:
  """Merges the 4 domain synthesis outputs and builds the 6-slide Google Slides deck."""
  as_of = (
      ctx.state.get("raw_context", {})
      .get("collect_kuwait_innovation_context", {})
      .get("as_of_date", "Oct 22, 2026")
  )
  todo_rem = node_input.get("todo_and_reminders_agent") or ctx.state.get("todo_and_reminders", {})
  pso = node_input.get("pso_risks_agent") or ctx.state.get("pso_portfolio", {})
  afa = node_input.get("afa_financials_agent") or ctx.state.get("afa_consumption", {})
  innov = node_input.get("innovation_radar_agent") or ctx.state.get("innovation_radar", {})

  payload = DashboardPayload(
      as_of_date=as_of,
      presentation_title=f"Kuwait CAL Executive Priority Dashboard — Willem Clappaert ({as_of})",
      todo_and_reminders=todo_rem,
      pso_portfolio=pso,
      afa_consumption=afa,
      innovation_radar=innov,
  ).model_dump()

  render_res = create_and_populate_dashboard_slides(payload, export_thumbnails=False)
  payload["presentation_id"] = render_res["presentation_id"]
  payload["presentation_url"] = render_res["presentation_url"]
  payload["slide_thumbnails"] = render_res.get("slide_thumbnails", [])

  return Event(
      message=f"Built 6-slide presentation: {payload['presentation_url']}",
      output=payload,
      state={"dashboard_payload": payload},
  )
