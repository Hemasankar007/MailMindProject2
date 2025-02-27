from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

def get_credentials():
    flow = InstalledAppFlow.from_client_secrets_file(
        'credentials.json',
        SCOPES)
    creds = flow.run_local_server(port=0)
    return creds

if __name__ == '__main__':
    credentials = get_credentials()
    with open('token.json', 'w') as token:
        token.write(credentials.to_json())