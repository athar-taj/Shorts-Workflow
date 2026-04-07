import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from app.config import settings
from app.utils.logger import get_logger

log = get_logger("service.youtube")

# If modifying these scopes, delete the file youtube_token.json.
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


class YouTubeUploadService:
    def __init__(self):
        self.creds = None
        self._authenticate()

    def _authenticate(self):
        """Handle the OAuth2 authentication."""
        if os.path.exists(settings.yt_credentials_cache):
            self.creds = Credentials.from_authorized_user_file(settings.yt_credentials_cache, SCOPES)
        
        # If there are no (valid) credentials available, let the user log in.
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                log.info("Refreshing expired YouTube token...")
                self.creds.refresh(Request())
            else:
                log.info("Starting new YouTube OAuth2 flow. Check your console. A browser window will open...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    settings.yt_client_secrets_file, SCOPES
                )
                # This explicitly locks the local callback server to port 8080.
                self.creds = flow.run_local_server(port=8080)
            
            # Save the credentials for the next run
            with open(settings.yt_credentials_cache, "w") as token:
                token.write(self.creds.to_json())
        
        self.youtube = build("youtube", "v3", credentials=self.creds)

    def upload_short(self, video_path: str, title: str, description: str, category_id: str = "24", tags: list[str] = None):
        """Uploads a vertical short to YouTube."""
        log.info(f"Starting YouTube Upload for: {title}")
        
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Cannot upload {video_path} - file doesn't exist.")

        tags = tags or ["Shorts", "Trending", "Viral"]

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": category_id
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False
            }
        }

        # MediaFileUpload handles splitting the video into chunks
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")

        request = self.youtube.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=media
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                log.info(f"Uploaded {int(status.progress() * 100)}%")

        video_id = response.get("id")
        log.info(f"Upload Complete! Video ID: {video_id}")
        return video_id
