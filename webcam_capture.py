#!/usr/bin/env python3
"""
Webcam Snapshot Capture Script
Captures snapshots from a live webcam at specified intervals
"""

import os
import argparse
import time
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
import shutil
import traceback
import sys


# Configure logging
log_file = "webcam_capture.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class WebcamCapture:
    def __init__(self, url, output_dir="images", interval=5, max_runtime=None):
        """Initialize webcam capture with a single URL"""
        self.url = url
        self.output_dir = output_dir
        self.interval = interval
        self.max_runtime = max_runtime
        self.driver = None
        self.session_id = None
        
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
        chrome_options.add_argument("--window-size=800,600")  # Tiny window for less memory
        chrome_options.add_argument("--hide-scrollbars")
        chrome_options.add_argument("--mute-audio")
        chrome_options.add_argument("--autoplay-policy=no-user-gesture-required")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--single-process")  # Less memory but less stable
        chrome_options.add_argument("--disable-application-cache")
        chrome_options.add_argument("--disable-features=site-per-process")  # Less memory
        chrome_options.add_argument("--js-flags=--max-old-space-size=128")  # Limit JS memory
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
            logger.info(f"Using browser binary: {chrome_bin}")

        # Find chromedriver
        driver_path = os.environ.get("CHROMEDRIVER") or shutil.which("chromedriver") or "/usr/bin/chromedriver"
        if not os.path.exists(driver_path):
            error_msg = "chromedriver not found. Install with: sudo apt install -y chromium-driver"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        try:
            # Initialize driver
            service = Service(driver_path)
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.set_page_load_timeout(120)
            self.driver.set_script_timeout(120)
            self.session_id = self.driver.session_id
            logger.info(f"Chrome driver initialized successfully (session: {self.session_id})")
        except Exception as e:
            logger.error(f"Failed to initialize driver: {e}")
            raise
            
    def is_driver_alive(self):
        """Check if the driver session is still valid"""
        if not self.driver:
            return False
        try:
            # Simple command to check if session is alive
            self.driver.current_url
            return True
        except Exception:
            return False

    def restart_driver_if_needed(self):
        """Restart the driver if it's dead"""
        if not self.is_driver_alive():
            logger.warning("Browser session died, restarting...")
            try:
                if self.driver:
                    try:
                        self.driver.quit()
                    except Exception:
                        pass
                self.setup_driver()
                logger.info(f"Loading webcam URL: {self.url}")
                self.driver.get(self.url)
                self.wait_for_page_load()
                return True
            except Exception as e:
                logger.error(f"Failed to restart driver: {e}")
                return False
        return False

    def capture_snapshot(self):
        """Capture a snapshot with retries and auto-restart"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"webcam_snapshot_{timestamp}.png"
        filepath = os.path.join(self.output_dir, filename)

        # Try up to 3 times
        for attempt in range(1, 4):
            try:
                # Check if driver needs restart
                if not self.is_driver_alive():
                    if not self.restart_driver_if_needed():
                        logger.error("Failed to restart browser, skipping this capture")
                        return None
                
                # Try element screenshot first (more reliable)
                elems = self.driver.find_elements(By.TAG_NAME, "video") or \
                        self.driver.find_elements(By.TAG_NAME, "canvas")
                if elems:
                    elems[0].screenshot(filepath)
                else:
                    self.driver.save_screenshot(filepath)
                logger.info(f"Snapshot saved: {filename}")
                return filepath
            except Exception as e:
                logger.error(f"Error on attempt {attempt}/3: {e}")
                if attempt == 3:
                    # On last attempt, try restarting the browser
                    self.restart_driver_if_needed()
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
            try:
                WebDriverWait(self.driver, 30).until(
                    lambda d: d.find_elements(By.TAG_NAME, "video") or d.find_elements(By.TAG_NAME, "canvas")
                )
                logger.info("Found video/canvas element")
            except Exception as e:
                logger.warning(f"No video/canvas found, will try screenshot anyway: {e}")
            
            time.sleep(3)  # Small buffer
            logger.info("Page loaded successfully")
        except Exception as e:
            logger.warning(f"Page load issue: {e}")
            
    def run(self):
        """Run the capture process with auto-restart capability"""
        start_time = time.time()
        capture_count = 0
        last_restart = 0
        restart_count = 0
        
        try:
            # Setup and navigate
            self.setup_driver()
            logger.info(f"Loading webcam URL: {self.url}")
            self.driver.get(self.url)
            self.wait_for_page_load()
            
            # Show info
            logger.info(f"Capturing every {self.interval} seconds")
            if self.max_runtime:
                logger.info(f"Will run for {self.max_runtime} seconds")
            else:
                logger.info("Press Ctrl+C to stop")
            logger.info(f"Saving to: {os.path.abspath(self.output_dir)}")
            logger.info(f"Logging to: {os.path.abspath(log_file)}")
            
            # Main loop
            while True:
                # Check max runtime
                if self.max_runtime and (time.time() - start_time) >= self.max_runtime:
                    logger.info(f"Maximum runtime reached. Captured {capture_count} images.")
                    break
                
                # Check if browser needs restart (periodic restart every 12 hours)
                current_time = time.time()
                if current_time - last_restart > 43200:  # 12 hours in seconds
                    logger.info("Performing scheduled browser restart")
                    self.restart_driver_if_needed()
                    last_restart = current_time
                    restart_count += 1
                
                # Take snapshot
                if self.capture_snapshot():
                    capture_count += 1
                    if self.max_runtime:
                        remaining = max(0, self.max_runtime - (time.time() - start_time))
                        logger.info(f"Captures: {capture_count} | Remaining: {remaining:.0f}s | Restarts: {restart_count}")
                    else:
                        logger.info(f"Captures: {capture_count} | Restarts: {restart_count}")
                else:
                    logger.warning("Failed to capture snapshot")
                
                # Wait for next interval
                time.sleep(self.interval)
                
        except KeyboardInterrupt:
            elapsed = time.time() - start_time if 'start_time' in locals() else 0
            logger.info(f"Stopped after {elapsed:.0f}s with {capture_count if 'capture_count' in locals() else 0} captures")
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            logger.error(traceback.format_exc())
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                    logger.info("Browser closed")
                except Exception as e:
                    logger.error(f"Error closing browser: {e}")


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
        "--output-dir", type=str, default=None,
        help="Directory to save images (default: images/{url})"
    )
    parser.add_argument(
        "--log-file", type=str, default="webcam_capture.log",
        help="Log file path (default: webcam_capture.log)"
    )
    args = parser.parse_args()
    if args.output_dir is None:
        args.output_dir = f"images/{args.url}"

    # Configure logging
    global log_file
    log_file = args.log_file
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

    # Handle max_runtime=0 meaning run indefinitely
    max_runtime = args.max_runtime if args.max_runtime > 0 else None

    logger.info(f"Starting webcam capture for {args.url}")
    logger.info(f"Python version: {sys.version}")
    
    try:
        # Create and run the capture
        capture = WebcamCapture(
            url=args.url,
            output_dir=args.output_dir,
            interval=args.interval,
            max_runtime=max_runtime
        )
        capture.run()
    except Exception as e:
        logger.error(f"Fatal error in main: {e}")
        logger.error(traceback.format_exc())
        return 1
    
    return 0


if __name__ == "__main__":
    main()
