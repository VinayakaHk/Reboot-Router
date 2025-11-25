import time
import platform
import re
import os

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException

import easyocr
import requests
from PIL import Image
from io import BytesIO

from pyvirtualdisplay import Display

MAX_RETRIES = 10
RETRY_DELAY = 10

def solve_captcha(captcha_url):
    """Download and solve the captcha using easyocr"""
    try:
        response = requests.get(captcha_url)
        if response.status_code == 200:
            with open('temp_captcha.jpg', 'wb') as f:
                f.write(response.content)            
            reader = easyocr.Reader(['en'])
            results = reader.readtext('temp_captcha.jpg')
            os.remove('temp_captcha.jpg')
            
            if results:
                return results[0][1].strip()
            else:
                return None
    except Exception as e:
        print(f"Error solving captcha: {e}")
        return None

def setup_driver():
    """Initialize and configure the Chrome driver."""
    options = uc.ChromeOptions()
    if platform.system() == "Darwin": 
        options.binary_location = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
        driver = uc.Chrome(options=options)
    elif platform.system() == "Linux":
        options.binary_location = "/usr/bin/chromium-browser"
        chrome_driver_path = "/usr/bin/chromedriver"
        driver = uc.Chrome(options=options, driver_executable_path=chrome_driver_path)
    else:
        driver = uc.Chrome(options=options)
    return driver

def setup_display():
    """Initialize virtual display for headless Linux environments."""
    if platform.machine() == "aarch64" and platform.system() == "Linux":
        display = Display(visible=False, size=(800, 600))
        display.start()
        return display
    return None

def fill_login_credentials(driver, wait):
    time.sleep(1)
    """Fill username and password fields."""
    username_field = wait.until(
        EC.presence_of_element_located((By.ID, "username"))
    )
    username_field.clear()
    username_field.send_keys("admin")
    print("Username filled")
    time.sleep(1)
    password_field = wait.until(
        EC.presence_of_element_located((By.ID, "password"))
    )
    password_field.clear()
    password_field.send_keys("admin")
    print("Password filled")

def handle_captcha(driver):
    """Get captcha image, solve it, and fill the captcha field."""
    captcha_img = driver.find_element(By.ID, "captchaimg")
    captcha_src = captcha_img.get_attribute("src")
    print(f"Captcha URL: {captcha_src}")
    
    captcha_solution = solve_captcha(captcha_src)
    captcha_solution_sanitized = captcha_solution.replace(" ", "").lower()
    if captcha_solution:
        print(f"Captcha solved: {captcha_solution_sanitized}")
        captcha_field = driver.find_element(By.ID, "ValidateCode")
        captcha_field.clear()
        captcha_field.send_keys(captcha_solution_sanitized)
        print("Captcha filled")
        return True
    else:
        print("Failed to solve captcha")
        return False

def click_login_button(driver):
    """Click the login button."""
    login_button = driver.find_element(By.ID, "loginbutton")
    login_button.click()
    print("Login button clicked")

def handle_login_error(driver, error_msg):
    """Handle login errors and determine if we should retry."""
    if "ValidateCode Error" in error_msg:
        print(f"Login error: {error_msg}")
        try:
            refresh_button = driver.find_element(By.ID, "Refresh")
            refresh_button.click()
            time.sleep(2)
        except Exception:
            pass
        return True  # Signal to retry
    return False

def verify_login_success(driver):
    """Verify if login was successful by checking post-login menu and URL."""
    current_url = driver.current_url
    print("current_url", current_url)
    if "content.asp" in current_url:
        print("Login successful - redirected and menu found")
        return True
    
    return False

def process_login_result(driver):
    """Check login result and handle errors."""
    time.sleep(3)
    
    try:
        error_msg = driver.find_element(By.ID, "errmsg")
        if error_msg.text.strip():
            return handle_login_error(driver, error_msg.text)
    except Exception:
        pass
    
    if verify_login_success(driver):
        return "success"
    else:
        print("Post-login verification failed, retrying")
        try:
            driver.refresh()
        except Exception:
            pass
        time.sleep(3)
        return "retry"

def perform_login_attempt(driver, wait):
    """Perform a single login attempt."""
    try:
        driver.get("http://192.168.1.1")
        print('Driver loaded successfully')
        
        fill_login_credentials(driver, wait)
        
        if not handle_captcha(driver):
            print("Failed to handle captcha")
            return "retry"
        
        click_login_button(driver)
        result = process_login_result(driver)
        
        return result
        
    except (WebDriverException, TimeoutException) as e:
        print(f"Error encountered: {str(e)}")
        time.sleep(RETRY_DELAY)
        return "retry"
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        time.sleep(RETRY_DELAY)
        return "retry"

def retrieve_cookies(driver):
    """Retrieve cookies from the current driver session."""
    cookies = driver.get_cookies()
    cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
    return cookie_dict

def send_curl_request(cookies):
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
        
def reboot_router():
    answer = ''
    driver = None
    display = None
    
    try:
        display = setup_display()
        
        for i in range(MAX_RETRIES):
            print(f'Attempt {i+1}')
            try:
                driver = setup_driver()
                wait = WebDriverWait(driver, 10)
                result = perform_login_attempt(driver, wait)
                if result == "success":
                    answer = "Login successful"
                    cookies = retrieve_cookies(driver)
                    print("cookies", cookies)
                    send_curl_request(cookies)
                    break
                elif result == "retry":
                    continue
                time.sleep(2)
            except Exception as e:
                print(f"Attempt exception: {e}")
            finally:
                if driver:
                    driver.quit()
                    driver = None
                
        if not answer:
            answer = "Login failed after all retries"
            
    except Exception as e:
        print(f"Main exception: {e}")
        answer = f"Error: {str(e)}"
    finally:
        if display:
            display.stop()
            
    return answer

if __name__ == "__main__":
    result = reboot_router()
    print(f"Final result: {result}")

