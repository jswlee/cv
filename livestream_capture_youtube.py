#!/usr/bin/env python3
"""
YouTube Livestream Capture for macOS
Captures snapshots from a YouTube livestream at specified intervals
"""

import os
import argparse
import time
import logging
import subprocess
import json
from datetime import datetime
import cv2
from urllib.parse import urlparse

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
    def __init__(self, url, output_dir=None, interval=5, max_runtime=None):
        """Initialize YouTube capture with a single URL"""
        self.url = url
        
        # Set default output directory based on URL domain
        if output_dir is None:
            domain = urlparse(url).netloc
            if domain == "youtu.be" or domain == "www.youtube.com" or domain == "youtube.com":
                video_id = self._get_video_id(url)
                output_dir = f"images/youtube_{video_id}"
            else:
                output_dir = f"images/{domain}"
                
        self.output_dir = output_dir
        self.interval = interval
        self.max_runtime = max_runtime
        self.cap = None
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
    def _get_video_id(self, url):
        """Extract video ID from YouTube URL"""
        if "youtu.be" in url:
            return url.split("/")[-1]
        elif "youtube.com" in url:
            if "v=" in url:
                return url.split("v=")[1].split("&")[0]
            else:
                return url.split("/")[-1]
        return "unknown"
        
    def get_stream_url(self):
        """Get the direct stream URL using yt-dlp, picking highest-res playable stream.

        Strategy:
        - Parse all formats from yt-dlp JSON
        - Prefer H.264/AVC ("avc"/"h264") video codecs when available
        - Among candidates, pick the highest height
        - Prefer HLS (m3u8) protocols which OpenCV can read
        - Fallback to yt-dlp's best URL
        """
        try:
            logger.info(f"Getting stream URL for: {self.url}")
            cmd = [
                "yt-dlp",
                "--dump-json",
                self.url,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            info = json.loads(result.stdout)

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

        except subprocess.CalledProcessError as e:
            logger.error(f"yt-dlp error: {e.stderr}")
            return None
        except Exception as e:
            logger.error(f"Error getting stream URL: {e}")
            return None
    
    def setup_capture(self):
        """Setup video capture from YouTube stream"""
        try:
            stream_url = self.get_stream_url()
            if not stream_url:
                raise ValueError("Failed to get stream URL")
            
            # Open video capture
            self.cap = cv2.VideoCapture(stream_url)
            
            if not self.cap.isOpened():
                raise ValueError("Failed to open video stream")
                
            # Get video properties
            width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            logger.info(f"Stream opened: {width}x{height} at {fps:.1f} fps")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup capture: {e}")
            return False
            
    def capture_snapshot(self):
        """Capture a snapshot from the stream"""
        if not self.cap or not self.cap.isOpened():
            if not self.setup_capture():
                return None
                
        # Read frame
        ret, frame = self.cap.read()
        if not ret:
            logger.error("Failed to read frame")
            return None
            
        # Save image
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"youtube_snapshot_{timestamp}.jpg"
        filepath = os.path.join(self.output_dir, filename)
        
        # Save with higher JPEG quality
        cv2.imwrite(filepath, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
        
        # Get file size for logging
        file_size = os.path.getsize(filepath) / (1024 * 1024)  # Size in MB
        logger.info(f"Saved: {filename} | Size: {file_size:.1f}MB")
        
        return filepath
        
    def run(self):
        """Run the capture process"""
        start_time = time.time()
        capture_count = 0
        
        try:
            # Setup capture
            if not self.setup_capture():
                logger.error("Failed to initialize capture. Exiting.")
                return
                
            # Show info
            logger.info(f"Capturing every {self.interval} seconds")
            if self.max_runtime:
                logger.info(f"Will run for {self.max_runtime} seconds")
            else:
                logger.info("Press Ctrl+C to stop")
            logger.info(f"Saving to: {os.path.abspath(self.output_dir)}")
            
            # Main loop
            while True:
                # Check max runtime
                if self.max_runtime and (time.time() - start_time) >= self.max_runtime:
                    logger.info(f"Maximum runtime reached. Captured {capture_count} images.")
                    break
                    
                # Take snapshot
                if self.capture_snapshot():
                    capture_count += 1
                    if self.max_runtime:
                        remaining = max(0, self.max_runtime - (time.time() - start_time))
                        logger.info(f"Captures: {capture_count} | Remaining: {remaining:.0f}s")
                        
                # Wait for next interval
                time.sleep(self.interval)
                
        except KeyboardInterrupt:
            elapsed = time.time() - start_time
            logger.info(f"Stopped after {elapsed:.0f}s with {capture_count} captures")
        except Exception as e:
            logger.error(f"Error: {e}")
        finally:
            if self.cap:
                self.cap.release()
                logger.info("Video capture released")


def main():
    """Parse arguments and start capture"""
    parser = argparse.ArgumentParser(description="YouTube livestream snapshot capture")
    parser.add_argument(
        "--url", type=str,
        default="https://www.youtube.com/watch?v=DNnj_9bVWGI",
        help="URL of the YouTube livestream to capture"
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
        "--output-dir", type=str, default=None,
        help="Directory to save images (default: images/youtube_{video_id})"
    )
    args = parser.parse_args()

    # Handle max_runtime=0 meaning run indefinitely
    max_runtime = args.max_runtime if args.max_runtime > 0 else None

    logger.info(f"Starting YouTube capture for {args.url}")
    
    try:
        # Create and run the capture
        capture = YouTubeCapture(
            url=args.url,
            output_dir=args.output_dir,
            interval=args.interval,
            max_runtime=max_runtime
        )
        capture.run()
    except Exception as e:
        logger.error(f"Fatal error in main: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    main()
