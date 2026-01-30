# step2_exceptions.py
import time
import re
import random
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
# Import ActionChains for advanced interactions
from selenium.webdriver import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Import các hàm utils
from config_utils import wait_element, wait_and_send_keys, wait_dom_ready, wait_and_click
from mail_handler_v2 import get_verify_code_v2
from step1_login import InstagramLoginStep as step1_login

class InstagramExceptionStep:
    def __init__(self, driver):
        self.driver = driver
        # Callback for password change, can be set externally
        self.on_password_changed = self._default_on_password_changed

    def _default_on_password_changed(self, username, new_password):
        # Default: do nothing. GUI or caller can override this.
        pass

    # ==========================================
    # 1. HELPER: VALIDATE MASKED EMAIL
    # ==========================================
    def _is_driver_alive(self):
        try:
            # Gửi lệnh nhẹ để check kết nối (lấy title hoặc url)
            _ = self.driver.current_url
            return True
        except:
            return False
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
            # [RETRY] Thử lấy body text 2 lần phòng trường hợp chưa load xong
            body_text = ""
            for _ in range(2):  # Reduced from 3 to 2 attempts
                try:
                    body_text = self.driver.find_element(By.TAG_NAME, "body").text
                    if "@" in body_text: break
                except: time.sleep(0.5)  # Reduced from 1s
            
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
    def _handle_require_password_change(self, new_password):
        # Timeout protection for password change (max 60s)
        start_time = time.time()
        TIMEOUT = 60
        print(f"   [Step 2] Handling Require Password Change (New password: {new_password})...")
        try:
            # Tìm chính xác 2 input theo id
            new_pass_input = self.driver.find_element(By.ID, "new_password1")
            confirm_pass_input = self.driver.find_element(By.ID, "new_password2")
            
            # Nhập password vào cả 2 ô với delay để chính xác
            self._fill_input_with_delay(new_pass_input, new_password)
            self._fill_input_with_delay(confirm_pass_input, new_password)

            # Nhấn nút Next (retry nhiều selector)
            next_clicked = False
            next_selectors = [
                (By.XPATH, "//button[contains(text(), 'Next')]") ,
                (By.CSS_SELECTOR, "div[role='button'][tabindex='0']"),
                (By.CSS_SELECTOR, "div.x1i10hfl.xjqpnuy.xc5r6h4.xqeqjp1.x1phubyo.x972fbf.x10w94by.x1qhh985.x14e42zd.xdl72j9.x2lah0s.x3ct3a4.xdj266r.x14z9mp.xat24cr.x1lziwak.x2lwn1j.xeuugli.xexx8yu.x18d9i69.x1hl2dhg.xggy1nq.x1ja2u2z.x1t137rt.x1q0g3np.x1lku1pv.x1a2a7pz.x6s0dn4.xjyslct.x1obq294.x5a5i1n.xde0f50.x15x8krk.x1ejq31n.x18oe1m7.x1sy0etr.xstzfhl.x9f619.x9bdzbf.x1ypdohk.x1f6kntn.xwhw2v2.x10w6t97.xl56j7k.x17ydfre.xf7dkkf.xv54qhq.x1n2onr6.x2b8uid.xlyipyv.x87ps6o.x5c86q.x18br7mf.x1i0vuye.xh8yej3.x18cabeq.x158me93.xk4oym4.x1uugd1q.x3nfvp2")
            ]
            for by, sel in next_selectors:
                try:
                    next_btns = self.driver.find_elements(by, sel)
                    for btn in next_btns:
                        if btn.is_displayed():
                            btn.click()
                            print(f"   [Step 2] Clicked Next after password change via selector: {sel}")
                            next_clicked = True
                            break
                    if next_clicked:
                        break
                except Exception as e:
                    print(f"   [Step 2] Error finding Next button via selector: {sel} - {e}")
                if time.time() - start_time > TIMEOUT:
                    raise Exception("TIMEOUT_REQUIRE_PASSWORD_CHANGE: Next button find")
            if not next_clicked:
                print("   [Step 2] Could not find Next button after password change (all selectors tried).")
            if time.time() - start_time > TIMEOUT:
                raise Exception("TIMEOUT_REQUIRE_PASSWORD_CHANGE: End")
            
            # Sau khi nhấn Next, chờ 2 giây và kiểm tra crash
            WebDriverWait(self.driver, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")
            try:
                # Kiểm tra driver còn sống
                current_url = self.driver.current_url
                print(f"   [Step 2] Post-Next URL: {current_url}")
                WebDriverWait(self.driver, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")
            except Exception as crash_e:
                print(f"   [Step 2] Crash detected after Next click: {crash_e}. Reloading to instagram.com...")
                self.driver.get("https://www.instagram.com/")
                WebDriverWait(self.driver, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")
                time.sleep(2)
                return  # Hoặc raise tùy logic
        except Exception as e:
            print(f"   [Step 2] Error handling require password change: {e}")
    def handle_status(self, status, ig_username, gmx_user, gmx_pass, linked_mail=None, ig_password=None, depth=0):
        # Chống đệ quy vô tận (giới hạn 20 bước nhảy trạng thái)
        if depth > 20:
             raise Exception("STOP_FLOW_LOOP: Max recursion depth reached")
        print(f"   [Step 2] Processing status: {status}")
        if not self._is_driver_alive():
            raise Exception("STOP_FLOW_CRASH: Browser Closed")

        success_statuses = [
            "LOGGED_IN_SUCCESS", "COOKIE_CONSENT", "TERMS_AGREEMENT", 
            "NEW_MESSAGING_TAB", "SUCCESS"
        ]
        if status in success_statuses:
            print(f"   [Step 2] Status {status} indicates successful login. No action needed.")
            return status
        
        # "REAL_BIRTHDAY_REQUIRED"
        if status == "REAL_BIRTHDAY_REQUIRED":
            # reload instagram to trigger birthday screen
            print("   [Step 2] Handling Real Birthday Required - Reloading Instagram...")
            self.driver.get("https://www.instagram.com/")
            WebDriverWait(self.driver, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")
            new_status = self._check_verification_result()
            return self.handle_status(new_status, ig_username, gmx_user, gmx_pass, linked_mail, ig_password, depth + 1)
        
        # SUBSCRIBE_OR_CONTINUE
        if status == "SUBSCRIBE_OR_CONTINUE":
            print("   [Step 2] Handling Subscribe Or Continue...")
            # se co 2 radio button: => chon cai thu 2 (use for free with ads)
            wait_and_click(self.driver, By.XPATH, "(//input[@type='radio'])[2]", timeout=20)
            time.sleep(1)
            wait_and_click(self.driver, By.XPATH, "//button[contains(text(), 'Continue') or contains(text(), 'Tiếp tục')]", timeout=20)
            WebDriverWait(self.driver, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")
            new_status = self._check_verification_result()
            return self.handle_status(new_status, ig_username, gmx_user, gmx_pass, linked_mail, ig_password, depth + 1)
                
        
        if status == "RETRY_UNUSUAL_LOGIN":
            print("   [Step 2] Detected 'Sorry, there was a problem. Please try again.' Retrying Unusual Login...")
            return self.handle_status("CONTINUE_UNUSUAL_LOGIN", ig_username, gmx_user, gmx_pass, linked_mail, ig_password, depth + 1)
        
        # CHECKPOINT_PHONE
        if status == "CHECKPOINT_PHONE":
            print("   [Step 2] Handling Checkpoint Phone...")
            # click button back to return CONTINUE_UNUSUAL_LOGIN
            back_clicked = wait_and_click(self.driver, By.XPATH, "//button[contains(text(), 'Back') or contains(text(), 'Quay lại')]", timeout=20)
            wait_dom_ready(self.driver, timeout=10)
            if back_clicked:
                return self.handle_status("CONTINUE_UNUSUAL_LOGIN", ig_username, gmx_user, gmx_pass, linked_mail, ig_password, depth + 1)
            
        # RECOVERY_CHALLENGE
        if status == "RECOVERY_CHALLENGE":
            print("   [Step 2] Handling Recovery Challenge...")
            # Select email radio button
            try:
                email_radio = self.driver.find_element(By.CSS_SELECTOR, "input[type='radio'][value='EMAIL']")
                email_radio.click()
                print("   [Step 2] Selected email radio button.")
            except Exception as e:
                print(f"   [Step 2] Error selecting email radio: {e}")
            
            # Click continue
            try:
                wait_and_click(self.driver, By.XPATH, "//span[contains(text(), 'Continue')]", timeout=20)
                print("   [Step 2] Clicked Continue.")
            except Exception as e:
                print(f"   [Step 2] Error clicking continue: {e}")
            
            WebDriverWait(self.driver, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")
            new_status = self._check_verification_result()
            return self.handle_status(new_status, ig_username, gmx_user, gmx_pass, linked_mail, ig_password, depth + 1)
            
        # RETRY_UNSUAL_LOGIN
        if status == "RETRY_UNUSUAL_LOGIN":
            # call step 1 to login again with new data 
            print("   [Step 2] Handling Retry Unusual Login...")
            isLogin = step1_login.perform_login(self, ig_username, ig_password)
            wait_dom_ready(self.driver, timeout=20)
            if isLogin:
                return self.handle_status("LOGGED_IN_SUCCESS", ig_username, gmx_user, gmx_pass, linked_mail, ig_password, depth + 1)
            else:
                return  self.handle_status("UNUSUAL_LOGIN", ig_username, gmx_user, gmx_pass, linked_mail, ig_password, depth + 1)
            
        
        # if status == "REQUIRE_PASSWORD_CHANGE":
        #     print("   [Step 2] Password too short, retrying change password...")
        #     return self.handle_status("REQUIRE_PASSWORD_CHANGE", ig_username, gmx_user, gmx_pass, linked_mail, ig_password, depth + 1)
        if status == "CONTINUE_UNUSUAL_LOGIN":
            # Timeout protection for unusual login (max 60s)
            start_time = time.time()
            TIMEOUT = 60
            print("   [Step 2] Handling Unusual Login (Clicking Continue/This Was Me)...")
            time.sleep(2) # Chờ load UI
            try:
                # Tìm tất cả các thẻ label (vì cấu trúc bạn gửi là <label ...> Text <input> ... </label>)
                labels = self.driver.execute_script("return Array.from(document.querySelectorAll('label'));")
                email_selected = False
                
                if len(labels) > 0:
                    # Ưu tiên chọn radio button Email
                    email_radio = None
                    for label in labels:
                        if "email" in label.text.lower() or "e-mail" in label.text.lower():
                            try:
                                inp = label.find_element(By.TAG_NAME, "input")
                                if inp.get_attribute("type") == "radio":
                                    email_radio = inp
                                    print(f"   [Step 2] Found Email radio: {label.text.strip()}")
                                    break
                            except:
                                continue
                    
                    if email_radio:
                        # Click radio Email
                        radio_id = email_radio.get_attribute("id")
                        if radio_id:
                            wait_and_click(self.driver, By.CSS_SELECTOR, f"input[id='{radio_id}']", timeout=20)
                        else:
                            email_radio.click()
                        print("   [Step 2] Selected Email radio button.")
                        email_selected = True
                    else:
                        # Fallback: Chọn radio đầu tiên nếu không tìm thấy Email
                        radios = self.driver.execute_script("return Array.from(document.querySelectorAll('input[type=\"radio\"]'));")
                        if len(radios) > 0:
                            print("   [Step 2] Email radio not found. Selecting 1st radio...")
                            wait_and_click(self.driver, By.CSS_SELECTOR, "input[type='radio']", timeout=20)
                            email_selected = True  # Assume selected
                        else:
                            print("   [Step 2] No radio buttons found.")
                else:
                    print("   [Step 2] No labels found. Proceeding to click Continue.")

            except Exception as e:
                print(f"   [Step 2] Radio selection warning: {e}")

            time.sleep(1) # Chờ UI update nhẹ
            
            # Tìm nút Continue hoặc This Was Me
            keywords = ["continue", "tiếp tục", "this was me", "đây là tôi"]
            
            # Quét buttons
            btns = self.driver.execute_script("return Array.from(document.querySelectorAll('button'));")
            clicked = False
            for b in btns:
                if any(k in b.text.lower() for k in keywords) and b.is_displayed():
                    if wait_and_click(self.driver, By.TAG_NAME, "button", timeout=20):
                        clicked = True
                        break
                if time.time() - start_time > TIMEOUT:
                    raise Exception("TIMEOUT_CONTINUE_UNUSUAL_LOGIN: Button click")
            
            # Fallback div role button
            if not clicked:
                divs = self.driver.execute_script("return Array.from(document.querySelectorAll('div[role=\"button\"]'));")
                for d in divs:
                    if any(k in d.text.lower() for k in keywords) and d.is_displayed():
                        wait_and_click(self.driver, By.XPATH, "//div[@role='button']", timeout=20); clicked = True; break
                    if time.time() - start_time > TIMEOUT:
                        raise Exception("TIMEOUT_CONTINUE_UNUSUAL_LOGIN: Fallback button click")

            time.sleep(5) # Chờ load sau khi click
            if time.time() - start_time > TIMEOUT:
                raise Exception("TIMEOUT_CONTINUE_UNUSUAL_LOGIN: End")
            
            # Sau khi click continue, thường sẽ nhảy sang Checkpoint Mail
            # Gọi đệ quy lại handle_status với trạng thái mới (quét lại body)
            wait_dom_ready(self.driver, timeout=10)
            time.sleep(2)
            new_status = self._check_verification_result()
            print(f"   [Step 2] Status after Continue: {new_status}")
            # Anti-hang: If status unchanged, refresh to avoid loop
            if new_status == status:
                print(f"   [Step 2] Status unchanged after handling {status}, refreshing to avoid hang...")
                self.driver.refresh()
                wait_dom_ready(self.driver, timeout=20)
                time.sleep(2)
                new_status = self._check_verification_result()
            return self.handle_status(new_status, ig_username, gmx_user, gmx_pass, linked_mail, ig_password, depth + 1)

        if status == "REQUIRE_PASSWORD_CHANGE":
            # Timeout protection for password change (max 60s)
            start_time = time.time()
            TIMEOUT = 60
            print("   [Step 2] Handling Require Password Change...")
            if ig_password :
                new_pass = ig_password + "@"
                try:
                    self._handle_require_password_change(new_pass)
                except Exception as e:
                    print(f"   [Step 2] Error in _handle_require_password_change: {e}")
                    # If error, try to recover by refreshing
                    self.driver.get("https://www.instagram.com/")
                    wait_dom_ready(self.driver, timeout=20)
                    time.sleep(2)
                    raise e  # Re-raise to stop flow
                if time.time() - start_time > TIMEOUT:
                    raise Exception("TIMEOUT_REQUIRE_PASSWORD_CHANGE: End")
                # Cập nhật lại password mới lên GUI NGAY LẬP TỨC trước khi gọi các bước tiếp theo
                if hasattr(self, "on_password_changed") and callable(self.on_password_changed):
                    self.on_password_changed(ig_username, new_pass)
                time.sleep(4)
                wait_dom_ready(self.driver, timeout=20)
                
                
                # Đảm bảo các bước sau luôn dùng mật khẩu mới
                ig_password = new_pass
                new_status = self._check_verification_result()
                print(f"   [Step 2] Status after Password Change: {new_status}")
                # Anti-hang: If status unchanged, refresh to avoid loop
                if new_status == status:
                    self.driver.get("https://www.instagram.com/")
                return self.handle_status(new_status, ig_username, gmx_user, gmx_pass, linked_mail, ig_password, depth + 1)
            else:
                raise Exception("STOP_FLOW_REQUIRE_PASSWORD_CHANGE: No password provided")

        if status == "CHANGE_PASSWORD":
            # handle one input for new password
            print("   [Step 2] Handling Change Password...")
            if ig_password :
                new_pass = ig_password + "@"
                try:
                    self._handle_change_password(new_pass)
                except Exception as e:
                    print(f"   [Step 2] Error in _handle_change_password: {e}")
                    # If error, try to recover by refreshing
                    self.driver.get("https://www.instagram.com/")
                    wait_dom_ready(self.driver, timeout=20)
                    time.sleep(2)
                    raise e
                # Cập nhật lại password mới lên GUI NGAY LẬP TỨC trước khi gọi các bước tiếp theo
                if hasattr(self, "on_password_changed") and callable(self.on_password_changed):
                    self.on_password_changed(ig_username, new_pass)
                
                wait_dom_ready(self.driver, timeout=20)
                time.sleep(4)
                new_status = self._check_verification_result()
                print(f"   [Step 2] Status after Change Password: {new_status}")
                # Anti-hang: If status unchanged, refresh to avoid loop
                if new_status == status:
                    self.driver.get("https://www.instagram.com/")

                return self.handle_status(new_status, ig_username, gmx_user, gmx_pass, linked_mail, ig_password, depth + 1)
            else:
                raise Exception("STOP_FLOW_CHANGE_PASSWORD: No password provided")
            
    

        # XỬ LÝ BIRTHDAY
        if status == "BIRTHDAY_SCREEN":
            wait_dom_ready(self.driver, timeout=20)
            if self._handle_birthday_screen():
                # get new status after handling birthday
                wait_dom_ready(self.driver, timeout=20)
                time.sleep(3)
                new_status = self._check_verification_result()
                print(f"   [Step 2] Status after Birthday: {new_status}")
                # Anti-hang: If status unchanged, refresh to avoid loop
                if new_status == status:
                    print(f"   [Step 2] Status unchanged after handling {status}, refreshing to avoid hang...")
                    self.driver.refresh()
                    wait_dom_ready(self.driver, timeout=20)
                    time.sleep(4)
                    new_status = self._check_verification_result()
                # de quy kiem tra lai trang thai
                return self.handle_status(new_status, ig_username, gmx_user, gmx_pass, linked_mail, ig_password, depth + 1)
            else:   
                return self._handle_birthday_screen()

        # XỬ LÝ CHECKPOINT MAIL
        if status == "CHECKPOINT_MAIL":
            print("   [Step 2] Handling Email Checkpoint...")
            result = self._solve_email_checkpoint(ig_username, gmx_user, gmx_pass, linked_mail, ig_password, depth)
            
            time.sleep(3)
            wait_dom_ready(self.driver, timeout=20)
            new_status = self._check_verification_result()
            print(f"   [Step 2] Status after Email Checkpoint: {new_status}")
            # Anti-hang: If status unchanged, refresh to avoid loop
            if new_status == status:
                print(f"   [Step 2] Status unchanged after handling {status}, refreshing to avoid hang...")
                self.driver.refresh()
                wait_dom_ready(self.driver, timeout=20)
                time.sleep(4)
                new_status = self._check_verification_result()
                
            # de quy kiem tra lai trang thai
            return self.handle_status(new_status, ig_username, gmx_user, gmx_pass, linked_mail, ig_password, depth + 1)
        
        # LOGIN_FAILED_SOMETHING_WENT_WRONG 
        if status == "LOGIN_FAILED_SOMETHING_WENT_WRONG":
            # refresh page to try again
            print("   [Step 2] Login Failed Something Went Wrong detected. Refreshing page to retry...")
            self.driver.get("https://www.instagram.com/")
            WebDriverWait(self.driver, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")
            new_status = self._check_verification_result()
            return self.handle_status(new_status, ig_username, gmx_user, gmx_pass, linked_mail, ig_password, depth + 1)
        
        if status == "SOMETHING_WRONG":
            # refresh page to try again
            print("   [Step 2] Something went wrong detected. Refreshing page to retry...")
            # truy cap instagram.com
            self.driver.get("https://www.instagram.com/")
            WebDriverWait(self.driver, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")
            new_status = self._check_verification_result()
            return self.handle_status(new_status, ig_username, gmx_user, gmx_pass, linked_mail, ig_password, depth + 1)
        

        # NHÓM FAIL
        if status == "WRONG_CODE":
            print("   [Step 2] Wrong code detected. Retrying checkpoint...")
            return self.handle_status("CHECKPOINT_MAIL", ig_username, gmx_user, gmx_pass, linked_mail, ig_password, depth + 1)
        
        fail_statuses = [
            "UNUSUAL_LOGIN", "TRY_ANOTHER_DEVICE", "2FA_REQUIRED", "SUSPENDED",
            "LOGIN_FAILED_INCORRECT", "2FA_SMS", "2FA_WHATSAPP", "GET_HELP_LOG_IN",
            "2FA_APP", "2FA_APP_CONFIRM", "FAIL_LOGIN_REDIRECTED_TO_PROFILE_SELECTION",
            "LOGIN_FAILED_RETRY", "2FA_NOTIFICATIONS", "LOGGED_IN_UNKNOWN_STATE",
            "TIMEOUT_LOGIN_CHECK", "PAGE_BROKEN", "SUSPENDED_PHONE","LOG_IN_ANOTHER_DEVICE", 
            "CONFIRM_YOUR_IDENTITY", "2FA_TEXT_MESSAGE", 
            "ACCOUNT_DISABLED", "CONTINUE_UNUSUAL_LOGIN_PHONE"
        ]

        if status in fail_statuses:
            raise Exception(f"STOP_FLOW_EXCEPTION: {status}")
        
        if status == "BIRTHDAY_SCREEN":
            wait_dom_ready(self.driver, timeout=20)
            time.sleep(2)
            if self._handle_birthday_screen():
                # get new status after handling birthday
                wait_dom_ready(self.driver, timeout=20)
                new_status = self._check_verification_result()
                print(f"   [Step 2] Status after Birthday: {new_status}")
                # Anti-hang: If status unchanged, refresh to avoid loop
                if new_status == status:
                    print(f"   [Step 2] Status unchanged after handling {status}, refreshing to avoid hang...")
                    self.driver.refresh()
                    wait_dom_ready(self.driver, timeout=20)
                    new_status = self._check_verification_result()
                # de quy kiem tra lai trang thai
                return self.handle_status(new_status, ig_username, gmx_user, gmx_pass, linked_mail, ig_password, depth + 1)
            else:
                return self._handle_birthday_screen()
        
        if status == "TIMEOUT" and depth < 3:
            print("   [Step 2] Status is TIMEOUT. Reloading page to retry...")
            self.driver.refresh()
            wait_dom_ready(self.driver, timeout=20)
            new_status = self._check_verification_result()
            return self.handle_status(new_status, ig_username, gmx_user, gmx_pass, linked_mail, ig_password, depth + 1)

        # Capture screenshot for unknown status
        timestamp = int(time.time())
        screenshot_dir = "screenshots"
        os.makedirs(screenshot_dir, exist_ok=True)
        screenshot_path = os.path.join(screenshot_dir, f"unknown_status_{status}_{timestamp}.png")
        self.driver.save_screenshot(screenshot_path)
        print(f"   [Step 2] Screenshot saved for unknown status '{status}': {screenshot_path}")

        raise Exception(f"STOP_FLOW_UNKNOWN_STATUS: {status}")

    # ==========================================
    # 3. LOGIC XỬ LÝ BIRTHDAY (STRICT VERIFY YEAR)
    # ==========================================
    def _handle_birthday_screen(self):
        # Timeout protection for birthday screen (max 60s)
        start_time = time.time()
        TIMEOUT = 60
        print("   [Step 2] Handling Birthday Screen...")
        # Check for "Enter your real birthday" text and reload if found
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
            if "enter your real birthday" in body_text or "nhập ngày sinh thật của bạn" in body_text:
                print("   [Step 2] Detected 'Enter your real birthday' - Reloading Instagram...")
                self.driver.get("https://www.instagram.com/")
                WebDriverWait(self.driver, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")
                return "LOGGED_IN_SUCCESS"
        except Exception as e:
            print(f"   [Step 2] Warning checking for real birthday text: {e}")
        
        try:
            # VÒNG LẶP CHÍNH (3 Lần)
            for attempt in range(3):
                try:
                    body_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
                    if "enter your real birthday" in body_text or "nhập ngày sinh thật của bạn" in body_text:
                        print("   [Step 2] Detected 'Enter your real birthday' - Reloading Instagram...")
                        self.driver.get("https://www.instagram.com/")
                        time.sleep(2)
                        wait_dom_ready(self.driver, timeout=20)
                        return "LOGGED_IN_SUCCESS"
                except Exception as e:
                    print(f"   [Step 2] Warning checking for real birthday text: {e}")
                if time.time() - start_time > TIMEOUT:
                    raise Exception("TIMEOUT_BIRTHDAY_SCREEN: Main loop")
                print(f"   [Step 2] Birthday Attempt {attempt+1}/3...")
                
                # BƯỚC 2: CHỌN NĂM (STRICT VERIFICATION)
                year_confirmed = False 
                
                try:
                    year_select_el = None
                    selectors = [
                        "select[title='Year:']", "select[title='Năm:']", 
                        "select[name='birthday_year']", "select[aria-label='Year']"
                    ]
                    
                    for sel in selectors:
                        els = self.driver.find_elements(By.CSS_SELECTOR, sel)
                        if els and els[0].is_displayed():
                            year_select_el = els[0]; break
                        if time.time() - start_time > TIMEOUT:
                            raise Exception("TIMEOUT_BIRTHDAY_SCREEN: Year select find")
                    
                    if year_select_el:
                        select = Select(year_select_el)
                        
                        # Random năm an toàn (1985-2000)
                        target_year = str(random.randint(1985, 2000))
                        
                        # --- LOOP CHỌN VÀ KIỂM TRA LẠI ---
                        for _ in range(3):
                            # Thử chọn
                            try: select.select_by_value(target_year)
                            except: pass
                            
                            # Thử JS ép giá trị
                            try:
                                self.driver.execute_script(f"arguments[0].value = '{target_year}';", year_select_el)
                                self.driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", year_select_el)
                            except: pass
                            
                            time.sleep(0.5)
                            
                            # Kiểm tra giá trị thực tế
                            current_val = year_select_el.get_attribute("value")
                            if current_val == target_year:
                                year_confirmed = True
                                print(f"   [Step 2] Year VERIFIED: {target_year}")
                                break 
                            else:
                                print(f"   [Step 2] Year mismatch ({current_val} vs {target_year}). Retrying...")
                            if time.time() - start_time > TIMEOUT:
                                raise Exception("TIMEOUT_BIRTHDAY_SCREEN: Year select loop")
                        
                        if year_confirmed:
                            # Chọn Tháng/Ngày
                            try:
                                Select(self.driver.find_element(By.CSS_SELECTOR, "select[name='birthday_month']")).select_by_index(random.randint(1, 11))
                                Select(self.driver.find_element(By.CSS_SELECTOR, "select[name='birthday_day']")).select_by_index(random.randint(1, 27))
                            except: pass
                            time.sleep(1.5)
                        else:
                            print("   [Step 2] Failed to verify Year change. Popup might be blocking.")
                    
                    else:
                        print(f"   [Step 2] Year dropdown missing. Retrying popup logic...")
                        # if nuke_real_birthday_popup(): continue 
                        time.sleep(1); continue
                        
                except Exception as e:
                    print(f"   [Step 2] Select error: {e}")
                    time.sleep(1); continue

                # BƯỚC 3: CLICK NEXT (CHỈ KHI ĐÃ VERIFY NĂM)
                if year_confirmed:
                    print("   [Step 2] Year is Confirmed. Clicking Next...")
                    next_clicked = False
                    
                    # Robust Next button finding and clicking
                    next_selectors = [
                        # Specific class from HTML
                        (By.CSS_SELECTOR, "div.x1i10hfl.xjqpnuy.xc5r6h4.xqeqjp1.x1phubyo.x972fbf.x10w94by.x1qhh985.x14e42zd.xdl72j9.x2lah0s.x3ct3a4.xdj266r.x14z9mp.xat24cr.x1lziwak.x2lwn1j.xeuugli.xexx8yu.x18d9i69.x1hl2dhg.xggy1nq.x1ja2u2z.x1t137rt.x1q0g3np.x1lku1pv.x1a2a7pz.x6s0dn4.xjyslct.x1ejq31n.x18oe1m7.x1sy0etr.xstzfhl.x9f619.x9bdzbf.x1ypdohk.x78zum5.x1f6kntn.xwhw2v2.xl56j7k.x17ydfre.x1n2onr6.x2b8uid.xlyipyv.x87ps6o.x14atkfc.x5c86q.x18br7mf.x1i0vuye.x6nl9eh.x1a5l9x9.x7vuprf.x1mg3h75.xn3w4p2.x106a9eq.x1xnnf8n.x18cabeq.x158me93.xk4oym4.x1uugd1q"),
                        # Generic role button with Next text
                        (By.XPATH, "//div[@role='button' and contains(text(), 'Next')]"),
                        # Button with Next text
                        (By.XPATH, "//button[contains(text(), 'Next')]"),
                        # Vietnamese Next
                        (By.XPATH, "//button[contains(text(), 'Tiếp')]"),
                        # Generic div role button
                        (By.CSS_SELECTOR, "div[role='button'][tabindex='0']")
                    ]
                    
                    for by, sel in next_selectors:
                        try:
                            next_btn = wait_element(self.driver, by, sel, timeout=20)
                            if next_btn and next_btn.is_displayed() and next_btn.is_enabled():
                                print(f"   [Step 2] Found Next button with selector: {sel}")
                                
                                # Try multiple click methods
                                click_success = False
                                
                                # Method 1: Direct click
                                try:
                                    next_btn.click()
                                    click_success = True
                                    print("   [Step 2] Next button clicked via direct click.")
                                except Exception as e:
                                    print(f"   [Step 2] Direct click failed: {e}")
                                
                                # Method 2: JS click if direct failed
                                if not click_success:
                                    try:
                                        self.driver.execute_script("arguments[0].click();", next_btn)
                                        click_success = True
                                        print("   [Step 2] Next button clicked via JS click.")
                                    except Exception as e:
                                        print(f"   [Step 2] JS click failed: {e}")
                                
                                # Method 3: ActionChains if JS failed
                                if not click_success:
                                    try:
                                        ActionChains(self.driver).move_to_element(next_btn).click().perform()
                                        click_success = True
                                        print("   [Step 2] Next button clicked via ActionChains.")
                                    except Exception as e:
                                        print(f"   [Step 2] ActionChains click failed: {e}")
                                
                                if click_success:
                                    next_clicked = True
                                    break
                        except Exception as e:
                            print(f"   [Step 2] Error with selector {sel}: {e}")
                            continue
                    
                    if not next_clicked:
                        print("   [Step 2] Failed to click Next button with all methods.")
                    else:
                        print("   [Step 2] Next button clicked successfully.")
                    
                    time.sleep(2)

                    # CHECK CONFIRM YES
                    yes_xpaths = ["//button[contains(text(), 'Yes')]", "//button[contains(text(), 'Có')]"]
                    clicked_yes = False
                    for xpath in yes_xpaths:
                        if wait_and_click(self.driver, By.XPATH, xpath, timeout=20): 
                            clicked_yes = True; break
                        if time.time() - start_time > TIMEOUT:
                            raise Exception("TIMEOUT_BIRTHDAY_SCREEN: Yes button click")
                    
                    if clicked_yes: break 
                    
                    # Nếu vào được bên trong -> Thoát
                    body = self.driver.find_element(By.TAG_NAME, "body").text.lower()
                    if "allow the use of cookies" in body or "posts" in body or "search" in body: break
                else:
                    print("   [Step 2] Skipping Next because Year was not confirmed.")

            WebDriverWait(self.driver, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")
            if time.time() - start_time > TIMEOUT:
                raise Exception("TIMEOUT_BIRTHDAY_SCREEN: End")
            return "LOGGED_IN_SUCCESS"

        except Exception as e:
            print(f"   [Step 2] Warning Birthday Handle: {str(e)}")
            return "LOGGED_IN_SUCCESS"

    # ==========================================
    # 4. LOGIC GIẢI CHECKPOINT (RADIO + POLLING FIX)
    # ==========================================
    def _check_is_birthday_screen(self):
        timeout = 30
        poll = 0.5
        end_time = time.time() + timeout
        keywords = ["add your birthday", "thêm ngày sinh", "date of birth", "birth", "sinh nhật"]
        while time.time() < end_time:
            try:
                body = self.driver.find_element(By.TAG_NAME, "body").text.lower()
                has_select = len(self.driver.find_elements(By.TAG_NAME, "select")) > 0
                has_text = any(k in body for k in keywords)
                if has_text and has_select:
                    return True
            except:
                pass
            time.sleep(poll)
        return False

    def _solve_email_checkpoint(self, ig_username, gmx_user, gmx_pass, linked_mail=None, ig_password=None, depth=0):
        # Timeout protection for email checkpoint (max 60s)
        start_time = time.time()
        TIMEOUT = 70
        print(f"   [Step 2] Detected Email Checkpoint...")
        
        # --- GIAI ĐOẠN 0: RADIO BUTTON ---
        try:
            radios = self.driver.execute_script("return Array.from(document.querySelectorAll('input[type=\"radio\"]'));")
            if len(radios) > 0:
                print(f"   [Step 2] Found {len(radios)} options. Selecting 1st radio...")
                
                # Click radio đầu tiên
                wait_and_click(self.driver, By.CSS_SELECTOR, "input[type='radio']", timeout=20)
                time.sleep(0.5)  # Reduced from 1s
                
                # Click Send/Next
                send_btns = self.driver.execute_script("return Array.from(document.querySelectorAll('button[type=\"submit\"], button._acan, div[role=\"button\"][tabindex=\"0\"]'));")
                for btn in send_btns:
                    txt = btn.text.lower()
                    if btn.is_displayed() and any(k in txt for k in ["send", "gửi", "next", "tiếp", "continue"]):
                        print(f"   [Step 2] Clicked confirmation: {txt}")
                        wait_and_click(self.driver, By.CSS_SELECTOR, "button[type='submit'], button._acan, div[role='button'][tabindex='0']", timeout=20)
                        time.sleep(2)  # Reduced from 2s
                        break
                        if time.time() - start_time > TIMEOUT:
                            raise Exception("TIMEOUT_EMAIL_CHECKPOINT: Radio/Send button")
        except Exception as e:
            print(f"   [Step 2] Warning handling radio buttons: {e}")
        
        # --- GIAI ĐOẠN 1: VERIFY HINT ---
        if not self._validate_masked_email_robust(gmx_user, linked_mail):
             raise Exception("STOP_FLOW_CHECKPOINT: Email hint mismatch")

        # Sử dụng _check_mail_flow để đồng bộ logic chống lặp vô hạn
        def get_code():
            try:
                # Truyền thêm tham số linked_mail vào đây
                return get_verify_code_v2(gmx_user, gmx_pass, ig_username, target_email=linked_mail)
            except Exception as e:
                if "GMX_DIE" in str(e): raise e
                return None
        def input_code(code):
            code_input = None
            # Fast JS check for common code inputs
            code_input = self.driver.execute_script("""
                var inputs = document.querySelectorAll('input');
                for (var i = 0; i < inputs.length; i++) {
                    var inp = inputs[i];
                    if (inp.id === 'security_code' || inp.name === 'security_code' || inp.name === 'verificationCode' || (inp.type === 'text' && inp.offsetParent !== null)) {
                        return inp;
                    }
                }
                return null;
            """)
            if code_input and code_input.is_displayed() and code_input.is_enabled():
                print("   [Step 2] Found code input via fast JS check")
            else:
                code_input = None
                # Ưu tiên tìm label "Code" rồi lấy input liên kết
                try:
                    labels = self.driver.execute_script("return Array.from(document.querySelectorAll('label'));")
                    for label in labels:
                        if label.text.strip().lower() == "code":
                            input_id = label.get_attribute("for")
                            if input_id:
                                try:
                                    code_input = self.driver.find_element(By.ID, input_id)
                                    if code_input.is_displayed() and code_input.is_enabled():
                                        print(f"   [Step 2] Found code input via label 'Code': {input_id}")
                                        break
                                except:
                                    continue
                except:
                    pass
                
                # Fallback: Thử các selector khác
                if not code_input:
                    input_css_list = ["input[id='security_code']", "input[name='email']", "input[name='security_code']", "input[type='text']", "input[name='verificationCode']"]
                    for sel in input_css_list:
                        try:
                            el = wait_element(self.driver, By.CSS_SELECTOR, sel, timeout=15)  # Giảm timeout
                            if el and el.is_displayed() and el.is_enabled():
                                code_input = el
                                print(f"   [Step 2] Found code input with selector: {sel}")
                                break
                        except Exception as e:
                            print(f"   [Step 2] Error finding input with {sel}: {e}")
            
            if code_input:
                try:
                    print(f"   [Step 2] Attempting to input code {code}...")
                    # First try to click and focus
                    code_input.click()
                    time.sleep(0.2)
                    # Clear existing value
                    code_input.send_keys(Keys.CONTROL + "a")
                    code_input.send_keys(Keys.DELETE)
                    time.sleep(0.1)
                    # Input the code
                    code_input.send_keys(code)
                    time.sleep(0.5)
                    # Check if value was set
                    current_value = code_input.get_attribute('value')
                    print(f"   [Step 2] Input field value after send_keys: '{current_value}'")
                    if current_value != code:
                        print("   [Step 2] send_keys failed, trying JS...")
                        # Fallback to JS
                        self.driver.execute_script("arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", code_input, code)
                        time.sleep(0.2)
                        current_value = code_input.get_attribute('value')
                        print(f"   [Step 2] Input field value after JS: '{current_value}'")
                    # Send Enter
                    code_input.send_keys(Keys.ENTER)
                    time.sleep(1)
                    if "security_code" in self.driver.current_url:
                        wait_and_click(self.driver, By.XPATH, "//button[@type='submit'] | //button[contains(text(), 'Confirm')] | //button[contains(text(), 'Xác nhận')]", timeout=20)
                    print("   [Step 2] Code input completed.")
                except Exception as e:
                    print(f"   [Step 2] Error inputting code: {e}")
                    # Last resort: JS input
                    try:
                        self.driver.execute_script(f"document.querySelector('input[id=\"{code_input.get_attribute('id')}\"]').value = '{code}'; document.querySelector('input[id=\"{code_input.get_attribute('id')}\"]').dispatchEvent(new Event('input', {{ bubbles: true }}));")
                        print("   [Step 2] JS fallback input attempted.")
                    except Exception as e2:
                        print(f"   [Step 2] JS fallback failed: {e2}")
            else:
                raise Exception("STOP_FLOW_CHECKPOINT: Cannot find code input")
        check_result = self._check_mail_flow(get_code, input_code, max_retries=3, timeout=TIMEOUT)
        print(f"   [Step 2] Email Checkpoint code verification result: {check_result}")
        return self.handle_status(check_result, ig_username, gmx_user, gmx_pass, linked_mail, ig_password, depth + 1)

    # ==========================================
    # 5. LOGIC CHECK MAIL (REUSE, ANTI-INFINITE LOOP)
    # ==========================================
    def _check_mail_flow(self, get_code_func, input_code_func, max_retries=3, timeout=60):
        """
        Chuẩn hóa logic check mail: lấy code, nhập code, kiểm tra kết quả, chống lặp vô hạn.
        get_code_func: hàm lấy code (lambda)
        input_code_func: hàm nhập code (lambda code)
        """
        start_time = time.time()
        for attempt in range(1, max_retries + 1):
            if time.time() - start_time > timeout:
                raise Exception("CHECK_MAIL: No code ")
            print(f"   [Step 2] >>> Code Attempt {attempt}/{max_retries} <<<")
            if attempt > 1:
                # Có thể bổ sung logic gửi lại mã nếu cần
                pass
            try:
                code = get_code_func()
            except Exception as e:
                print(f"   [Step 2] Error getting code: {e}")
                code = None
            if not code:
                if attempt < max_retries:
                    print("   [Step 2] No code found via mail. Retrying...")
                    time.sleep(2)  # Reduced from 3s to 2s for faster retry
                    continue
                else:
                    raise Exception("STOP_FLOW_CHECK_MAIL: No code found in mail")
            print(f"   [Step 2] Inputting code {code}...")
            try:
                if not self._is_driver_alive():
                    raise Exception("Browser closed before input")
                input_code_func(code)
                if not self._is_driver_alive():
                    raise Exception("Browser closed during input")
                print("   [Step 2] Waiting for UI to update after code input...")
                wait_and_click(self.driver, By.CSS_SELECTOR, "button[type='submit']", timeout=20)
                # Tăng thời gian chờ sau khi nhấn submit để tránh check mail quá sớm khi UI còn đang xử lý
                WebDriverWait(self.driver, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")
                time.sleep(1)  # Reduced sleep to 1s
                print("   [Step 2] Verifying code...")
                check_result = self._check_verification_result()
                print(f"   [Step 2] Result: {check_result}")
            except Exception as e:
                if "closed" in str(e).lower() or "crash" in str(e).lower() or "stale" in str(e).lower() or "not reachable" in str(e).lower():
                    raise Exception("STOP_FLOW_CRASH: Browser closed during code verification")
                else:
                    print(f"   [Step 2] Error during code input/verification: {e}")
                    if attempt < max_retries:
                        print("   [Step 2] Retrying due to error...")
                        time.sleep(1)
                        continue
                    else:
                        raise
            if check_result in ["CHECKPOINT_MAIL", "WRONG_CODE", "TIMEOUT"]:
                if attempt < max_retries:
                    if check_result == "WRONG_CODE":
                        # Click "Get a new one" link to request new code
                        try:
                            get_new_link = self.driver.find_element(By.XPATH, "//a[contains(text(), 'Get a new one') or contains(@href, '_replay')]")
                            get_new_link.click()
                            print("   [Step 2] Clicked 'Get a new one' to request new code.")
                            time.sleep(2)  # Wait for new code to be sent
                        except Exception as e:
                            print(f"   [Step 2] Could not find or click 'Get a new one' link: {e}")
                    print("   [Step 2] Code verification failed (wrong/rejected/timeout), retrying mail...")
                    continue
                else:
                    raise Exception("STOP_FLOW_CHECKPOINT_MAIL_EXHAUSTED: Max mail attempts reached")
            return check_result

    def _handle_change_password(self, old_password):
        # Timeout protection for change password (max 60s)
        start_time = time.time()
        TIMEOUT = 60
        print(f"   [Step 2] Handling Password Change (Re-using old password)...")
        
        try:
            # 1. Chờ ít nhất một ô input xuất hiện (Retry mechanism tích hợp trong wait_element)
            first_input = wait_element(self.driver, By.CSS_SELECTOR, 
                "input[name='password'], input[name='new_password'], input[type='password']", timeout=20)
            
            if not first_input:
                raise Exception("No password input fields found")
            
            visible_inputs = []
            visible_inputs.append(first_input)

            # 3. Điền pass vào các ô tìm thấy (Logic: Điền tối đa 2 ô đầu tiên tìm thấy - thường là New & Confirm)
            filled_count = 0
            for inp in visible_inputs:
                if filled_count >= 2: break # Safety: Chỉ điền tối đa 2 ô để tránh điền nhầm vào ô 'Old Password' nếu form quá dị
                try:
                    inp.click()
                    inp.clear()
                    inp.send_keys(old_password)
                    filled_count += 1
                except Exception as e:
                    print(f"   [Step 2] Warning: Failed to fill an input field: {str(e)}")
            
            time.sleep(1) # Ổn định UI trước khi submit

            # 4. Xử lý Submit (Giữ nguyên logic retry tìm nút mạnh mẽ của bạn)
            submit_clicked = False
            # Ưu tiên nút submit chuẩn
            if wait_and_click(self.driver, By.CSS_SELECTOR, "button[type='submit']", timeout=20): 
                submit_clicked = True
            
            # Fallback: Quét tất cả button nếu nút submit chuẩn không hoạt động
            if not submit_clicked:
                btns = self.driver.execute_script("return Array.from(document.querySelectorAll('button'));")
                for b in btns:
                    try:
                        if b.is_displayed() and any(k in b.text.lower() for k in ["change", "submit", "continue", "save", "update", "confirm", "xác nhận"]):
                            b.click()
                            submit_clicked = True
                            break
                    except: continue # Bỏ qua nếu button bị stale trong quá trình loop
                    
                    if time.time() - start_time > TIMEOUT:
                        raise Exception("TIMEOUT_CHANGE_PASSWORD: Button scanning loop")

            if not submit_clicked:
                 print("   [Step 2] Warning: No submit button clicked. Attempting Enter key on last input...")
                 visible_inputs[-1].send_keys(Keys.ENTER) # Backup cuối cùng

            print("   [Step 2] Submitted password change form.")
            
            # 5. Wait for finish (increased from 2s to 5s to allow page transition)
            time.sleep(5) 
            WebDriverWait(self.driver, 30).until(lambda d: d.execute_script("return document.readyState") == "complete")
            
            if time.time() - start_time > TIMEOUT:
                raise Exception("TIMEOUT_CHANGE_PASSWORD: End process exceeded time")

        except Exception as e:
            print(f"   [Step 2] Error handling password change: {e}")
            # Có thể thêm logic retry lại hàm này 1 lần nữa nếu cần thiết ở tầng gọi hàm

    def _check_verification_result(self):
        # Timeout protection for verification result (max 60s)
        # Optimized with JS checks to avoid hangs and speed up detection
        TIMEOUT = 20
        end_time = time.time() + TIMEOUT
        consecutive_failures = 0
        max_consecutive_failures = 20  # If JS fails 20 times in a row, consider timeout
        try:
            WebDriverWait(self.driver, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")
        except Exception as e:
            print(f"   [Step 2] Page not ready after 10s: {e}")
        while time.time() < end_time:
            try:
                
                
                #  Check your email or This email will replace all existing contact and login info on your account
                if self.driver.execute_script("return /check your email|this email will replace all existing contact and login info on your account/.test(document.body.innerText.toLowerCase())"):
                    return "CHECKPOINT_MAIL"
                
                if self.driver.execute_script("return /change password|new password|create a strong password|change your password to secure your account/.test(document.body.innerText.toLowerCase())"):
                    # nếu có new confirm new password thì require change password
                    if len(self.driver.execute_script("return Array.from(document.querySelectorAll('input[type=\"password\"]'));")) >= 2:
                        return "REQUIRE_PASSWORD_CHANGE"
                    else:
                        return "CHANGE_PASSWORD"
                
                if self.driver.execute_script("return /add phone number|send confirmation|log into another account/.test(document.body.innerText.toLowerCase())"):
                    return "SUSPENDED_PHONE"
                
                if self.driver.execute_script("return /select your birthday|add your birthday/.test(document.body.innerText.toLowerCase())"):
                    return "BIRTHDAY_SCREEN"
                
                if self.driver.execute_script("return /allow the use of cookies|posts|save your login info/.test(document.body.innerText.toLowerCase())"):
                    return "SUCCESS"
                
                if self.driver.execute_script("return /suspended|đình chỉ/.test(document.body.innerText.toLowerCase())"):
                    return "SUSPENDED"
                # some thing wrong 
                if self.driver.execute_script("return /something went wrong|đã xảy ra sự cố/.test(document.body.innerText.toLowerCase())"):
                    return "SOMETHING_WRONG"
                
                if self.driver.execute_script("return /sorry, there was a problem|please try again/.test(document.body.innerText.toLowerCase())"):
                    return "RETRY_UNUSUAL_LOGIN"
                
                # Check for wrong code
                if self.driver.execute_script("return /code isn't right| mã không đúng|incorrect|wrong code|invalid|the code you entered/.test(document.body.innerText.toLowerCase())"):
                    return "WRONG_CODE"
                
                if self.driver.execute_script("return /create a password at least 6 characters long|password must be at least 6 characters/.test(document.body.innerText.toLowerCase())"):
                    return "REQUIRE_PASSWORD_CHANGE"
                
                # enter your real birthday
                if self.driver.execute_script("return /enter your real birthday|nhập ngày sinh thật của bạn/.test(document.body.innerText.toLowerCase())"):
                    return "REAL_BIRTHDAY_REQUIRED"
                
                # use another profile va log into instagram => dang nhap lai voi data moi 
                if self.driver.execute_script("return /log into instagram|use another profile/.test(document.body.innerText.toLowerCase())"):
                    return "RETRY_UNUSUAL_LOGIN"  
                
                # URL checks
                # current_url = self.driver.current_url
                # if "instagram.com/" in current_url and "challenge" not in current_url:
                #     return "SUCCESS"
                
                # Element-based checks for logged in state
                if self.driver.execute_script("return /posts|followers|search|home/.test(document.body.innerText.toLowerCase())"):
                    return "LOGGED_IN_SUCCESS"
                
                if self.driver.execute_script("return /save your login info|we can save your login info|lưu thông tin đăng nhập/.test(document.body.innerText.toLowerCase())"):
                    return "LOGGED_IN_SUCCESS"
                
                # save info or not now
                if self.driver.execute_script("return document.querySelector('button[type=\"submit\"]') !== null && /save info|not now|để sau/.test(document.body.innerText.toLowerCase())"):
                    return "LOGGED_IN_SUCCESS"
                
                
                
                # Want to subscribe or continue
                if self.driver.execute_script("return /subscribe/.test(document.body.innerText.toLowerCase())"):
                    return "SUBSCRIBE_OR_CONTINUE"
                
                consecutive_failures = 0  # Reset on successful check
            except Exception as e:
                consecutive_failures += 1
                if consecutive_failures >= max_consecutive_failures:
                    print(f"   [Step 2] Too many JS failures in verification check: {e}")
                    break
            time.sleep(1.0)
        # Log current state for debugging timeout
        try:
            current_url = self.driver.current_url
            body_text = self.driver.find_element(By.TAG_NAME, "body").text[:500]  # First 500 chars
            print(f"   [Step 2] TIMEOUT reached. Current URL: {current_url}")
            print(f"   [Step 2] Page body preview: {body_text}...")
        except Exception as e:
            print(f"   [Step 2] Error logging timeout state: {e}")
        return "TIMEOUT"

    def _fill_input_with_delay(self, input_el, text_value):
        """Nhập text vào input với delay giữa mỗi ký tự để mô phỏng nhập thật."""
        val = str(text_value).strip()
        try:
            ActionChains(self.driver).move_to_element(input_el).click().perform()
            input_el.clear()
            for char in val:
                input_el.send_keys(char)
                time.sleep(0.1)  # Delay 0.1s giữa mỗi ký tự
            time.sleep(0.5)  # Chờ sau khi nhập xong
            return input_el.get_attribute("value") == val
        except Exception as e:
            print(f"   [Step 2] Input fill failed: {e}")
            return False