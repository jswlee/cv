# YouTube Livestream Capture with S3 Upload

This script captures snapshots from YouTube livestreams and can either save them locally or upload them directly to an Amazon S3 bucket.

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
- Default region name (e.g., us-east-1)
- Default output format (json)

#### Option B: Environment Variables
```bash
export AWS_ACCESS_KEY_ID=your_access_key_here
export AWS_SECRET_ACCESS_KEY=your_secret_key_here
export AWS_DEFAULT_REGION=us-east-2
```

### 3. S3 Bucket Setup

1. Create an S3 bucket in your AWS account
2. Create an IAM user with the following permissions:
   - `s3:PutObject`
   - `s3:GetBucketLocation`
   - `s3:ListBucket`

## Usage

### Local File Saving (Original Behavior)
```bash
python livestream_capture_youtube.py --url "https://www.youtube.com/watch?v=VIDEO_ID" --interval 10 --max-runtime 300
```

### S3 Upload Test
```bash
python3 livestream_capture_youtube.py \
  --s3-bucket "haleakala-scraped-screenshots" \
  --s3-prefix "test" \
  --interval 10 \
  --max-runtime 30 \
  --aws-region "us-east-2"
```

## Command Line Arguments

- `--url`: YouTube livestream URL to capture
- `--interval`: Seconds between snapshots (default: 5)
- `--max-runtime`: Total runtime in seconds; 0 = run until Ctrl+C (default: 30)
- `--output-dir`: Directory for local saving (ignored if using S3)
- `--s3-bucket`: S3 bucket name for uploads (enables S3 mode)
- `--s3-prefix`: Optional S3 key prefix (like a folder path)
- `--aws-region`: AWS region for S3 client (default: us-east-2)

## Error Handling

The script includes robust error handling for S3 operations:
- Automatic retries with exponential backoff
- Credential validation on startup
- Bucket accessibility checks
- Detailed logging of upload status

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
- Check environment variables or AWS CLI configuration

### "S3 bucket does not exist" 
- Ensure the bucket name is correct and exists in your account
- Verify you're using the correct AWS region

### "Access Denied"
- Check that your AWS credentials have the necessary S3 permissions
- Verify the bucket policy allows your account to write objects
