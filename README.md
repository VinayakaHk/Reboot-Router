# Router Reboot Utility

Small utility to log into a local router web UI, solve its captcha, and trigger a reboot via a POST request.

- Main implementation: [reboot_router.py](reboot_router.py)
- Entry point / primary function: [`reboot_router`](reboot_router.py)

## What it does
1. Starts a (virtual) display on some headless Linux systems ([`setup_display`](reboot_router.py)).
2. Launches an undetected Chrome driver ([`setup_driver`](reboot_router.py)).
3. Loads the router login page and fills credentials (username/password are hardcoded as `admin` in [`fill_login_credentials`](reboot_router.py)).
4. Downloads and OCRs the captcha using EasyOCR ([`solve_captcha`](reboot_router.py) and [`handle_captcha`](reboot_router.py)).
5. Submits the login form and verifies success ([`perform_login_attempt`](reboot_router.py), [`process_login_result`](reboot_router.py), [`verify_login_success`](reboot_router.py)).
6. If login succeeds, retrieves cookies ([`retrieve_cookies`](reboot_router.py)) and issues the reboot POST via a curl command ([`send_curl_request`](reboot_router.py)).

Run as a script: the file calls [`reboot_router`](reboot_router.py) when executed directly.

## Requirements
See [requirements.txt](requirements.txt) for required packages (examples include undetected-chromedriver, selenium, easyocr, pyvirtualdisplay, pillow, requests).

## Usage
Run from the project root:

```sh
python reboot_router.py
