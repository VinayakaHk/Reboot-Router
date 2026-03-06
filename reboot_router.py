"""
Router Reboot Automation Script

Automates logging into a router web interface using Selenium and OCR for captcha solving,
then reboots the router. Supports multiple platforms (macOS, Linux, Raspberry Pi).
"""

import time
import platform
import os
import json
import logging
from typing import Optional, Dict, Any

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException
import easyocr
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RouterRebooter:
    """Handles router login and reboot operations."""
    
    def __init__(self, config_path: str = "config.json"):
        """Initialize with configuration from file."""
        self.config = self._load_config(config_path)
        self.driver = None
        self.reader = None
        
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Config file {config_path} not found, using defaults")
            return self._default_config()
    
    def _default_config(self) -> Dict[str, Any]:
        """Return default configuration."""
        return {
            "router_url": "http://192.168.1.1",
            "username": "admin",
            "password": "admin",
            "max_retries": 10,
            "retry_delay": 10,
            "timeout": 10,
            "reboot_page": "/rebootinfo.cgi"
        }
    
    def _solve_captcha(self, captcha_url: str) -> Optional[str]:
        """Download and solve captcha using OCR."""
        temp_file = 'temp_captcha.jpg'
        try:
            response = requests.get(captcha_url, timeout=5)
            if response.status_code != 200:
                logger.error(f"Failed to download captcha: {response.status_code}")
                return None
                
            with open(temp_file, 'wb') as f:
                f.write(response.content)
            
            if not self.reader:
                self.reader = easyocr.Reader(['en'], verbose=False)
            
            results = self.reader.readtext(temp_file)
            
            if results:
                solution = results[0][1].strip()
                logger.info(f"Captcha solved: {solution}")
                return solution
            
            logger.warning("No text detected in captcha")
            return None
            
        except Exception as e:
            logger.error(f"Error solving captcha: {e}")
            return None
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)
    
    def _setup_driver(self):
        """Initialize Chrome driver with platform-specific settings."""
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        
        system = platform.system().lower()
        machine = platform.machine()
        
        # Determine platform key
        if system == "linux":
            platform_key = f"linux_{machine}"
        else:
            platform_key = system
        
        chrome_paths = self.config.get("chrome_paths", {})
        
        # Use regular Selenium for Raspberry Pi (more stable)
        if machine == "aarch64" and system == "linux":
            options = webdriver.ChromeOptions()
            options.binary_location = chrome_paths.get(platform_key, {}).get("binary", "/usr/bin/chromium-browser")
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-software-rasterizer")
            
            driver_path = chrome_paths.get(platform_key, {}).get("driver", "/usr/bin/chromedriver")
            service = Service(executable_path=driver_path)
            self.driver = webdriver.Chrome(service=service, options=options)
        else:
            # Use undetected-chromedriver for other platforms
            options = uc.ChromeOptions()
            if platform_key in chrome_paths:
                binary = chrome_paths[platform_key].get("binary")
                if binary:
                    options.binary_location = binary
            self.driver = uc.Chrome(options=options, use_subprocess=True)
        
        logger.info("Chrome driver initialized")
    
    def _login(self) -> bool:
        """Attempt to login to router. Returns True if successful."""
        wait = WebDriverWait(self.driver, self.config["timeout"])
        
        try:
            username_field = wait.until(EC.presence_of_element_located((By.ID, "username")))
            username_field.clear()
            username_field.send_keys(self.config["username"])
            logger.info("Username filled")
            
            password_field = self.driver.find_element(By.ID, "password")
            password_field.clear()
            password_field.send_keys(self.config["password"])
            logger.info("Password filled")
            
            captcha_img = self.driver.find_element(By.ID, "captchaimg")
            captcha_src = captcha_img.get_attribute("src")
            
            captcha_solution = self._solve_captcha(captcha_src)
            if not captcha_solution:
                logger.warning("Failed to solve captcha")
                return False
            
            captcha_field = self.driver.find_element(By.ID, "ValidateCode")
            captcha_field.clear()
            captcha_field.send_keys(captcha_solution)
            
            login_button = self.driver.find_element(By.ID, "loginbutton")
            login_button.click()
            logger.info("Login button clicked")
            
            time.sleep(3)
            
            # Check for errors
            try:
                error_msg = self.driver.find_element(By.ID, "errmsg")
                if error_msg.text.strip():
                    logger.error(f"Login error: {error_msg.text}")
                    return False
            except:
                pass
            
            # Check if redirected (successful login)
            current_url = self.driver.current_url
            if "content.asp" in current_url or current_url != self.config["router_url"]:
                logger.info("Login successful")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Login error: {e}")
            return False

    def _retrieve_cookies(self, driver):
        """Retrieve cookies from the current driver session."""
        cookies = driver.get_cookies()
        cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
        return cookie_dict

    def _send_curl_request(self, cookies):
        try: 
            eboovalue = '9b490b66'
            ecnttoken = cookies["ecntToken"]
            if eboovalue and ecnttoken:
                curl_command = f"""curl 'http://192.168.1.1/cgi-bin/mag-reset.asp' \
    -X POST \
    -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:145.0) Gecko/20100101 Firefox/145.0' \
    -H 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8' \
    -H 'Accept-Language: en-US,en;q=0.5' \
    -H 'Accept-Encoding: gzip, deflate' \
    -H 'Content-Type: application/x-www-form-urlencoded' \
    -H 'Origin: http://192.168.1.1' \
    -H 'DNT: 1' \
    -H 'Sec-GPC: 1' \
    -H 'Connection: keep-alive' \
    -H 'Referer: http://192.168.1.1/cgi-bin/mag-reset.asp' \
    -H 'Cookie: EBOOVALUE={eboovalue}; ecntToken={ecnttoken}' \
    -H 'Upgrade-Insecure-Requests: 1' \
    -H 'Priority: u=4' \
    -H 'Pragma: no-cache' \
    -H 'Cache-Control: no-cache' \
    --data-raw 'rebootflag=1&restoreFlag=1&isCUCSupport=0'
    """
                os.system(curl_command)
            else:
                print("Required cookies missing; cannot send curl request")
        except Exception as e:
            print(f"Error sending curl request: {e}")
            
    def _reboot(self) -> bool:
        """Navigate to reboot page and trigger reboot."""
        try:
            cookies = self._retrieve_cookies(self.driver)
            print("cookies", cookies)
            self._send_curl_request(cookies)            
            return True
            
        except Exception as e:
            logger.error(f"Reboot error: {e}")
            return False
    
    def run(self) -> str:
        """Main execution: login and reboot router."""
        try:
            # No need for virtual display when using headless mode
            for attempt in range(1, self.config["max_retries"] + 1):
                logger.info(f"Attempt {attempt}/{self.config['max_retries']}")
                
                try:
                    self._setup_driver()
                    self.driver.get(self.config["router_url"])
                    
                    if self._login():
                        if self._reboot():
                            return "Router reboot initiated successfully"
                        else:
                            return "Login successful but reboot failed"
                    
                    logger.warning(f"Attempt {attempt} failed, retrying...")
                    
                except (WebDriverException, TimeoutException) as e:
                    logger.error(f"Driver error: {e}")
                except Exception as e:
                    logger.error(f"Unexpected error: {e}")
                finally:
                    if self.driver:
                        self.driver.quit()
                        self.driver = None
                
                if attempt < self.config["max_retries"]:
                    time.sleep(self.config["retry_delay"])
            
            return "Failed to reboot router after all retries"
            
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            return f"Error: {str(e)}"
        finally:
            if self.driver:
                self.driver.quit()

def main():
    """Entry point for the script."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Automate router login and reboot")
    parser.add_argument("--config", default="config.json", help="Path to config file")
    parser.add_argument("--login-only", action="store_true", help="Only login, don't reboot")
    args = parser.parse_args()
    
    rebooter = RouterRebooter(config_path=args.config)
    
    if args.login_only:
        logger.info("Login-only mode")
        # Modify to skip reboot
        original_reboot = rebooter._reboot
        rebooter._reboot = lambda: True
    
    result = rebooter.run()
    logger.info(f"Final result: {result}")
    return result

if __name__ == "__main__":
    main()