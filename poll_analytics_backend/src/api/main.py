from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware

from .analytics_models import (
    PollEventIn, EventFilter, PollAnalyticsSummary,
    EventLogResponse, AnalyticsQueryResponse
)
from .analytics_store import (
    log_event, query_events, poll_summary_analytics
)

description = """
API for Poll Engagement Analytics Platform.

* Log poll events (impressions, votes).
* Deduplication based on event_id.
* Capture device/platform/session metadata.
* Analytics endpoints for powerful filtering and breakdowns.
* Get poll analytics summary metrics.

All endpoints are well-documented for easy frontend and BI consumption.
"""

openapi_tags = [
    {"name": "Event Logging", "description": "Log poll events (impressions, votes) with dedup and device/session metadata"},
    {"name": "Analytics", "description": "Query events and retrieve poll analytics summaries"},
]

app = FastAPI(
    title="Poll Engagement Analytics API",
    version="1.0.0",
    description=description,
    openapi_tags=openapi_tags
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Health"])
def health_check():
    """PUBLIC_INTERFACE: Verify that the analytics service is operational."""
    return {"message": "Healthy"}


# PUBLIC_INTERFACE
@app.post("/fanEngage/analytics/v1/event", response_model=EventLogResponse, tags=["Event Logging"], summary="Log a poll event")
async def log_poll_event(payload: PollEventIn = Body(..., description="Event object with pollId, eventId, device metadata, etc.")):
    """
    Log an impression, vote, or poll event from the frontend, with deduplication enforced on event_id.
    Captures full device/platform/session/user metadata.
    """
    deduped, stored, reason = log_event(payload)
    return EventLogResponse(deduplicated=deduped, stored=stored, reason=reason)


# PUBLIC_INTERFACE
@app.post("/fanEngage/analytics/v1/query", response_model=AnalyticsQueryResponse, tags=["Analytics"], summary="Query poll events (advanced filter)")
async def analytics_query(
    filter: EventFilter = Body(..., description="Filter parameters for pollId, event_type, user_id, date range, etc."),
    limit: int = Query(100, ge=1, le=500), 
    offset: int = Query(0, ge=0)
):
    """
    Return filtered analytics event logs, including device/platform metadata, for detailed analytics and dashboards.
    """
    events, total_count = query_events(filter, limit=limit, offset=offset)
    return AnalyticsQueryResponse(events=events, total_count=total_count)


# PUBLIC_INTERFACE
@app.get("/fanEngage/analytics/v1/pollSummary", response_model=PollAnalyticsSummary, tags=["Analytics"], summary="Poll analytics summary metrics")
async def poll_summary(
    poll_id: str = Query(..., description="Poll id to fetch analytics for")
):
    """
    Returns high-level analytics summary for a given poll, including:
    - Total unique impressions, votes
    - Vote distribution
    - Device, platform, geo breakdown
    - First/last event timestamp
    """
    res = poll_summary_analytics(poll_id)
    if not res:
        raise HTTPException(status_code=404, detail="PollId not found")
    return res

