#!/usr/bin/env python3
"""
Webcam Snapshot Capture Script
Captures snapshots from a live webcam at specified intervals
"""

import os
import argparse
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
import shutil


class WebcamCapture:
    def __init__(self, url, output_dir="images", interval=5, max_runtime=None):
        """Initialize webcam capture with a single URL"""
        self.url = url
        self.output_dir = output_dir
        self.interval = interval
        self.max_runtime = max_runtime
        self.driver = None
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)

    def setup_driver(self):
        """Setup Chrome/Chromium driver using system binaries"""
        chrome_options = Options()
        # Headless mode with performance settings for small VMs
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--hide-scrollbars")
        chrome_options.add_argument("--mute-audio")
        chrome_options.add_argument("--autoplay-policy=no-user-gesture-required")
        chrome_options.page_load_strategy = "none"

        # Find Chrome/Chromium binary
        chrome_bin = os.environ.get("CHROME_BIN")
        if not chrome_bin:
            for candidate in (
                shutil.which("chromium-browser"),
                shutil.which("chromium"),
                shutil.which("google-chrome"),
                "/usr/bin/chromium-browser",
                "/usr/bin/chromium",
                "/usr/bin/google-chrome",
            ):
                if candidate and os.path.exists(candidate):
                    chrome_bin = candidate
                    break
        if chrome_bin:
            chrome_options.binary_location = chrome_bin

        # Find chromedriver
        driver_path = os.environ.get("CHROMEDRIVER") or shutil.which("chromedriver") or "/usr/bin/chromedriver"
        if not os.path.exists(driver_path):
            raise RuntimeError("chromedriver not found. Install with: sudo apt install -y chromium-driver")

        # Initialize driver
        service = Service(driver_path)
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.set_page_load_timeout(120)
        self.driver.set_script_timeout(120)
        print("Chrome driver initialized successfully")
            
    def capture_snapshot(self):
        """Capture a snapshot with retries"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"webcam_snapshot_{timestamp}.png"
        filepath = os.path.join(self.output_dir, filename)

        # Try up to 3 times
        for attempt in range(1, 4):
            try:
                # Try element screenshot first (more reliable)
                elems = self.driver.find_elements(By.TAG_NAME, "video") or \
                        self.driver.find_elements(By.TAG_NAME, "canvas")
                if elems:
                    elems[0].screenshot(filepath)
                else:
                    self.driver.save_screenshot(filepath)
                print(f"Snapshot saved: {filename}")
                return filepath
            except Exception as e:
                print(f"Error on attempt {attempt}/3: {e}")
                time.sleep(2)
        return None
            
    def wait_for_page_load(self):
        """Wait for page to load and video/canvas to appear"""
        try:
            # Wait for document ready state
            WebDriverWait(self.driver, 60).until(
                lambda d: d.execute_script("return document.readyState") in ("interactive", "complete")
            )
            # Wait for video/canvas (best effort)
            WebDriverWait(self.driver, 30).until(
                lambda d: d.find_elements(By.TAG_NAME, "video") or d.find_elements(By.TAG_NAME, "canvas")
            )
            time.sleep(3)  # Small buffer
            print("Page loaded successfully")
        except Exception as e:
            print(f"Warning: Page load issue: {e}")
            
    def run(self):
        """Run the capture process"""
        try:
            # Setup and navigate
            self.setup_driver()
            print(f"Loading webcam URL: {self.url}")
            self.driver.get(self.url)
            self.wait_for_page_load()
            
            # Start capturing
            start_time = time.time()
            capture_count = 0
            
            # Show info
            print(f"Capturing every {self.interval} seconds")
            if self.max_runtime:
                print(f"Will run for {self.max_runtime} seconds")
            else:
                print("Press Ctrl+C to stop")
            print(f"Saving to: {os.path.abspath(self.output_dir)}")
            
            # Main loop
            while True:
                # Check max runtime
                if self.max_runtime and (time.time() - start_time) >= self.max_runtime:
                    print(f"\nMaximum runtime reached. Captured {capture_count} images.")
                    break
                
                # Take snapshot
                if self.capture_snapshot():
                    capture_count += 1
                    if self.max_runtime:
                        remaining = max(0, self.max_runtime - (time.time() - start_time))
                        print(f"Captures: {capture_count} | Remaining: {remaining:.0f}s")
                
                # Wait for next interval
                time.sleep(self.interval)
                
        except KeyboardInterrupt:
            elapsed = time.time() - start_time if 'start_time' in locals() else 0
            print(f"\nStopped after {elapsed:.0f}s with {capture_count if 'capture_count' in locals() else 0} captures")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            if self.driver:
                self.driver.quit()
                print("Browser closed")


def main():
    """Parse arguments and start capture"""
    parser = argparse.ArgumentParser(description="Webcam snapshot capture")
    parser.add_argument(
        "--url", type=str,
        default="https://share.earthcam.net/tJ90CoLmq7TzrY396Yd88M3ySv9LnAn8E0UsZn2nKhs!/hilton_waikiki_beach/camera/live",
        help="URL of the webcam to capture"
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
        "--output-dir", type=str, default="images",
        help="Directory to save images (default: images)"
    )
    args = parser.parse_args()

    # Handle max_runtime=0 meaning run indefinitely
    max_runtime = args.max_runtime if args.max_runtime > 0 else None

    # Create and run the capture
    capture = WebcamCapture(
        url=args.url,
        output_dir=args.output_dir,
        interval=args.interval,
        max_runtime=max_runtime
    )
    capture.run()


if __name__ == "__main__":
    main()
