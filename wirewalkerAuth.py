#! /usr/bin/python3
#
# A GMAIL API client to read email from gmail for SUNRISE
#
# Install the google client library with oauth2 support:
#  https://developers.google.com/gmail/api/quickstart/python
#  python3 -m pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib
# June-2021, Pat Welch, pat@mousebrains.com

import argparse
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import os.path

parser = argparse.ArgumentParser()
parser.add_argument("--token", type=str, default="/home/pat/.config/ww.token.json",
        help="JSON token file for GMAIL login")
parser.add_argument("--creds", type=str, default="/home/pat/.config/ww.creds.json",
        help="JSON credentials file for GMAIL login")
args = parser.parse_args()

try:
    SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
    # Get a valid set of credentials to access GMAIL
    creds = None
    if os.path.exists(args.token):
        creds = Credentials.from_authorized_user_file(args.token, SCOPES)
        print("Creds", creds)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing creds")
            creds.refresh(Request())
        else:
            print("Building flow")
            flow = InstalledAppFlow.from_client_secrets_file(args.creds, SCOPES)
            creds = flow.run_console()
        with open(args.token, "w") as token:
            token.write(creds.to_json())

    service = build("gmail", "v1", credentials=creds, cache_discovery=False) # GMAIL API
    # Get the UNREAD message ids
    msgs = service.users().messages().list(userId="me", labelIds="UNREAD").execute()
    if msgs and "messages" in msgs:
        for item in msgs["messages"]:
            print("id", item["id"])
except Exception as e:
    print(e)
