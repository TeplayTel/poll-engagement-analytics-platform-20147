from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# PUBLIC_INTERFACE
class EventMetadata(BaseModel):
    """Device, platform, and session metadata attached to an event."""
    device_type: str = Field(..., description="Device type, e.g. mobile, desktop, tv")
    platform: str = Field(..., description="Platform identifier, e.g. ios, android, web, smarttv")
    app_version: Optional[str] = Field(None, description="App or frontend version")
    user_id: Optional[str] = Field(None, description="User account or system identifier.")
    session_id: str = Field(..., description="Unique or semi-unique session hash.")
    geo: Optional[str] = Field(None, description="ISO country code or city if available.")
    additional: Optional[Dict[str, Any]] = Field(None, description="Other auxiliary metadata as submitted")


# PUBLIC_INTERFACE
class PollEventIn(BaseModel):
    """Incoming poll event submission from frontend."""
    event_id: str = Field(..., description="Unique event (impression/vote) id for deduplication.")
    poll_id: str = Field(..., description="The poll's unique id.")
    event_type: str = Field(..., description="impression | vote | abandonment (custom types allowed)")
    user_choice: Optional[str] = Field(None, description="If voting, contains the choice voted for.")
    timestamp: datetime = Field(..., description="Datetime of the event as reported by the client.")
    metadata: EventMetadata = Field(..., description="Device/platform/session info and more.")

# PUBLIC_INTERFACE
class PollEventDb(PollEventIn):
    """Stored poll event in database (with database received/processed time)."""
    id: int = Field(..., description="Backend-generated record id (primary key)")
    received_at: datetime = Field(..., description="Time received by backend (system clock)")

# PUBLIC_INTERFACE
class EventFilter(BaseModel):
    """Filter criteria for querying poll events/analytics."""
    poll_id: Optional[str] = Field(None, description="Filter by poll id")
    event_type: Optional[str] = Field(None, description="Filter by event type")
    event_id: Optional[str] = Field(None, description="Filter by event id (for debugging)") 
    user_id: Optional[str] = Field(None, description="Filter by user/account id")
    start_time: Optional[datetime] = Field(None, description="Start timestamp filter")
    end_time: Optional[datetime] = Field(None, description="End timestamp filter")

# PUBLIC_INTERFACE
class PollAnalyticsSummary(BaseModel):
    """High-level analytics summary result for a poll."""
    poll_id: str = Field(..., description="Poll id the summary describes")
    total_impressions: int = Field(..., description="Number of unique impressions")
    total_votes: int = Field(..., description="Number of unique votes")
    participants: int = Field(..., description="Unique participants (votes)")
    vote_distribution: Dict[str, int] = Field(..., description="Vote counts by option")
    device_breakdown: Dict[str, int] = Field(..., description="Events by device type")
    platform_breakdown: Dict[str, int] = Field(..., description="Events by platform")
    geo_breakdown: Dict[str, int] = Field(..., description="Events by geo region (if present)")
    first_event_at: Optional[datetime] = Field(None, description="First event for poll")
    last_event_at: Optional[datetime] = Field(None, description="Last event for poll")


# PUBLIC_INTERFACE
class EventLogResponse(BaseModel):
    """API response after event ingestion"""
    deduplicated: bool = Field(..., description="Was this event a duplicate (deduped)?")
    stored: bool = Field(..., description="Was this event logged in db?")
    reason: Optional[str] = Field(None, description="If not stored or deduped, explains why.")


# PUBLIC_INTERFACE
class AnalyticsQueryResponse(BaseModel):
    """Detailed event query response, for list endpoints."""
    events: List[PollEventDb]
    total_count: int

