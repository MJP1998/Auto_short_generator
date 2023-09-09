import httplib2
import random
import time
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

RETRIABLE_EXCEPTIONS = (httplib2.HttpLib2Error, IOError)
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]
YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"
MAX_RETRIES = 10


def upload_youtube_video(file_path, client_secret_path, title=" ", description=" ", category="24", keywords="", privacy_status="private"):
    # Authenticate and construct service.
    flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, scopes=[YOUTUBE_UPLOAD_SCOPE])
    credentials = flow.run_local_server()
    youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, credentials=credentials)

    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': keywords.split(","),
            'categoryId': category
        },
        'status': {
            'privacyStatus': privacy_status
        }
    }

    insert_request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=MediaFileUpload(file_path, chunksize=-1, resumable=True)
    )

    resumable_upload(insert_request)


def resumable_upload(request):
    response = None
    error = None
    retry = 0

    while response is None:
        try:
            print("Uploading file...")
            status, response = request.next_chunk()

            if 'id' in response:
                print(f"Video id '{response['id']}' was successfully uploaded.")
            else:
                print(f"The upload failed with an unexpected response: {response}")
        except HttpError as e:
            if e.resp.status in RETRIABLE_STATUS_CODES:
                error = f"A retriable HTTP error {e.resp.status} occurred:\n{e.content.decode('utf-8')}"
            else:
                raise
        except RETRIABLE_EXCEPTIONS as e:
            error = f"A retriable error occurred: {e}"

        if error is not None:
            print(error)
            retry += 1
            if retry > MAX_RETRIES:
                print("No longer attempting to retry.")
                return

            sleep_seconds = random.random() * (2 ** retry)
            print(f"Sleeping {sleep_seconds} seconds and then retrying...")
            time.sleep(sleep_seconds)