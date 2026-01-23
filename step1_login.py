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
        # Tối ưu: Kiểm tra nhanh nếu Input chưa xuất hiện thì mới tìm nút Switch
        # Dùng CSS gộp để check nhanh bất kỳ ô input nào
        input_check_css = "input[name='username'], input[name='email'], input[type='text']"
        
        if not wait_element(self.driver, By.CSS_SELECTOR, input_check_css, timeout=5):
            print("   [Step 1] Inputs not ready. Checking for 'Use another profile'...")
            xpath_switch = "//*[contains(text(), 'Use another profile') or contains(text(), 'Switch accounts')]"
            
            if wait_and_click(self.driver, By.XPATH, xpath_switch, timeout=5):
                print("   [Step 1] Clicked 'Switch'. Waiting for inputs...")
                # Chờ input xuất hiện sau khi click
                wait_element(self.driver, By.CSS_SELECTOR, input_check_css, timeout=5)

        # --- GIAI ĐOẠN 2: NHẬP USER (TỐI ƯU TỐC ĐỘ) ---
        # Thay vì loop từng selector, dùng 1 CSS Selector gộp để tìm TẤT CẢ cùng lúc.
        # Cái nào thấy trước thì lấy luôn -> Không bị delay timeout.
        # Ưu tiên name='email' (từ HTML bạn gửi) và name='username'
        print("   [Step 1] Entering Username...")
        user_css_group = "input[name='email'], input[name='username'], input[id^='_r_'][type='text']"
        
        user_input = wait_element(self.driver, By.CSS_SELECTOR, user_css_group, timeout=5)
        if user_input:
            try:
                user_input.clear()
                user_input.send_keys(username)
            except:
                print("   [Step 1] Retry sending username...")
                wait_and_send_keys(self.driver, By.CSS_SELECTOR, user_css_group, username)
        else:
            return "FAIL_FIND_INPUT_USER"

        # --- GIAI ĐOẠN 3: NHẬP PASSWORD (TỐI ƯU TỐC ĐỘ) ---
        # Tương tự, gộp name='pass' (HTML bạn gửi) và name='password'
        print("   [Step 1] Entering Password...")
        pass_css_group = "input[name='pass'], input[name='password'], input[id^='_r_'][type='password']"
        
        pass_input = wait_element(self.driver, By.CSS_SELECTOR, pass_css_group, timeout=5)
        if pass_input:
            try:
                pass_input.clear()
                pass_input.send_keys(password)
            except:
                 wait_and_send_keys(self.driver, By.CSS_SELECTOR, pass_css_group, password)
        else:
            return "FAIL_FIND_INPUT_PASS"

        # --- GIAI ĐOẠN 4: CLICK LOGIN ---
        print("   [Step 1] Clicking Login...")
        try:
            # Enter trên ô password là nhanh nhất
            pass_input.send_keys(Keys.ENTER)
        except:
            login_btn_xpath = "//button[@type='submit'] | //div[contains(text(), 'Log in')]"
            wait_and_click(self.driver, By.XPATH, login_btn_xpath)

        return self._wait_for_login_result(timeout=15)

    def _wait_for_login_result(self, timeout=15):
        """
        Vòng lặp kiểm tra trạng thái liên tục.
        Trả về kết quả ngay khi phát hiện trạng thái cụ thể.
        """
        print("   [Step 1] Waiting for login result...")
        end_time = time.time() + timeout
        
        while time.time() < end_time:
            status = self._detect_initial_status()
            
            # Nếu status đã rõ ràng (không phải Unknown/Retry) -> Return ngay
            if status not in ["LOGGED_IN_UNKNOWN_STATE", "LOGIN_FAILED_RETRY"]:
                return status
            
            time.sleep(0.5) # Poll nhẹ
            
        return "TIMEOUT_LOGIN_CHECK"

    def _detect_initial_status(self):
        """
        Quét DOM để xác định trạng thái sơ bộ sau khi nhấn Login.
        (GIỮ NGUYÊN TEXT LỖI TỪ BẢN GỐC)
        """
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
            
            # 1. Các trường hợp Exception / Checkpoint
            if "check your email" in body_text:
                return "CHECKPOINT_MAIL"
            
            # yêu cầu đổi mật khẩu 
            if "we noticed unusual activity" in body_text or "change your password" in body_text or "yêu cầu đổi mật khẩu" in body_text:
                return "REQUIRE_PASSWORD_CHANGE"
            
            if "unusual login" in body_text or "suspicious" in body_text:
                return "UNUSUAL_LOGIN"  
            
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

            # 2. Các trường hợp Thành công / Tiếp tục
            if "select your birthday" in body_text or "add your birthday" in body_text:
                return "BIRTHDAY_SCREEN"
            
            if "allow the use of cookies" in body_text:
                return "COOKIE_CONSENT"
            
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
            
            # We Detected An Unusual Login Attempt 
            if "we detected an unusual login attempt" in body_text or "get help logging in" in body_text:
                return "GET_HELP_LOG_IN"
            
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
            
            # Nếu không xác định được trạng thái, trả về Unknown State
            return "LOGGED_IN_UNKNOWN_STATE"

        except Exception as e:
            return f"ERROR_DETECT: {str(e)}"