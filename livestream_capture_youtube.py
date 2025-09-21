#!/usr/bin/env python3
"""
YouTube Livestream Capture for macOS
Captures snapshots from a YouTube livestream and uploads to S3
"""

import argparse
import time
import logging
from datetime import datetime
import cv2
import random
from utils import (
    get_youtube_livestream_url,
    read_config,
    create_s3_client,
    ensure_bucket_access,
    upload_bytes_to_s3,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("youtube_capture.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class YouTubeCapture:
    def __init__(self, url, s3_bucket, s3_prefix=None, interval=5, max_runtime=None, aws_region='us-east-2'):
        """Initialize YouTube capture with S3 upload
        
        Args:
            url: YouTube URL to capture
            s3_bucket: S3 bucket name for uploads
            s3_prefix: S3 key prefix for uploaded files (if None, uses domain-based naming)
            interval: Seconds between captures
            max_runtime: Maximum runtime in seconds
            aws_region: AWS region for S3 client
        """
        self.url = url
        self.s3_bucket = s3_bucket
        self.interval = interval
        self.max_runtime = max_runtime
        
        # Determine S3 prefix
        self.s3_prefix = s3_prefix if s3_prefix else "youtube"
        
        # Initialize S3 client via utils
        self.s3_client = create_s3_client(aws_region)
        ensure_bucket_access(self.s3_client, self.s3_bucket)
        logger.info(f"S3 bucket '{self.s3_bucket}' is accessible")
        logger.info(f"Using S3 prefix: {self.s3_prefix}")

    def get_stream_url(self):
        """Get the direct stream URL using yt-dlp Python API, picking highest-res playable stream.

        Strategy:
        - Use yt-dlp Python API instead of subprocess calls
        - Prefer H.264/AVC ("avc"/"h264") video codecs when available
        - Among candidates, pick the highest height
        - Prefer HLS (m3u8) protocols which OpenCV can read
        - Fallback to yt-dlp's best URL
        """
        try:
            import yt_dlp
            logger.info(f"Getting stream URL for: {self.url}")
            
            # Configure yt-dlp options
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'format': 'best',  # Default format
            }
            
            # Use a context manager to ensure proper cleanup
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract info
                info = ydl.extract_info(self.url, download=False)
                
                # If yt-dlp already gave a direct URL (best), keep it as fallback
                fallback_url = info.get("url")
                
                formats = info.get("formats") or []
                if not formats:
                    if fallback_url:
                        logger.info("No formats list; using fallback best URL from yt-dlp")
                        return fallback_url
                    raise ValueError("No formats available in yt-dlp output")
                
                def is_h264(fmt):
                    v = (fmt.get("vcodec") or "").lower()
                    return ("avc" in v) or ("h264" in v)
                
                def is_hls(fmt):
                    p = (fmt.get("protocol") or "").lower()
                    ext = (fmt.get("ext") or "").lower()
                    return ("m3u8" in p) or (ext == "m3u8")
                
                def playable(fmt):
                    # Must have video
                    vcodec = fmt.get("vcodec")
                    return vcodec and vcodec != "none"
                
                # Build candidate lists
                candidates = [f for f in formats if playable(f)]
                h264_candidates = [f for f in candidates if is_h264(f)]
                
                def key(fmt):
                    # Sort by height desc, fps desc, hls preferred
                    height = fmt.get("height") or 0
                    fps = fmt.get("fps") or 0
                    hls_boost = 1 if is_hls(fmt) else 0
                    return (height, fps, hls_boost)
                
                chosen = None
                if h264_candidates:
                    chosen = sorted(h264_candidates, key=key, reverse=True)[0]
                elif candidates:
                    chosen = sorted(candidates, key=key, reverse=True)[0]
                
                if chosen and chosen.get("url"):
                    logger.info(
                        "Chosen format: %sx%s @ %sfps | vcodec=%s acodec=%s prot=%s ext=%s",
                        chosen.get("width"), chosen.get("height"), chosen.get("fps"),
                        chosen.get("vcodec"), chosen.get("acodec"), chosen.get("protocol"), chosen.get("ext")
                    )
                    return chosen.get("url")
                
                if fallback_url:
                    logger.info("Falling back to yt-dlp best URL")
                    return fallback_url
                
                raise ValueError("No suitable stream URL found")
                
        except Exception as e:
            logger.error(f"Error getting stream URL: {e}")
            return None
    
            
    def capture_snapshot(self, max_retries=3):
        """Capture a snapshot from the stream by opening a fresh connection each time
        
        Args:
            max_retries: Maximum number of retry attempts if capture fails
        
        Returns:
            str: Path to the saved image file, or None if capture failed
        """
        attempt = 0
        while attempt < max_retries:
            try:
                # Get a fresh stream URL each time
                stream_url = self.get_stream_url()
                if not stream_url:
                    logger.error(f"Failed to get stream URL (attempt {attempt+1}/{max_retries})")
                    attempt += 1
                    if attempt < max_retries:
                        # Add exponential backoff with jitter
                        backoff = (2 ** attempt) + random.uniform(0, 1)
                        logger.info(f"Retrying in {backoff:.1f} seconds...")
                        time.sleep(backoff)
                    continue
                
                # Open a new capture for this snapshot
                cap = cv2.VideoCapture(stream_url)
                if not cap.isOpened():
                    logger.error(f"Failed to open video stream (attempt {attempt+1}/{max_retries})")
                    cap.release()  # Ensure release even if not opened
                    attempt += 1
                    if attempt < max_retries:
                        # Add exponential backoff with jitter
                        backoff = (2 ** attempt) + random.uniform(0, 1)
                        logger.info(f"Retrying in {backoff:.1f} seconds...")
                        time.sleep(backoff)
                    continue
                
                # Read frame
                ret, frame = cap.read()
                
                # Always close the capture immediately
                cap.release()
                
                if not ret:
                    logger.error(f"Failed to read frame (attempt {attempt+1}/{max_retries})")
                    attempt += 1
                    if attempt < max_retries:
                        # Add exponential backoff with jitter
                        backoff = (2 ** attempt) + random.uniform(0, 1)
                        logger.info(f"Retrying in {backoff:.1f} seconds...")
                        time.sleep(backoff)
                    continue
                
                # Generate filename and upload to S3
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"youtube_snapshot_{timestamp}.jpg"
                
                # Encode image to JPEG in memory
                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 100]
                success, encoded_img = cv2.imencode('.jpg', frame, encode_param)
                
                if not success:
                    logger.error("Failed to encode image")
                    attempt += 1
                    if attempt < max_retries:
                        backoff = (2 ** attempt) + random.uniform(0, 1)
                        logger.info(f"Retrying in {backoff:.1f} seconds...")
                        time.sleep(backoff)
                    continue
                
                # Upload to S3
                image_data = encoded_img.tobytes()
                file_size = len(image_data) / (1024 * 1024)  # Size in MB
                s3_key = f"{self.s3_prefix}/{filename}" if self.s3_prefix else filename
                s3_url = upload_bytes_to_s3(self.s3_client, self.s3_bucket, s3_key, image_data, content_type='image/jpeg')
                if s3_url:
                    logger.info(f"Uploaded: {filename} | Size: {file_size:.1f}MB | Location: {s3_url}")
                    return s3_url
                else:
                    logger.error("Failed to upload to S3")
                    attempt += 1
                    if attempt < max_retries:
                        backoff = (2 ** attempt) + random.uniform(0, 1)
                        logger.info(f"Retrying in {backoff:.1f} seconds...")
                        time.sleep(backoff)
                    continue
                
            except Exception as e:
                logger.error(f"Error capturing snapshot (attempt {attempt+1}/{max_retries}): {e}")
                attempt += 1
                if attempt < max_retries:
                    # Add exponential backoff with jitter
                    backoff = (2 ** attempt) + random.uniform(0, 1)
                    logger.info(f"Retrying in {backoff:.1f} seconds...")
                    time.sleep(backoff)
        
        logger.error(f"Failed to capture snapshot after {max_retries} attempts")
        return None
        
    def run(self):
        """Run the capture process with error recovery for long-running sessions"""
        start_time = time.time()
        capture_count = 0
        consecutive_failures = 0
        max_consecutive_failures = 5
        
        try:
            # Verify we can get a stream URL before starting
            if not self.get_stream_url():
                logger.error("Failed to get initial stream URL. Exiting.")
                return
                
            # Show info
            logger.info(f"Capturing every {self.interval} seconds")
            if self.max_runtime:
                logger.info(f"Will run for {self.max_runtime} seconds")
            else:
                logger.info("Press Ctrl+C to stop")
            
            s3_location = f"s3://{self.s3_bucket}/{self.s3_prefix}"
            logger.info(f"Uploading to S3: {s3_location}")
                
            logger.info("Using fresh connection for each capture to prevent freezing")
            logger.info("Added error recovery with automatic retries")
            
            # Main loop
            while True:
                # Check max runtime
                if self.max_runtime and (time.time() - start_time) >= self.max_runtime:
                    logger.info(f"Maximum runtime reached. Captured {capture_count} images.")
                    break
                
                try:    
                    # Take snapshot with fresh connection each time (with retries)
                    if self.capture_snapshot():
                        capture_count += 1
                        consecutive_failures = 0  # Reset failure counter on success
                        
                        if self.max_runtime:
                            remaining = max(0, self.max_runtime - (time.time() - start_time))
                            logger.info(f"Captures: {capture_count} | Remaining: {remaining:.0f}s")
                    else:
                        consecutive_failures += 1
                        logger.warning(f"Snapshot capture failed. Consecutive failures: {consecutive_failures}")
                        
                        # If too many consecutive failures, try a longer cooldown period
                        if consecutive_failures >= max_consecutive_failures:
                            cooldown = 30 + random.uniform(0, 10)  # 30-40 second cooldown
                            logger.warning(f"Too many consecutive failures. Cooling down for {cooldown:.1f}s before retrying")
                            time.sleep(cooldown)
                            consecutive_failures = 0  # Reset after cooldown
                            
                            # Force Python garbage collection to help clean up resources
                            import gc
                            gc.collect()
                            
                except Exception as e:
                    consecutive_failures += 1
                    logger.error(f"Error in capture cycle: {e}")
                    logger.warning(f"Continuing to next cycle. Consecutive failures: {consecutive_failures}")
                
                # Wait for next interval
                time.sleep(self.interval)
                
        except KeyboardInterrupt:
            elapsed = time.time() - start_time
            logger.info(f"Stopped after {elapsed:.0f}s with {capture_count} captures")
        except Exception as e:
            logger.error(f"Critical error in main loop: {e}")
        finally:
            pass  # No cleanup needed for S3-only mode


def main():
    """Parse arguments and start capture"""
    parser = argparse.ArgumentParser(description="YouTube livestream snapshot capture")
    parser.add_argument(
        "--url", type=str, default=None,
        help="Direct URL of the YouTube livestream to capture (overrides --search-query)"
    )
    parser.add_argument(
        "--search-query", type=str,
        default="4K MAUI LIVE CAM WhalerCondo.net",
        help="YouTube search query used to find the livestream when --url is not provided"
    )
    parser.add_argument(
        "--interval", type=float, default=5,
        help="Seconds between snapshots (default: 5)"
    )
    parser.add_argument(
        "--max-runtime", type=int, default=30,
        help="Total runtime in seconds; 0 = run until Ctrl+C (default: 30)"
    )
    parser.add_argument(
        "--s3-bucket", type=str, required=True,
        help="S3 bucket name for uploading images"
    )
    parser.add_argument(
        "--s3-prefix", type=str, default=None,
        help="S3 key prefix for uploaded files (if not specified, uses domain-based naming like 'www.nps.gov')"
    )
    parser.add_argument(
        "--aws-region", type=str, default="us-east-2",
        help="AWS region for S3 client (default: us-east-2)"
    )
    args = parser.parse_args()

    # Handle max_runtime=0 meaning run indefinitely
    max_runtime = args.max_runtime if args.max_runtime > 0 else None
    
    # Resolve livestream URL: prefer explicit --url, otherwise use search query
    cfg = read_config() or {}
    resolved_url = args.url
    if not resolved_url:
        # Prefer CLI search-query over config default
        search_query = args.search_query or cfg.get("search_query")
        if not search_query:
            logger.error("No --url provided and no --search-query specified (or in config.yaml)")
            return 1
        resolved_url = get_youtube_livestream_url(search_query)
        if not resolved_url:
            logger.error("Failed to resolve YouTube URL from search query")
            return 1

    logger.info(f"Starting YouTube capture for {resolved_url}")
    
    try:
        # Create and run the capture
        capture = YouTubeCapture(
            url=resolved_url,
            s3_bucket=args.s3_bucket,
            s3_prefix=args.s3_prefix,
            interval=args.interval,
            max_runtime=max_runtime,
            aws_region=args.aws_region
        )
        capture.run()
    except Exception as e:
        logger.error(f"Fatal error in main: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    main()
