import os
import base64
import time
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# Set up Google API credentials
SCOPES = ['https://www.googleapis.com/auth/gmail.modify', 'https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_FILE = 'path/to/your/service_account.json'

creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)

gmail_service = build('gmail', 'v1', credentials=creds)
drive_service = build('drive', 'v3', credentials=creds)

# Function to read unread emails
def get_unread_emails():
    try:
        results = gmail_service.users().messages().list(userId='me', labelIds=['INBOX'], q='is:unread').execute()
        messages = results.get('messages', [])

        email_data = []

        for message in messages:
            msg = gmail_service.users().messages().get(userId='me', id=message['id']).execute()
            email_subject = ''
            email_sender = ''

            for header in msg['payload']['headers']:
                if header['name'] == 'Subject':
                    email_subject = header['value']
                if header['name'] == 'From':
                    email_sender = header['value']

            email_body = base64.urlsafe_b64decode(msg['payload']['body']['data']).decode('utf-8')

            email_data.append({
                'id': message['id'],
                'sender': email_sender,
                'subject': email_subject,
                'body': email_body
            })

        return email_data

    except HttpError as error:
        print(f'An error occurred: {error}')
        return []

# Function to search Google Drive
def search_drive(query):
    try:
        results = drive_service.files().list(q=query, pageSize=5, fields="files(id, name, mimeType)").execute()
        files = results.get('files', [])
        return files
    except HttpError as error:
        print(f'An error occurred: {error}')
        return []

# Function to send email with attachment
def send_email(receiver, subject, body, file_id):
    try:
        file = drive_service.files().get(fileId=file_id, fields='name').execute()
        file_name = file['name']

        request = drive_service.files().get_media(fileId=file_id)
        file_path = f'/tmp/{file_name}'

        with open(file_path, 'wb') as f:
            f.write(request.execute())

        message = MIMEMultipart()
        message['to'] = receiver
        message['subject'] = subject

        message.attach(MIMEText(body, 'plain'))

        attachment = MIMEBase('application', 'octet-stream')
        attachment.set_payload(open(file_path, 'rb').read())
        encoders.encode_base64(attachment)
        attachment.add_header('Content-Disposition', f'attachment; filename={file_name}')

        message.attach(attachment)

        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')

        gmail_service.users().messages().send(userId='me', body={'raw': raw_message}).execute()

        print(f'Email sent to {receiver}')

    except HttpError as error:
        print(f'An error occurred: {error}')

# Main loop
def main():
    while True:
        print("Checking for new emails...")
        emails = get_unread_emails()

        for email in emails:
            print(f"Processing email from {email['sender']}")

            # Search Drive based on keywords in the email body
            search_query = f"fullText contains '{email['body']}'"
            files = search_drive(search_query)

            if files:
                # Send the first matching file
                send_email(email['sender'], 'Requested Data', 'Here is the data you requested.', files[0]['id'])
            else:
                send_email(email['sender'], 'Data Not Found', 'Sorry, we could not find the requested data.', None)

            # Mark email as read
            gmail_service.users().messages().modify(userId='me', id=email['id'], body={'removeLabelIds': ['UNREAD']}).execute()

        time.sleep(60)  # Check every 60 seconds

if __name__ == '__main__':
    main()
