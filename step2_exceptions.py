# step2_exceptions.py
import time
import re
import random
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
from config_utils import wait_element, wait_and_send_keys, wait_dom_ready, wait_and_click
from mail_handler_v2 import get_verify_code_v2

class InstagramExceptionStep:
    def __init__(self, driver):
        self.driver = driver

    # ==========================================
    # 1. HELPER: VALIDATE MASKED EMAIL
    # ==========================================
    def _check_mask_match(self, real_email, masked_hint):
        if not real_email or "@" not in real_email: return False
        try:
            real_user, real_domain = real_email.lower().strip().split("@")
            mask_user, mask_domain = masked_hint.lower().strip().split("@")
            
            if mask_domain[0] != '*' and mask_domain[0] != real_domain[0]: return False
            if "." in mask_domain:
                if mask_domain.split('.')[-1] != real_domain.split('.')[-1]: return False
            if mask_user[0] != '*' and mask_user[0] != real_user[0]: return False
            
            return True
        except: return False

    def _validate_masked_email_robust(self, primary_email, secondary_email=None):
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            match = re.search(r'\b([a-zA-Z0-9][\w\*]*@[\w\*]+\.[a-zA-Z\.]+)\b', body_text)
            if not match: return True 
            masked = match.group(1).lower().strip()
            print(f"   [2FA] Detected Hint: {masked}")
            
            is_primary = self._check_mask_match(primary_email, masked)
            is_secondary = secondary_email and self._check_mask_match(secondary_email, masked)
            
            if is_primary or is_secondary: return True
            print(f"   [CRITICAL] Hint {masked} mismatch with {primary_email} / {secondary_email}")
            return False
        except: return True

    # ==========================================
    # 2. MAIN ROUTING (HANDLE STATUS)
    # ==========================================
    def handle_status(self, status, ig_username, gmx_user, gmx_pass, linked_mail=None):
        print(f"   [Step 2] Processing status: {status}")

        success_statuses = [
            "LOGGED_IN_SUCCESS", "COOKIE_CONSENT", "TERMS_AGREEMENT", 
            "NEW_MESSAGING_TAB"
        ]
        if status in success_statuses:
            return status

        # XỬ LÝ BIRTHDAY
        if status == "BIRTHDAY_SCREEN":
            return self._handle_birthday_screen()

        # XỬ LÝ CHECKPOINT MAIL
        if status == "CHECKPOINT_MAIL":
            return self._solve_email_checkpoint(ig_username, gmx_user, gmx_pass, linked_mail)

        # NHÓM FAIL
        fail_statuses = [
            "UNUSUAL_LOGIN", "TRY_ANOTHER_DEVICE", "2FA_REQUIRED", "SUSPENDED",
            "LOGIN_FAILED_INCORRECT", "2FA_SMS", "2FA_WHATSAPP", "GET_HELP_LOG_IN",
            "2FA_APP", "2FA_APP_CONFIRM", "FAIL_LOGIN_REDIRECTED_TO_PROFILE_SELECTION",
            "LOGIN_FAILED_RETRY", "2FA_NOTIFICATIONS", "LOGGED_IN_UNKNOWN_STATE",
            "TIMEOUT_LOGIN_CHECK", "PAGE_BROKEN"
        ]

        if status in fail_statuses:
            raise Exception(f"STOP_FLOW_EXCEPTION: {status}")
        
        raise Exception(f"STOP_FLOW_UNKNOWN_STATUS: {status}")

    # ==========================================
    # 3. LOGIC XỬ LÝ BIRTHDAY (ĐÃ CẬP NHẬT)
    # ==========================================
    def _handle_birthday_screen(self):
        print("   [Step 2] Handling Birthday Screen...")
        try:
            # 1. Chọn Năm Sinh (1980 - 2007)
            # Tìm select box Year theo title hoặc selector chung
            year_select_el = wait_element(self.driver, By.CSS_SELECTOR, "select[title='Year:'], select[name='birthday_year']", timeout=5)
            if year_select_el:
                select = Select(year_select_el)
                random_year = str(random.randint(1980, 2007))
                select.select_by_value(random_year)
                print(f"   [Step 2] Selected Year: {random_year}")
            else:
                print("   [Step 2] Warning: Year select box not found.")

            # 2. Click Next
            print("   [Step 2] Clicking Next...")
            next_clicked = False
            # Quét nhiều loại nút Next để đảm bảo click trúng
            next_xpaths = [
                "//button[contains(text(), 'Next')]",
                "//div[contains(text(), 'Next') and @role='button']",
                "//button[contains(text(), 'Tiếp')]",
                "//div[contains(text(), 'Tiếp') and @role='button']"
            ]
            for xpath in next_xpaths:
                if wait_and_click(self.driver, By.XPATH, xpath, timeout=2):
                    next_clicked = True
                    break
            
            if not next_clicked:
                print("   [Step 2] Warning: Could not click Next button.")

            # 3. Handle Popup "Yes" (Xác nhận tuổi) - [CẬP NHẬT QUAN TRỌNG]
            print("   [Step 2] Waiting for confirmation popup...")
            time.sleep(2) # Chờ animation popup hiện ra
            
            yes_clicked = False
            # Quét các nút Yes/Có
            yes_xpaths = [
                "//button[contains(text(), 'Yes')]",
                "//div[contains(text(), 'Yes') and @role='button']",
                "//span[contains(text(), 'Yes')]", # Đôi khi là span
                "//button[contains(text(), 'Có')]",
                "//div[contains(text(), 'Có') and @role='button']"
            ]
            
            for xpath in yes_xpaths:
                if wait_and_click(self.driver, By.XPATH, xpath, timeout=3):
                    print("   [Step 2] Clicked 'Yes' confirmation.")
                    yes_clicked = True
                    break
            
            if not yes_clicked:
                print("   [Step 2] No confirmation popup found (Auto passed or skipped).")

            # 4. Wait & Re-check
            wait_dom_ready(self.driver, timeout=5)
            time.sleep(3)
            
            body = self.driver.find_element(By.TAG_NAME, "body").text.lower()
            if "allow the use of cookies" in body: return "COOKIE_CONSENT"
            if "posts" in body or "followers" in body: return "LOGGED_IN_SUCCESS"
            
            return "LOGGED_IN_SUCCESS"

        except Exception as e:
            # Nếu lỗi ở đoạn birthday thì log warning thôi, cố gắng chạy tiếp
            print(f"   [Step 2] Warning Birthday Handle: {str(e)}")
            return "LOGGED_IN_SUCCESS"

    # ==========================================
    # 4. LOGIC GIẢI CHECKPOINT (IMAP)
    # ==========================================
    def _solve_email_checkpoint(self, ig_username, gmx_user, gmx_pass, linked_mail=None):
        print(f"   [Step 2] Detected Email Checkpoint...")
        
        if not self._validate_masked_email_robust(gmx_user, linked_mail):
             raise Exception("STOP_FLOW_CHECKPOINT: Email hint mismatch")

        MAX_RETRIES = 2
        for attempt in range(1, MAX_RETRIES + 1):
            print(f"   [Step 2] >>> Code Attempt {attempt}/{MAX_RETRIES} <<<")
            
            if attempt > 1:
                resend_xpath = "//*[contains(text(), 'Get a new code') or contains(text(), 'Gửi mã mới')]"
                if wait_and_click(self.driver, By.XPATH, resend_xpath, timeout=3): 
                    print("   [Step 2] Requested new code. Waiting 1s...")
                    time.sleep(1)

            try:
                code = get_verify_code_v2(gmx_user, gmx_pass, ig_username)
            except Exception as e:
                if "GMX_LOGIN_FAIL" in str(e): raise e
                code = None
            
            if not code:
                if attempt < MAX_RETRIES: continue
                else: raise Exception("STOP_FLOW_CHECKPOINT: No code found in mail")

            print(f"   [Step 2] Inputting code {code}...")
            input_css = "#_r_7_, input[name='email'], input[name='security_code'], input[type='text']"
            code_input = wait_element(self.driver, By.CSS_SELECTOR, input_css, timeout=5)
            
            if code_input:
                try:
                    code_input.send_keys(Keys.CONTROL + "a"); code_input.send_keys(Keys.DELETE)
                    code_input.send_keys(code)
                    time.sleep(0.5)
                    code_input.send_keys(Keys.ENTER)
                except: 
                    wait_and_click(self.driver, By.XPATH, "//button[@type='submit']")
            else:
                raise Exception("STOP_FLOW_CHECKPOINT: Cannot find code input")

            print("   [Step 2] Verifying code...")
            check_result = self._check_verification_result()
            
            if check_result == "SUCCESS": 
                return "CHECKPOINT_SOLVED"
            elif check_result == "BIRTHDAY":
                return self._handle_birthday_screen()
            elif check_result == "WRONG_CODE":
                print(f"   [Step 2] Code {code} rejected.")
                if attempt < MAX_RETRIES: continue 
                else: raise Exception("STOP_FLOW_CHECKPOINT: All codes rejected.")
            elif check_result == "SUSPENDED": 
                raise Exception("STOP_FLOW_CHECKPOINT: Suspended after code")
            else:
                if attempt < MAX_RETRIES: continue
                raise Exception("STOP_FLOW_CHECKPOINT: Timeout verifying code")

    def _check_verification_result(self):
        end_time = time.time() + 15
        while time.time() < end_time:
            try:
                body = self.driver.find_element(By.TAG_NAME, "body").text.lower()
                if "select your birthday" in body or "add your birthday" in body: return "BIRTHDAY"
                if "allow the use of cookies" in body or "posts" in body or "save your login info" in body: return "SUCCESS"
                if "suspended" in body or "đình chỉ" in body: return "SUSPENDED"
                if "please check the security code" in body or "code isn't right" in body: return "WRONG_CODE"
            except: pass
            time.sleep(1)
        return "TIMEOUT"