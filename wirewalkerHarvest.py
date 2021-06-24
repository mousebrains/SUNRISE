#! /usr/bin/python3
#
# A GMAIL API client to read email from gmail for SUNRISE
#
# Install the google client library with oauth2 support:
#  https://developers.google.com/gmail/api/quickstart/python
#  python3 -m pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib
# June-2021, Pat Welch, pat@mousebrains.com

import argparse
import MyLogger
import logging
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import re
import datetime
import time
import sqlite3

def toCSV(fn:str, rows:tuple, logger:logging.Logger) -> bool:
    qHdr = not os.path.exists(fn)
    logger.info("toCSV fn %s qHdr %s n %s", fn, qHdr, len(rows))
    try:
        with open(fn, "a") as fp:
            if qHdr: fp.write("t,device,latitude,longitude\n")
            for row in rows: fp.write(",".join(map(str, row)) + "\n")
        return True
    except:
        logger.exception("Error writing to %s", fn)
    return False

def toDB(dbName:str, csvName:str, records:list, logger:logging.Logger) -> None:
    sqlTable = "CREATE TABLE IF NOT EXISTS fixes (\n"
    sqlTable+= "  t TEXT,"
    sqlTable+= "  device TEXT,"
    sqlTable+= "  latitude REAL,"
    sqlTable+= "  longitude REAL,"
    sqlTable+= "  qCSV BOOL DEFAULT 0,"
    sqlTable+= "  PRIMARY KEY(t, device)\n"
    sqlTable+= ");"

    sqlIndex = "CREATE INDEX IF NOT EXISTS fixes_qCSV ON fixes (qCSV);"

    sqlInsert = "INSERT OR IGNORE INTO fixes VALUES(?,?,?,?,0);"

    sqlCSV = "SELECT t,device,latitude,longitude FROM fixes"
    if os.path.exists(csvName): sqlCSV+= " WHERE qCSV=0"
    sqlCSV+= " ORDER BY t;"

    sqlSET = "UPDATE fixes SET qCSV=1 WHERE t=? AND device=?;"

    csvRows = []

    logger.info("db %s n %s", dbName, len(records))
    with sqlite3.connect(dbName) as db:
        cur = db.cursor()
        cur.execute("BEGIN;")
        cur.execute(sqlTable)
        cur.execute(sqlIndex)
        for row in records: cur.execute(sqlInsert, row);
        cur.execute(sqlCSV)
        for row in cur: csvRows.append((row[0], row[1], row[2], row[3]))
        cur.execute("COMMIT;")
        if toCSV(csvName, csvRows, logger):
            cur.execute("BEGIN;")
            for row in csvRows: cur.execute(sqlSET, (row[0], row[1]))
            cur.execute("COMMIT;")

def decodeMessage(body:dict, logger:logging.Logger) -> dict:
    info = {} # Information harvested from this message
    if "snippet" not in body:
        logger.info("Snippet not in body")
        return None
    # Ignore milliseconds
    matches = re.match(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})[.]\d{3}Z " \
            + r"([+-]?\d+[.]\d*) ([+-]?\d+[.]\d*)", body["snippet"])
    if not matches:
        logger.info("Snippet match failed %s", body["snippet"])
        return None
    t = datetime.datetime(int(matches[1]), int(matches[2]), int(matches[3]),
            int(matches[4]), int(matches[5]), int(matches[6]))
    info = {"t": t, "latitude": float(matches[7]), "longitude": float(matches[8])}

    if "payload" not in body:
        logger.info("Payload not in body")
        return None
    
    if "headers" not in body["payload"]:
        logger.info("Headers not in payload")
        return None

    for hdr in body["payload"]["headers"]:
        if hdr["name"] != "Subject": continue
        matches = re.match("Xeos Forward - ([A-Za-z0-9 ]+)", hdr["value"])
        if matches is None:
            logger.info("Match failed for subject, %s", hdr["value"])
            continue
        info["id"] = matches[1]
        break

    if "id" not in info: return None

    return (info["t"], info["id"], info["latitude"], info["longitude"])

parser = argparse.ArgumentParser()
MyLogger.addArgs(parser)
parser.add_argument("--db", type=str, default="/home/pat/logs/wirewalker.db",
        help="SQLite3 database of wire walker fixes")
parser.add_argument("--csv", type=str, default="/home/pat/Dropbox/Shore/WireWalker/wirewalker.csv",
        help="Wire Walker fixes in a growing CSV file")
parser.add_argument("--token", type=str, default="/home/pat/.config/ww.token.json",
        help="JSON token file for GMAIL login")
parser.add_argument("--creds", type=str, default="/home/pat/.config/ww.creds.json",
        help="JSON credentials file for GMAIL login")
parser.add_argument("--dt", type=float, default=180, help="Time between fetching messages")
args = parser.parse_args()

logger = MyLogger.mkLogger(args, fmt="%(asctime)s %(levelname)s: %(message)s")
logger.info("db %s csv %s", args.db, args.csv)

try:
    SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
    while True:
        # Get a valid set of credentials to access GMAIL
        creds = None
        if os.path.exists(args.token):
            creds = Credentials.from_authorized_user_file(args.token, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(args.creds, SCOPES)
                creds = flow.run_console()
            with open(args.token, "w") as token:
                token.write(creds.to_json())

        service = build("gmail", "v1", credentials=creds, cache_discovery=False) # GMAIL API
        #  # Get the UNREAD message ids
        msgs = service.users().messages().list(userId="me", labelIds="UNREAD").execute()
        if msgs and "messages" in msgs:
            records = []
            for item in msgs["messages"]:
                ident = item["id"]
                body = service.users().messages().get(userId="me", id=ident, format="metadata") \
                        .execute()
                info = decodeMessage(body, logger)
                service.users().messages() \
                        .modify(userId="me", id=ident, body={"removeLabelIds": ["UNREAD"]}) \
                        .execute()
                if info is not None: records.append(info)
            if records: toDB(args.db, args.csv, records, logger)
        if msgs and "nextPageToken" in msgs:
            logger.info("More messages to get, skip sleeping")
            continue
        logger.info("Sleeping for %s seconds", args.dt)
        time.sleep(args.dt)
except:
    logger.exception("Unexpected exception")
