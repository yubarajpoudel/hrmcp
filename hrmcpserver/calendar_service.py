import datetime
import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

class CalendarService:

  @staticmethod
  def get_free_time_from_google(interviewer: str) -> dict:
    #initialize the google calendar
    creds = None
    if os.path.exists("google_service.json"):
      creds = Credentials.from_authorized_user_file("google_service.json", SCOPES)
    if not creds or not creds.valid:
      if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
      else:
        flow = InstalledAppFlow.from_client_secrets_file(
            "google_service.json", SCOPES
        )
        creds = flow.run_local_server(port=0)
    with open("google_service.json", "w") as token:
      token.write(creds.to_json())

    try:
      service = build("calendar", "v3", credentials=creds)
      now = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
      events_result = (
          service.events()
          .list(
              calendarId="primary",
              timeMin=now,
              maxResults=10,
              singleEvents=True,
              orderBy="startTime",
          )
          .execute()
      )
      events = events_result.get("items", [])

      if not events:
        print("No upcoming events found.")
        return

      # Prints the start and name of the next 10 events
      for event in events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        print(start, event["summary"])

    except HttpError as error:
      print(f"An error occurred: {error}")

    

    
    
  