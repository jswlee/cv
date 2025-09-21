import os
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional, Dict, Any

# Optional dependencies
try:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except Exception:  # pragma: no cover
    build = None
    HttpError = Exception

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


# =======================
# S3 UTILS (centralized)
# =======================
try:
    import boto3  # type: ignore
    from botocore.exceptions import ClientError, NoCredentialsError  # type: ignore
except Exception:  # pragma: no cover
    boto3 = None
    ClientError = Exception
    NoCredentialsError = Exception


def create_s3_client(region_name: str):
    """Create and return an S3 client for a given region.
    Raises if boto3 is not available or credentials are missing.
    """
    if boto3 is None:
        raise RuntimeError("boto3 is not installed. Please install boto3 to use S3 features.")
    try:
        return boto3.client('s3', region_name=region_name)
    except NoCredentialsError as e:  # type: ignore[name-defined]
        raise RuntimeError("""
        AWS credentials not found. Configure your credentials:
        1. Create a .env file in the root directory of the project
        2. Add the following lines to the .env file:
        AWS_ACCESS_KEY_ID=your_access_key_id
        AWS_SECRET_ACCESS_KEY=your_secret_access_key

        OR

        1. Configure your AWS credentials using the AWS CLI
        2. Run the following command:
        aws configure
        3. Follow the prompts to enter your AWS access key ID and secret access key
        4. Verify that your credentials are correct by running the following command:
        aws s3 ls
        """) from e


def ensure_bucket_access(s3_client, bucket: str) -> None:
    """Validate that the S3 bucket is accessible by attempting a HeadBucket.
    Raises a RuntimeError on failure.
    """
    try:
        s3_client.head_bucket(Bucket=bucket)
    except ClientError as e:  # type: ignore[name-defined]
        # Propagate a clearer message upward
        code = getattr(getattr(e, 'response', {}).get('Error', {}), 'get', lambda *_: None)('Code')
        if code == '404':
            raise RuntimeError(f"S3 bucket '{bucket}' does not exist") from e
        raise RuntimeError(f"Error accessing S3 bucket '{bucket}': {e}") from e


def upload_bytes_to_s3(s3_client, bucket: str, key: str, data: bytes, content_type: str = 'image/jpeg') -> Optional[str]:
    """Upload raw bytes to S3 under the provided key.
    Returns the s3:// URL on success, or None on failure.
    """
    # Normalize key (no leading slash)
    key = key.lstrip('/')
    try:
        s3_client.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)
        return f"s3://{bucket}/{key}"
    except ClientError as e:  # type: ignore[name-defined]
        print(f"Failed to upload to S3: {e}")
        return None

# =======================
# OTHER UTILS
# =======================
def project_root() -> Path:
    # repo root assumed to be the directory of this file's parent
    return Path(__file__).parent


def read_config() -> Dict[str, Any]:
    """Read config.yaml if present at project root.
    Returns an empty dict if file doesn't exist or PyYAML isn't installed.
    """
    root = project_root()
    cfg_path = root / 'config.yaml'
    if not cfg_path.exists() or yaml is None:
        return {}
    try:
        with open(cfg_path, 'r') as f:
            data = yaml.safe_load(f) or {}
            if not isinstance(data, dict):
                return {}
            return data
    except Exception:
        return {}


def get_youtube_livestream_url(search_query: str) -> Optional[str]:
    """
    Searches YouTube using the official API and returns the URL of the first result.
    Requires YOUTUBE_API_KEY in environment (.env supported).
    """
    # Load environment variables from .env (if python-dotenv is available)
    if load_dotenv is not None:
        # load_dotenv does not error if file is missing; it returns False
        load_dotenv(dotenv_path=project_root() / '.env')
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        print("ERROR: YOUTUBE_API_KEY not found in environment.")
        return None

    if build is None:
        print("ERROR: google-api-python-client is not installed.")
        return None

    try:
        youtube_service = build("youtube", "v3", developerKey=api_key)
        print(f"Searching for: {search_query}")
        search_response = youtube_service.search().list(
            q=search_query,
            part="snippet",
            maxResults=1,
            type="video",
        ).execute()

        items = search_response.get("items", [])
        if not items:
            print(f"No video results found for '{search_query}'.")
            return None

        first = items[0]
        video_id = first["id"]["videoId"]
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        return video_url

    except HttpError as e:  # type: ignore[name-defined]
        print(f"An HTTP error occurred: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None
