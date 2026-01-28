# step1_login.py
import json
import time
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from config_utils import wait_element, wait_and_click, wait_and_send_keys, wait_dom_ready

class InstagramLoginStep:
    def __init__(self, driver):
        self.driver = driver
        self.base_url = "https://www.instagram.com/"

    def load_base_cookies(self, json_path):
        """
        Nạp cookie mồi từ file JSON để giả lập thiết bị cũ/phiên làm việc cũ.
        Tối ưu: Sử dụng wait_dom_ready thay vì time.sleep.
        """
        if not os.path.exists(json_path):
            print(f"   [Step 1] Warning: Cookie file {json_path} not found.")
            return False

        try:
            print("   [Step 1] Loading base cookies...")
            self.driver.get(self.base_url) # Truy cập lần 1 để nhận domain
            
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                cookies = data.get("cookies", [])
            
            for cookie in cookies:
                cookie_dict = {
                    'name': cookie.get('name'),
                    'value': cookie.get('value'),
                    'domain': cookie.get('domain', '.instagram.com'),
                    'path': cookie.get('path', '/'),
                    'secure': cookie.get('secure', True)
                }
                if 'expirationDate' in cookie:
                    cookie_dict['expiry'] = int(cookie['expirationDate'])
                try: self.driver.add_cookie(cookie_dict)
                except: pass
            
            self.driver.refresh()
            # TỐI ƯU: Chờ DOM load xong thay vì ngủ cứng 3s
            wait_dom_ready(self.driver, timeout=10)
            return True
        except Exception as e:
            print(f"   [Step 1] Error loading cookies: {e}")
            return False

    def perform_login(self, username, password):
        print(f"   [Step 1] Login as {username}...")

        # --- GIAI ĐOẠN 1: CHỌN "USE ANOTHER PROFILE" ---
        input_check_css = "input[name='username'], input[name='email'], input[type='text']"
        attempts = 0
        max_attempts = 2
        timeout = 30
        while attempts < max_attempts:
            start_time = time.time()
            while time.time() - start_time < timeout:
                if wait_element(self.driver, By.CSS_SELECTOR, input_check_css, timeout=3):
                    break
                print("   [Step 1] Inputs not ready. Checking for 'Use another profile'...")
                xpath_switch = "//*[contains(text(), 'Use another profile') or contains(text(), 'Switch accounts') or contains(text(), 'Use another account')]"
                if wait_and_click(self.driver, By.XPATH, xpath_switch, timeout=3):
                    print("   [Step 1] Clicked 'Switch'. Waiting for inputs...")
            else:
                if attempts < max_attempts - 1:
                    print("   [Step 1] Refreshing page to retry finding inputs...")
                    self.driver.refresh()
                    wait_dom_ready(self.driver, timeout=10)
                    attempts += 1
                    continue
                else:
                    return "FAIL_INPUT_TIMEOUT"
            break

        # --- GIAI ĐOẠN 2: NHẬP USER (TỐI ƯU TỐC ĐỘ) ---
        print("   [Step 1] Entering Username...")
        user_css_group = "input[name='email'], input[name='username'], input[id^='_r_'][type='text']"
        user_start = time.time()
        # Max 30s for user input
        while time.time() - user_start < 30:
            user_input = wait_element(self.driver, By.CSS_SELECTOR, user_css_group, timeout=3)
            if user_input:
                try:
                    user_input.clear()
                    user_input.send_keys(username)
                except:
                    print("   [Step 1] Retry sending username...")
                    wait_and_send_keys(self.driver, By.CSS_SELECTOR, user_css_group, username)
                break
            time.sleep(1)
        else:
            return "FAIL_FIND_INPUT_USER_TIMEOUT"

        # --- GIAI ĐOẠN 3: NHẬP PASSWORD (TỐI ƯU TỐC ĐỘ) ---
        print("   [Step 1] Entering Password...")
        pass_css_group = "input[name='pass'], input[name='password'], input[id^='_r_'][type='password']"
        pass_start = time.time()
        # Max 30s for password input
        while time.time() - pass_start < 30:
            pass_input = wait_element(self.driver, By.CSS_SELECTOR, pass_css_group, timeout=3)
            if pass_input:
                try:
                    pass_input.clear()
                    pass_input.send_keys(password)
                except:
                    wait_and_send_keys(self.driver, By.CSS_SELECTOR, pass_css_group, password)
                break
            time.sleep(1)
        else:
            return "FAIL_FIND_INPUT_PASS_TIMEOUT"

        # --- GIAI ĐOẠN 4: CLICK LOGIN ---
        print("   [Step 1] Clicking Login...")
        login_start = time.time()
        # Max 15s for login button
        while time.time() - login_start < 15:
            try:
                pass_input.send_keys(Keys.ENTER)
                break
            except:
                login_btn_xpath = "//button[@type='submit'] | //div[contains(text(), 'Log in')]"
                if wait_and_click(self.driver, By.XPATH, login_btn_xpath, timeout=3):
                    break
            time.sleep(1)
        else:
            return "FAIL_LOGIN_BUTTON_TIMEOUT"

        status = self._wait_for_login_result(timeout=120)
        wait_dom_ready(self.driver , timeout=10)
        time.sleep(2)
        print(f"   [Step 1] Login result detected: {status}")
        return status

    # def _wait_for_login_result(self, timeout=120):
    #     """
    #     Vòng lặp kiểm tra trạng thái liên tục.
    #     Trả về kết quả ngay khi phát hiện trạng thái cụ thể.
    #     """
    #     print("   [Step 1] Waiting for login result...")
    #     end_time = time.time() + timeout
        
    #     while time.time() < end_time:
    #         status = self._detect_initial_status()
            
    #         # Nếu status đã rõ ràng (không phải Unknown/Retry) -> Return ngay
    #         if status not in ["LOGGED_IN_UNKNOWN_STATE", "LOGIN_FAILED_RETRY"]:
    #             return status
            
    #         time.sleep(0.5) # Poll nhẹ
            
    #     return "TIMEOUT_LOGIN_CHECK"

    def _wait_for_login_result(self, timeout=120):
        print("   [Step 1] Waiting for login result...")
        end_time = time.time() + timeout
        
        while time.time() < end_time:
            status = self._detect_initial_status()
            
            # [NEW] XỬ LÝ MÀN HÌNH "CHOOSE A WAY TO RECOVER" -> BẤM CONTINUE
            if status == "RECOVERY_CHALLENGE":
                print("   [Step 1] Detected Recovery Challenge. Clicking Continue...")
                # Tìm nút Continue (Quét nhiều selector cho chắc)
                continue_xpaths = [
                    "//div[contains(text(), 'Continue')]", 
                    "//span[contains(text(), 'Continue')]",
                    "//button[contains(text(), 'Continue')]",
                    "//div[text()='Continue']" 
                ]
                clicked = False
                for xp in continue_xpaths:
                    if wait_and_click(self.driver, By.XPATH, xp, timeout=2):
                        clicked = True
                        break
                
                if clicked:
                    print("   [Step 1] Clicked Continue. Waiting for next step...")
                    time.sleep(5) # Chờ load sau khi bấm
                    continue # Quay lại đầu vòng lặp để check trạng thái mới
            
            # Nếu status đã rõ ràng (không phải Unknown/Retry) -> Return ngay
            if status not in ["LOGGED_IN_UNKNOWN_STATE", "LOGIN_FAILED_RETRY", "RECOVERY_CHALLENGE"]:
                return status
            
            time.sleep(0.5) 
            
        return "TIMEOUT_LOGIN_CHECK"
    def _detect_initial_status(self):
        """
        Quét DOM để xác định trạng thái sơ bộ sau khi nhấn Login.
        (GIỮ NGUYÊN TEXT LỖI TỪ BẢN GỐC)
        """
        try:
            wait_dom_ready(self.driver, timeout=10)
            body_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
            
            if "choose a way to recover" in body_text:
                return "RECOVERY_CHALLENGE"
            # 1. Các trường hợp Exception / Checkpoint
            if "check your email" in body_text or " we sent to the email address" in body_text:
                return "CHECKPOINT_MAIL"
            
            # Enter the 6-digit code we sent to the number ending in
            if "enter the 6-digit code we sent to the number ending in" in body_text:
                return "CHECKPOINT_PHONE"
            
            # Log in on another device to continue
            if "log in on another device to continue" in body_text or "đăng nhập trên thiết bị khác để tiếp tục" in body_text:
                return "LOG_IN_ANOTHER_DEVICE"
            
            if "add phone number to get back into instagram" in body_text or "send confirmation" in body_text or "log into another account" in body_text or "we will send a confirmation code via sms to your phone." in body_text: 
                return "SUSPENDED_PHONE"
            
            # yêu cầu đổi mật khẩu 
            if "we noticed unusual activity" in body_text or "change your password" in body_text or "yêu cầu đổi mật khẩu" in body_text:
                return "REQUIRE_PASSWORD_CHANGE"
            
            # Nếu đã vào trong (có Post/Follower/Nav bar)
            if "posts" in body_text or "followers" in body_text or "search" in body_text or "home" in body_text:
                return "LOGGED_IN_SUCCESS"

            if("save your login info?" in body_text or "we can save your login info on this browser so you don't need to enter it again." in body_text or "lưu thông tin đăng nhập của bạn" in body_text or "save info" in body_text):
                return "LOGGED_IN_SUCCESS"
            
            try:
                wait_dom_ready(self.driver, timeout=10)
                start_time = time.time()
                last_url = self.driver.current_url
                while True:
                    body_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
                    current_url = self.driver.current_url

                    # you need to request help logging in To secure your account, you need to request help logging in
                    if "you need to request help logging in" in body_text or "to secure your account, you need to request help logging in" in body_text:
                        return "GET_HELP_LOG_IN"
                    
                    
                    # We Detected An Unusual Login Attempt 
                    if ("we detected an unusual login attempt" in body_text or "to secure your account, we'll send you a security code." in body_text) :
                        if "email" in body_text or "mail" in body_text:            
                            return "CONTINUE_UNUSUAL_LOGIN"
                        return "CONTINUE_UNUSUAL_LOGIN_PHONE"
                
                    if "choose a way to recover" in body_text:
                        return "RECOVERY_CHALLENGE"
                    # 1. Các trường hợp Exception / Checkpoint
                    if "check your email" in body_text or " we sent to the email address" in body_text:
                        return "CHECKPOINT_MAIL"

                    # Log in on another device to continue
                    if "log in on another device to continue" in body_text or "đăng nhập trên thiết bị khác để tiếp tục" in body_text:
                        return "LOG_IN_ANOTHER_DEVICE"
                    
                    # your account has been disabled
                    if "your account has been disabled" in body_text:
                        return "ACCOUNT_DISABLED"

                    if "add phone number to get back into instagram" in body_text or "send confirmation" in body_text or "log into another account" in body_text or "we will send a confirmation code via sms to your phone." in body_text: 
                        return "SUSPENDED_PHONE"

                    # yêu cầu đổi mật khẩu 
                    if "we noticed unusual activity" in body_text or "change your password" in body_text or "yêu cầu đổi mật khẩu" in body_text:
                        return "REQUIRE_PASSWORD_CHANGE"

                    # Try another device to continue
                    if "try another device" in body_text or "try another device to continue" in body_text or "can’t try another device?" in body_text:
                        return "TRY_ANOTHER_DEVICE"

                    if "suspended" in body_text or "đình chỉ" in body_text:
                        return "SUSPENDED"

                    # The login information you entered is incorrect
                    if "the login information you entered is incorrect" in body_text or \
                       "incorrect username or password" in body_text or \
                        "thông tin đăng nhập bạn đã nhập không chính xác" in body_text:
                        return "LOGIN_FAILED_INCORRECT"
                    # Something went wrong
                    if "something went wrong" in body_text or "something went wrong" in body_text:
                        return "LOGIN_FAILED_SOMETHING_WENT_WRONG"

                    # 2. Các trường hợp Thành công / Tiếp tục
                    if "select your birthday" in body_text or "add your birthday" in body_text:
                        return "BIRTHDAY_SCREEN"

                    # 
                    # check your text messages
                    if "check your text messages" in body_text or "kiểm tra tin nhắn văn bản của bạn" in body_text:
                        return "2FA_TEXT_MESSAGE"
                    
                    if "allow the use of cookies" in body_text:
                        return "COOKIE_CONSENT"
                    
                    # Help us confirm it's you
                    if "help us confirm it's you" in body_text or "xác nhận đó là bạn" in body_text:
                        return "CONFIRM_YOUR_IDENTITY"

                    # Nếu đã vào trong (có Post/Follower/Nav bar)
                    if "posts" in body_text or "followers" in body_text or "search" in body_text or "home" in body_text:
                        return "LOGGED_IN_SUCCESS"

                    if("save your login info?" in body_text or "we can save your login info on this browser so you don't need to enter it again." in body_text or "lưu thông tin đăng nhập của bạn" in body_text):
                        return "LOGGED_IN_SUCCESS"

                    # SMS 2FA screen "Enter a 6-digit login code generated by an authentication app." or vietnamese
                    if "mã đăng nhập 6 chữ số được tạo bởi ứng dụng xác thực" in body_text or "enter a 6-digit login code generated by an authentication app." in body_text:
                        return "2FA_SMS"

                    # Check your WhatsApp messages 
                    if "check your whatsapp messages" in body_text or "kiểm tra tin nhắn whatsapp của bạn" in body_text:
                        return "2FA_WHATSAPP"


                    # Confirm your info on the app 
                    if "confirm your info on the app" in body_text:
                        return "2FA_APP"

                    # Use another profile => Văng về chọn tài khoản
                    if "use another profile" in body_text or "Log into Instagram" in body_text:
                        return "FAIL_LOGIN_REDIRECTED_TO_PROFILE_SELECTION"

                    # Nếu vẫn còn ô password -> Login chưa qua (có thể đang loading)
                    if len(self.driver.find_elements(By.CSS_SELECTOR, "input[type='password']")) > 0:
                        return "LOGIN_FAILED_RETRY"

                    # Check your notifications  && Check your notifications there and approve the login to continue.
                    if "check your notifications" in body_text or "xem thông báo của bạn" in body_text or "check your notifications there and approve the login to continue." in body_text:
                        return "2FA_NOTIFICATIONS"

                    # Nếu không xác định được trạng thái, kiểm tra loading hoặc url đứng yên
                    loading_selectors = [
                        "div[role='progressbar']", "div[aria-busy='true']", "._ab8w", ".loading-spinner", "[data-testid='loading-indicator']"
                    ]
                    loading_found = False
                    for sel in loading_selectors:
                        try:
                            if len(self.driver.find_elements(By.CSS_SELECTOR, sel)) > 0:
                                loading_found = True
                                break
                        except:
                            pass

                    # Nếu có loading hoặc url không đổi thì tiếp tục chờ
                    if loading_found or current_url == last_url:
                        if time.time() - start_time > 120:
                            break
                        time.sleep(1)
                        last_url = current_url
                        continue

                    # Nếu không xác định được trạng thái, trả về Unknown State
                    break
                return "LOGGED_IN_UNKNOWN_STATE"
            except Exception as e:
                return f"ERROR_DETECT: {str(e)}" 
        except Exception as e:
            return f"ERROR_DETECT_EXCEPTION: {str(e)}"
        
    