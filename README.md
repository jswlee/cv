# Webcam Snapshot Capture

A Python script to automatically capture snapshots from a live webcam at regular intervals.

## Features

- Capture from multiple webcam URLs in one run
- Interleaved, round-robin snapshots across URLs (url1 shot1, url2 shot1, ...)
- Saves images with timestamp filenames
- Configurable capture intervals (default: 5 seconds)
- Optional max runtime to stop automatically
- Per-URL subdirectories under `images/`
- Automatic directory creation
- Headless browser operation

## Requirements

- Python 3.6+
- Chrome browser installed
- Internet connection

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

Optional (recommended) virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Usage

Run the script (uses the URLs defined in `webcam_capture.py`):

```bash
python3 webcam_capture.py
```

The script will:
- Prepare each URL once, then alternate snapshots across them
- Create an `images/` directory (and per-URL subfolders) if it doesn't exist
- Start capturing snapshots every 5 seconds (default)
- Save images with timestamp filenames like `webcam_snapshot_20230830_143052.png`
- Stop automatically after a configured max runtime or continue until you press Ctrl+C

## Configuration

Edit `webcam_capture.py`:

- URLs list in `main()` (or `run_interleaved()`):
  ```python
  urls = [
      "https://share.earthcam.net/.../live",
      "https://embed.cdn-surfline.com/cams/...",
  ]
  ```
- Interleaved settings in `main()`:
  ```python
  interval = 5      # seconds between any two consecutive snapshots overall
  max_runtime = 30  # total seconds for the whole run across all URLs
  ```
- Output base directory (default: `images/`). Per-URL subfolders are auto-named from the URL.

## Output

Images are saved in the `images/` directory with filenames formatted as:
`webcam_snapshot_YYYYMMDD_HHMMSS.png`

With multiple URLs, images are organized per URL:
```
images/
  share.earthcam.net_tJ90..._h/
    webcam_snapshot_2025....png
  embed.cdn-surfline.com_cams_6328.../
    webcam_snapshot_2025....png
```

## Stopping the Script

There are two ways:

- Automatic: Set `max_runtime` (in seconds) and the script stops on its own.
- Manual: Press `Ctrl+C` to stop gracefully.

## Troubleshooting

- Ensure Chrome browser is installed on your system
- Check your internet connection
- The script will automatically download the appropriate ChromeDriver
