# Live Stream & Webcam Capture with S3 Upload

This repository contains two Python scripts for capturing snapshots from live video sources and uploading them directly to Amazon S3:

1. **YouTube Livestream Capture** (`livestream_capture_youtube.py`) - Captures from YouTube live streams using yt-dlp and OpenCV
2. **Webcam Capture** (`webcam_capture.py`) - Captures from web-based cameras using Selenium WebDriver

Both scripts support S3-only uploads (no local file saving) and can be configured via command line arguments or `config.yaml`.

## Prerequisites

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. AWS Credentials Setup

You need to configure AWS credentials to use S3 functionality. Choose one of these methods:

#### Option A: AWS CLI Configuration (Recommended)
```bash
# Install AWS CLI if not already installed
pip install awscli

# Configure your credentials
aws configure
```
This will prompt you for:
- AWS Access Key ID
- AWS Secret Access Key  
- Default region name (e.g., us-east-2)
- Default output format (json)

#### Option B: Environment Variables
```bash
export AWS_ACCESS_KEY_ID=your_access_key_here
export AWS_SECRET_ACCESS_KEY=your_secret_key_here
export AWS_DEFAULT_REGION=us-east-2
```

#### Option C: .env File
Create a `.env` file in the project root:
```
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
YOUTUBE_API_KEY=your_youtube_api_key_here
```

### 3. S3 Bucket Setup

1. Create an S3 bucket in your AWS account
2. Create an IAM user with the following permissions:
   - `s3:PutObject`
   - `s3:GetBucketLocation`
   - `s3:ListBucket`

### 4. YouTube API Key (Optional)
For automatic YouTube URL discovery via search queries, get a YouTube Data API v3 key from the Google Cloud Console and add it to your `.env` file.

### 5. Chrome/Chromium Setup (For Webcam Capture)
Install Chrome or Chromium and chromedriver:
```bash
# Ubuntu/Debian
sudo apt install -y chromium-browser chromium-driver

# macOS with Homebrew
brew install --cask google-chrome
brew install chromedriver
```

## Configuration

Create a `config.yaml` file in the project root to set default URLs:

```yaml
search_query: "4K MAUI LIVE CAM BEACH CAM"
webcam_url: "https://www.nps.gov/media/webcam/view.htm?id=56F5E0DC-9116-8502-7F673D0FF0B8378A"
# webcam_url: "https://www.skylinewebcams.com/zh/webcam/united-states/hawaii/maui/kahului.html"
```

## Usage

### YouTube Livestream Capture

#### Using Search Query (Default)
```bash
python3 livestream_capture_youtube.py --s3-bucket "your-bucket-name"
```

#### Using Custom Search Query
```bash
python3 livestream_capture_youtube.py \
  --search-query "Hawaii beach live cam 4K" \
  --s3-bucket "your-bucket-name"
```

#### Using Direct URL
```bash
python3 livestream_capture_youtube.py \
  --url "https://www.youtube.com/watch?v=VIDEO_ID" \
  --s3-bucket "your-bucket-name" \
  --interval 30 \
  --max-runtime 300
```

### Webcam Capture

#### Using Default URL from config.yaml
```bash
python3 webcam_capture.py --s3-bucket "your-bucket-name"
```

#### Using Custom URL
```bash
python3 webcam_capture.py \
  --url "https://example.com/webcam" \
  --s3-bucket "your-bucket-name" \
  --zoom 1.5 \
  --interval 60
```

#### For Kahului Webcam (SkylineWebcams)
Uncomment the Kahului URL in `config.yaml` or use:
```bash
python3 webcam_capture.py \
  --url "https://www.skylinewebcams.com/zh/webcam/united-states/hawaii/maui/kahului.html" \
  --s3-bucket "your-bucket-name"
```

## Command Line Arguments

### Common Arguments (Both Scripts)
- `--s3-bucket`: S3 bucket name for uploads (required)
- `--s3-prefix`: S3 key prefix/folder (default: "youtube" or "webcam")
- `--interval`: Seconds between snapshots (default: 5)
- `--max-runtime`: Total runtime in seconds; 0 = run until Ctrl+C (default: 30)
- `--aws-region`: AWS region for S3 client (default: us-east-2)

### YouTube-Specific Arguments
- `--url`: Direct YouTube livestream URL (overrides search)
- `--search-query`: YouTube search query to find livestream

### Webcam-Specific Arguments
- `--url`: Webcam URL (overrides config.yaml)
- `--zoom`: Page zoom factor, e.g., 1.0, 1.25, 1.5 (default: 1.0)

## File Organization

Uploaded files are organized in S3 as:
- YouTube: `s3://bucket/youtube/youtube_snapshot_YYYYMMDD_HHMMSS.jpg`
- Webcam: `s3://bucket/webcam/webcam_snapshot_YYYYMMDD_HHMMSS.png`

## Special Features

### YouTube Livestream Capture
- **Automatic URL discovery**: Search YouTube for live streams using the Data API
- **Smart format selection**: Prefers H.264/AVC codecs and HLS streams for OpenCV compatibility
- **Fresh URLs**: Refreshes stream URLs each capture to prevent expiry
- **Retry logic**: Exponential backoff with automatic retries

### Webcam Capture
- **Interactive player support**: Automatically clicks play buttons and enters fullscreen for SkylineWebcams
- **Smart element detection**: Finds and captures the largest video/canvas/img element
- **Browser management**: Automatic browser restarts every 12 hours and on failures
- **Cross-frame support**: Works with iframed video players

## Error Handling

Both scripts include robust error handling:
- Automatic retries with exponential backoff
- AWS credential validation on startup
- S3 bucket accessibility checks
- Browser session management (webcam capture)
- Detailed logging of all operations

## Cost Considerations

- S3 PUT requests: ~$0.0005 per 1,000 requests
- S3 storage: ~$0.023 per GB/month (Standard tier)
- Data transfer: Free for uploads to S3

For a capture every 30 seconds running 24/7:
- ~2,880 images per day
- ~1 million images per year
- ~$0.50/year in PUT request costs (assuming 1MB images)

## Troubleshooting

### "AWS credentials not found"
- Verify your AWS credentials are configured correctly
- Check environment variables, `.env` file, or AWS CLI configuration

### "S3 bucket does not exist" 
- Ensure the bucket name is correct and exists in your account
- Verify you're using the correct AWS region

### "Access Denied"
- Check that your AWS credentials have the necessary S3 permissions
- Verify the bucket policy allows your account to write objects

### "YOUTUBE_API_KEY not found"
- Add your YouTube Data API v3 key to the `.env` file
- Or use direct URLs with `--url` instead of search queries

### "chromedriver not found" (Webcam capture)
- Install chromedriver: `sudo apt install chromium-driver` (Linux) or `brew install chromedriver` (macOS)
- Set `CHROMEDRIVER` environment variable to the binary path if needed

### Browser issues (Webcam capture)
- The script automatically restarts the browser on failures
- For persistent issues, try adjusting the `--zoom` factor
- Check that the webcam URL is accessible and contains video elements

## Examples

### Quick Test (30 seconds)
```bash
# YouTube
python3 livestream_capture_youtube.py --s3-bucket "test-bucket" --max-runtime 30

# Webcam
python3 webcam_capture.py --s3-bucket "test-bucket" --max-runtime 30
```

### Long-running Capture
```bash
# YouTube (run until Ctrl+C)
python3 livestream_capture_youtube.py \
  --s3-bucket "live-captures" \
  --s3-prefix "maui-beach" \
  --interval 60 \
  --max-runtime 0

# Webcam (run until Ctrl+C)
python3 webcam_capture.py \
  --s3-bucket "webcam-captures" \
  --s3-prefix "kahului-airport" \
  --interval 300 \
  --max-runtime 0
```
