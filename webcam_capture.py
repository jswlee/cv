#!/usr/bin/env python3
"""
Webcam Snapshot Capture Script
Captures snapshots from a live webcam at 5-second intervals
"""

import os
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import urlparse
import re


class WebcamCapture:
    def __init__(self, url, output_dir="images", interval=5, max_runtime=None):
        """
        Initialize the webcam capture
        
        Args:
            url (str): The webcam URL
            output_dir (str): Directory to save images
            interval (int): Capture interval in seconds
            max_runtime (int, optional): Maximum runtime in seconds. If None, runs indefinitely
        """
        self.url = url
        self.output_dir = output_dir
        self.interval = interval
        self.max_runtime = max_runtime
        self.driver = None
        self.start_time = None
        
        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)

    def setup_driver(self):
        """Setup Chrome driver with appropriate options"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run in background
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-plugins")
        
        try:
            # Automatically download and setup ChromeDriver
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            print("Chrome driver initialized successfully")
        except Exception as e:
            print(f"Error initializing Chrome driver: {e}")
            print("Make sure Chrome browser is installed on your system")
            raise
            
    def capture_snapshot(self):
        """Capture a single snapshot"""
        try:
            # Generate timestamp for filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"webcam_snapshot_{timestamp}.png"
            filepath = os.path.join(self.output_dir, filename)
            
            # Take screenshot
            self.driver.save_screenshot(filepath)
            print(f"Snapshot saved: {filename}")
            return filepath
            
        except Exception as e:
            print(f"Error capturing snapshot: {e}")
            return None
            
    def wait_for_page_load(self, timeout=30):
        """Wait for the webcam page to load"""
        try:
            # Wait for the page to load and any video/canvas elements to appear
            WebDriverWait(self.driver, timeout).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            
            # Give extra time for the webcam stream to load
            time.sleep(15)
            print("Page loaded successfully")
            
        except Exception as e:
            print(f"Warning: Page load timeout or error: {e}")
            print("Proceeding anyway...")
            
    def start_capture(self):
        """Start the continuous capture process"""
        try:
            self.setup_driver()
            
            print(f"Loading webcam URL: {self.url}")
            self.driver.get(self.url)
            
            self.wait_for_page_load()
            
            # Record start time for runtime tracking
            self.start_time = time.time()
            
            if self.max_runtime:
                print(f"Starting capture every {self.interval} seconds for maximum {self.max_runtime} seconds...")
                print(f"Images will be saved to: {os.path.abspath(self.output_dir)}")
                print("Script will stop automatically after the specified time")
            else:
                print(f"Starting capture every {self.interval} seconds (indefinite)...")
                print(f"Images will be saved to: {os.path.abspath(self.output_dir)}")
                print("Press Ctrl+C to stop")
            
            capture_count = 0
            while True:
                # Check if we've exceeded the maximum runtime
                if self.max_runtime:
                    elapsed_time = time.time() - self.start_time
                    if elapsed_time >= self.max_runtime:
                        print(f"\nMaximum runtime of {self.max_runtime} seconds reached.")
                        print(f"Total captures: {capture_count}")
                        break
                
                filepath = self.capture_snapshot()
                if filepath:
                    capture_count += 1
                    if self.max_runtime:
                        elapsed_time = time.time() - self.start_time
                        remaining_time = max(0, self.max_runtime - elapsed_time)
                        print(f"Total captures: {capture_count} | Time remaining: {remaining_time:.0f}s")
                    else:
                        print(f"Total captures: {capture_count}")
                
                time.sleep(self.interval)
                
        except KeyboardInterrupt:
            if self.max_runtime:
                elapsed_time = time.time() - self.start_time
                print(f"\nCapture stopped by user after {elapsed_time:.0f} seconds. Total captures: {capture_count}")
            else:
                print(f"\nCapture stopped by user. Total captures: {capture_count}")
        except Exception as e:
            print(f"Error during capture: {e}")
        finally:
            self.cleanup()
            
    def cleanup(self):
        """Clean up resources"""
        if self.driver:
            self.driver.quit()
            print("Browser closed")


def safe_dirname(url: str) -> str:
    """Create a filesystem-safe directory name from a URL."""
    parsed = urlparse(url)
    # Combine netloc and path, replace non-safe chars with underscores
    raw = f"{parsed.netloc}{parsed.path}".strip("/") or parsed.netloc or "source"
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", raw)
    # Limit length to avoid extremely long folder names
    return name[:64] if name else "source"

def run_interleaved(urls, interval=5, max_runtime=None):
    """Alternate snapshots across multiple URLs in a round-robin manner.

    Args:
        urls (list[str]): List of webcam page URLs to capture from.
        interval (int): Seconds to wait between consecutive snapshots (overall).
        max_runtime (int|None): Total seconds to run. If None, runs until Ctrl+C.
    """
    captures = []
    try:
        # Prepare a capture instance per URL and open pages
        for u in urls:
            out_dir = os.path.join("images", safe_dirname(u))
            print(f"\n=== Preparing URL: {u} ===")
            print(f"Saving to directory: {out_dir}")
            cap = WebcamCapture(url=u, output_dir=out_dir)
            cap.setup_driver()
            cap.driver.get(u)
            cap.wait_for_page_load()
            captures.append(cap)

        start_time = time.time()
        counts = [0] * len(captures)
        print(
            f"Starting interleaved capture across {len(captures)} URL(s) with {interval}s between snapshots"
        )
        if max_runtime:
            print(f"Total maximum runtime: {max_runtime} seconds")
        else:
            print("Press Ctrl+C to stop")

        # Round-robin loop
        while True:
            # Stop check (time-based)
            if max_runtime and (time.time() - start_time) >= max_runtime:
                print("\nMaximum total runtime reached. Stopping.")
                break

            for i, cap in enumerate(captures):
                # Check again before each shot to avoid overshooting
                if max_runtime and (time.time() - start_time) >= max_runtime:
                    break
                filepath = cap.capture_snapshot()
                if filepath:
                    counts[i] += 1
                    print(
                        f"URL {i+1}/{len(captures)} snapshot {counts[i]} saved."
                    )
                time.sleep(interval)

    except KeyboardInterrupt:
        elapsed = time.time() - start_time if 'start_time' in locals() else 0
        print(f"\nCapture stopped by user after {elapsed:.0f} seconds.")
        if 'counts' in locals():
            for i, c in enumerate(counts):
                print(f"URL {i+1}: {c} snapshots")
    finally:
        # Cleanup all drivers
        for cap in captures:
            cap.cleanup()

def main():
    """Main function"""
    # Webcam URLs to interleave
    urls = [
        "https://share.earthcam.net/tJ90CoLmq7TzrY396Yd88M3ySv9LnAn8E0UsZn2nKhs!/hilton_waikiki_beach/camera/live",
        "https://embed.cdn-surfline.com/cams/6328c8d46a2a105e18365162/2a22d923244e8a4160f57feff3b47e1f8f5d0abc",
    ]

    # Interleave settings
    interval = 5      # seconds between each snapshot (overall)
    max_runtime = 30  # total seconds for the whole run (covering all URLs)

    run_interleaved(urls, interval=interval, max_runtime=max_runtime)


if __name__ == "__main__":
    main()
