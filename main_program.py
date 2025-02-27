import firebase_admin
from firebase_admin import credentials, firestore, auth
import click
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from datetime import datetime
import pytz

# Initialize Firebase
cred = credentials.Certificate("serviceAccountKey.json") 
firebase_admin.initialize_app(cred)
db = firestore.client()

# Load Google API credentials
def get_credentials():
    return Credentials.from_authorized_user_file("token.json", ["https://www.googleapis.com/auth/calendar"])

# Validate meeting time (Monday-Friday, 07:00-17:00)
def is_valid_meeting_time(meeting_time):
    tz = pytz.timezone("Africa/Johannesburg")
    meeting_dt = datetime.strptime(meeting_time, "%Y-%m-%dT%H:%M:%S").astimezone(tz)
    return 0 <= meeting_dt.weekday() <= 4 and 7 <= meeting_dt.hour < 17

# Register a user
@click.command()
@click.option("--name", prompt="Enter your name")
@click.option("--email", prompt="Enter your email")
@click.option("--password", prompt="Enter a password", hide_input=True, confirmation_prompt=True)
@click.option("--role", type=click.Choice(["mentor", "peer"]), prompt="Enter your role")
def register(name, email, password, role):
    """Register a new user."""
    try:
        user = auth.create_user(email=email, password=password)
        db.collection("users").document(user.uid).set({"name": name, "email": email, "role": role})
        print(f"User {name} registered successfully!")
    except Exception as e:
        print(f"Error: {e}")

# Login a user (simulated since Firebase Admin SDK doesn't handle logins)
@click.command()
@click.option("--email", prompt="Enter your email")
def login(email):
    """Login as a user."""
    user_ref = db.collection("users").where("email", "==", email).stream()
    user = next(user_ref, None)
    if user:
        print(f"Welcome back, {user.to_dict()['name']} ({user.to_dict()['role']})!")
    else:
        print("User not found.")

# Request a meeting
@click.command()
@click.option("--mentor-id", prompt="Enter Mentor ID")
@click.option("--mentee-id", prompt="Enter Your ID")
@click.option("--meeting-time", prompt="Enter Meeting Time (YYYY-MM-DDTHH:MM:SS)")
def book(mentor_id, mentee_id, meeting_time):
    """Request a meeting with a mentor."""
    if not is_valid_meeting_time(meeting_time):
        print("Meetings must be Monday-Friday between 07:00-17:00.")
        return
    meeting_id = f"meeting_{mentor_id}_{mentee_id}_{int(datetime.now().timestamp())}"
    db.collection("meetings").document(meeting_id).set({"mentor_id": mentor_id, "mentee_id": mentee_id, "time": meeting_time, "status": "pending"})
    print(f"Meeting requested with {mentor_id} at {meeting_time}. Awaiting confirmation.")

# Confirm a meeting & add to Google Calendar
@click.command()
@click.option("--meeting-id", prompt="Enter Meeting ID")
def confirm(meeting_id):
    """Confirm a meeting and add it to Google Calendar."""
    meeting_ref = db.collection("meetings").document(meeting_id)
    meeting = meeting_ref.get().to_dict()

    if meeting:
        mentor = db.collection("users").document(meeting["mentor_id"]).get().to_dict()
        mentee = db.collection("users").document(meeting["mentee_id"]).get().to_dict()
        
        if mentor and mentee:
            creds = get_credentials()
            service = build("calendar", "v3", credentials=creds)
            event = {
                "summary": "SkillSync Meeting",
                "start": {"dateTime": meeting["time"], "timeZone": "Africa/Johannesburg"},
                "end": {"dateTime": meeting["time"], "timeZone": "Africa/Johannesburg"},
                "attendees": [{"email": mentor["email"]}, {"email": mentee["email"]}]
            }
            event = service.events().insert(calendarId="primary", body=event).execute()
            meeting_ref.update({"status": "confirmed"})
            print(f"Meeting confirmed! View on Google Calendar: {event.get('htmlLink')}")
        else:
            print("User details not found.")

# CLI group
@click.group()
def cli():
    """SkillSync CLI Application."""
    pass

cli.add_command(register)
cli.add_command(login)
cli.add_command(book)
cli.add_command(confirm)

if __name__ == "__main__":
    cli()
