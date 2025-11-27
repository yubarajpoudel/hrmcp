import datetime
import os.path
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Get the project root directory (parent of hrmcpserver)
PROJECT_ROOT = Path(__file__).parent.parent
CREDENTIALS_FILE = PROJECT_ROOT / "google_service.json"  # OAuth client secrets
TOKEN_FILE = PROJECT_ROOT / "token.json"  # Stored user credentials

class CalendarService:

  @staticmethod
  def _get_credentials():
    """
    Get Google Calendar credentials, handling authentication flow if needed.
    
    Returns:
        Credentials object or dict with error if authentication fails
    """
    creds = None
    
    # Load credentials from token file
    if TOKEN_FILE.exists():
      try:
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        print(f"Loaded credentials from {TOKEN_FILE}")
      except Exception as e:
        print(f"Error loading token file: {e}")
        creds = None
    
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
      if creds and creds.expired and creds.refresh_token:
        try:
          creds.refresh(Request())
          print("Refreshed expired credentials")
        except Exception as e:
          print(f"Error refreshing credentials: {e}")
          creds = None
      
      if not creds:
        if not CREDENTIALS_FILE.exists():
          return {
            "error": f"OAuth credentials file not found at {CREDENTIALS_FILE}",
            "message": "Please download OAuth 2.0 Client ID credentials from Google Cloud Console"
          }
        
        try:
          flow = InstalledAppFlow.from_client_secrets_file(
              str(CREDENTIALS_FILE), SCOPES
          )
          creds = flow.run_local_server(port=0)
          print("Completed OAuth flow")
        except Exception as e:
          return {
            "error": f"OAuth authentication failed: {str(e)}",
            "message": "Please check your google_service.json file"
          }
      
      # Save the credentials for the next run
      with open(TOKEN_FILE, "w") as token:
        token.write(creds.to_json())
        print(f"Saved credentials to {TOKEN_FILE}")
    
    return creds


  @staticmethod
  def schedule_interview_on_google(to_email: str, start_time: str, end_time: str, candidate_name: str = None, role: str = None) -> dict:
    """
    Schedule an interview on Google Calendar for the given time.
    
    Args:
        to_email: Email address of the interviewee
        start_time: Start time in ISO format (e.g., "2025-11-27T10:00:00+04:00")
        end_time: End time in ISO format (e.g., "2025-11-27T11:00:00+04:00")
        candidate_name: Optional name of the candidate
        role: Optional role being interviewed for
        
    Returns:
        dict: Event creation result with event link or error
    """
    # Get credentials
    creds = CalendarService._get_credentials()
    
    # Check if authentication failed
    if isinstance(creds, dict) and "error" in creds:
      return creds
    
    try:
      service = build("calendar", "v3", credentials=creds)
      
      # Build event summary
      summary = "Interview"
      if candidate_name and role:
        summary = f"Interview: {candidate_name} - {role}"
      elif candidate_name:
        summary = f"Interview: {candidate_name}"
      elif role:
        summary = f"Interview - {role}"
      
      # Build event description
      description = "Interview scheduled via HR Agent"
      if candidate_name:
        description += f"\nCandidate: {candidate_name}"
      if role:
        description += f"\nRole: {role}"
      
      # Create event
      event = {
        'summary': summary,
        'description': description,
        'start': {
          'dateTime': start_time,
          'timeZone': 'UTC',
        },
        'end': {
          'dateTime': end_time,
          'timeZone': 'UTC',
        },
        'attendees': [
          {'email': to_email},
        ],
        'reminders': {
          'useDefault': False,
          'overrides': [
            {'method': 'email', 'minutes': 24 * 60},  # 1 day before
            {'method': 'popup', 'minutes': 30},  # 30 minutes before
          ],
        },
        'conferenceData': {
          'createRequest': {
            'requestId': f"interview-{datetime.datetime.now().timestamp()}",
            'conferenceSolutionKey': {'type': 'hangoutsMeet'}
          }
        }
      }
      
      # Insert event
      event_result = service.events().insert(
        calendarId='primary',
        body=event,
        conferenceDataVersion=1,
        sendUpdates='all'  # Send email notifications to attendees
      ).execute()
      
      return {
        "success": True,
        "event_id": event_result.get('id'),
        "event_link": event_result.get('htmlLink'),
        "meet_link": event_result.get('hangoutLink'),
        "summary": summary,
        "start_time": start_time,
        "end_time": end_time,
        "attendee": to_email,
        "message": "Interview scheduled successfully"
      }
      
    except HttpError as error:
      return {
        "error": f"Google Calendar API error: {str(error)}",
        "success": False
      }
    except Exception as e:
      return {
        "error": f"Unexpected error: {str(e)}",
        "success": False
      }

  @staticmethod
  def get_free_time_from_google(interviewer: str) -> dict:
    """
    Get free time slots from Google Calendar for the given interviewer.
    
    Args:
        interviewer: Name of the interviewer
        
    Returns:
        dict: Calendar events and free time information
    """
    # Get credentials
    creds = CalendarService._get_credentials()
    
    # Check if authentication failed
    if isinstance(creds, dict) and "error" in creds:
      return creds

    try:
      service = build("calendar", "v3", credentials=creds)
      
      # Get current week boundaries (Monday to Sunday)
      now = datetime.datetime.now(tz=datetime.timezone.utc)
      # Find Monday of current week
      start_of_week = now - datetime.timedelta(days=now.weekday())
      start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
      # Find Sunday of current week
      end_of_week = start_of_week + datetime.timedelta(days=6, hours=23, minutes=59, seconds=59)
      
      # Fetch all events for the current week
      events_result = (
          service.events()
          .list(
              calendarId="primary",
              timeMin=start_of_week.isoformat(),
              timeMax=end_of_week.isoformat(),
              singleEvents=True,
              orderBy="startTime",
          )
          .execute()
      )
      events = events_result.get("items", [])
      
      # Define working hours (9 AM to 5 PM)
      work_start_hour = 9
      work_end_hour = 17
      
      # Calculate available time slots
      available_slots = []
      
      # Process each day of the week
      for day_offset in range(7):
        current_day = start_of_week + datetime.timedelta(days=day_offset)
        
        # Skip weekends (Saturday=5, Sunday=6)
        if current_day.weekday() >= 5:
          continue
        
        # Skip past days
        if current_day.date() < now.date():
          continue
        
        # Set working hours for this day
        day_start = current_day.replace(hour=work_start_hour, minute=0, second=0, microsecond=0)
        day_end = current_day.replace(hour=work_end_hour, minute=0, second=0, microsecond=0)
        
        # Get events for this specific day
        day_events = []
        for event in events:
          event_start_str = event["start"].get("dateTime", event["start"].get("date"))
          event_end_str = event["end"].get("dateTime", event["end"].get("date"))
          
          # Parse datetime
          if "T" in event_start_str:
            event_start = datetime.datetime.fromisoformat(event_start_str.replace("Z", "+00:00"))
            event_end = datetime.datetime.fromisoformat(event_end_str.replace("Z", "+00:00"))
          else:
            # All-day event
            continue
          
          # Check if event is on this day
          if event_start.date() == current_day.date():
            day_events.append({
              "start": event_start,
              "end": event_end,
              "summary": event.get("summary", "Busy")
            })
        
        # Sort events by start time
        day_events.sort(key=lambda x: x["start"])
        
        # Find gaps between events
        current_time = day_start
        
        for event in day_events:
          # If there's a gap before this event
          if current_time < event["start"]:
            # Add available slot
            available_slots.append({
              "start": current_time.isoformat(),
              "end": event["start"].isoformat(),
              "duration_minutes": int((event["start"] - current_time).total_seconds() / 60),
              "day": current_day.strftime("%A, %Y-%m-%d")
            })
          # Move current time to end of this event
          current_time = max(current_time, event["end"])
        
        # Check if there's time left at the end of the day
        if current_time < day_end:
          available_slots.append({
            "start": current_time.isoformat(),
            "end": day_end.isoformat(),
            "duration_minutes": int((day_end - current_time).total_seconds() / 60),
            "day": current_day.strftime("%A, %Y-%m-%d")
          })
      
      return {
        "interviewer": interviewer,
        "week_start": start_of_week.strftime("%Y-%m-%d"),
        "week_end": end_of_week.strftime("%Y-%m-%d"),
        "available_slots": available_slots,
        "total_slots": len(available_slots),
        "working_hours": f"{work_start_hour}:00 - {work_end_hour}:00"
      }

    except HttpError as error:
      return {
        "error": f"Google Calendar API error: {str(error)}",
        "interviewer": interviewer
      }
    except Exception as e:
      return {
        "error": f"Unexpected error: {str(e)}",
        "interviewer": interviewer
      }
  