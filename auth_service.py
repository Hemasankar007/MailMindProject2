import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from pathlib import Path

class GmailAuthService:
    def __init__(self):
        # Use minimal scope that should work
        self.scopes = ['https://www.googleapis.com/auth/gmail.modify']
        self.token_file = 'token.json'
        self.credentials_file = 'credentials.json'
        
    def authenticate(self):
        """Authenticate with Gmail API"""
        creds = None
        
        # Load existing token if available
        if os.path.exists(self.token_file):
            try:
                with open(self.token_file, 'r') as token:
                    creds_data = json.load(token)
                    creds = Credentials.from_authorized_user_info(creds_data, self.scopes)
            except Exception as e:
                print(f"Error loading credentials: {e}")
                if os.path.exists(self.token_file):
                    os.remove(self.token_file)
                creds = None
        
        # If no valid credentials available, let the user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    print(f"Error refreshing token: {e}")
                    creds = None
        
        if not creds or not creds.valid:
            if not os.path.exists(self.credentials_file):
                raise FileNotFoundError(
                    f"Credentials file '{self.credentials_file}' not found. "
                    "Please download it from Google Cloud Console and place it in the project directory."
                )
            
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, 
                    self.scopes
                )
                creds = flow.run_local_server(port=0, open_browser=True)
            except Exception as e:
                raise Exception(f"Authentication failed: {e}")
        
        # Save the credentials for the next run
        try:
            with open(self.token_file, 'w') as token:
                token.write(creds.to_json())
        except Exception as e:
            print(f"Warning: Could not save token: {e}")
        
        return creds
    
    def get_gmail_service(self, creds):
        """Build and return the Gmail service"""
        try:
            return build('gmail', 'v1', credentials=creds, static_discovery=False)
        except Exception as e:
            raise Exception(f"Failed to create Gmail service: {e}")