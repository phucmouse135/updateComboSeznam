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
        start_time = time.time()
        # Max 30s for input to appear
        while time.time() - start_time < 30:
            if wait_element(self.driver, By.CSS_SELECTOR, input_check_css, timeout=3):
                break
            print("   [Step 1] Inputs not ready. Checking for 'Use another profile'...")
            xpath_switch = "//*[contains(text(), 'Use another profile') or contains(text(), 'Switch accounts')]"
            if wait_and_click(self.driver, By.XPATH, xpath_switch, timeout=3):
                print("   [Step 1] Clicked 'Switch'. Waiting for inputs...")
        else:
            return "FAIL_INPUT_TIMEOUT"

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

        # --- GIAI ĐOẠN 5: CHỜ KẾT QUẢ ---
        return self._wait_for_login_result(timeout=60)

    def _wait_for_login_result(self, timeout=120):
        print("   [Step 1] Waiting for login result...")
        
        # [QUAN TRỌNG] Ngủ 5s để trang web kịp load sau khi nhấn Login
        # Tránh trường hợp JS quét quá nhanh khi vẫn còn ở trang cũ
        time.sleep(5) 
        
        end_time = time.time() + timeout
        
        while time.time() < end_time:
            status = self._detect_initial_status()
            
            # [NEW] XỬ LÝ MÀN HÌNH "CHOOSE A WAY TO RECOVER" -> BẤM CONTINUE
            if status == "RECOVERY_CHALLENGE":
                print("   [Step 1] Detected Recovery Challenge. Clicking Continue...")
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
            
            time.sleep(1) 
            
        return "TIMEOUT_LOGIN_CHECK"

    def _detect_initial_status(self):
        """
        Quét DOM bằng JavaScript để xác định trạng thái.
        CAM KẾT: Giữ nguyên 100% text và status code từ bản gốc của bạn.
        """
        try:
            # Script JS tái hiện chính xác logic if/else của Python
            js_script = """
            var body = document.body.innerText.toLowerCase();
            
            // --- 1. RECOVERY & CHECKPOINT ---
            if (body.includes("choose a way to recover")) return "RECOVERY_CHALLENGE";
            
            if (body.includes("check your email") || body.includes(" we sent to the email address")) return "CHECKPOINT_MAIL";
            
            if (body.includes("log in on another device to continue") || body.includes("đăng nhập trên thiết bị khác để tiếp tục")) return "LOG_IN_ANOTHER_DEVICE";
            
            if (body.includes("your account has been disabled")) return "ACCOUNT_DISABLED";

            if (body.includes("add phone number to get back into instagram") || 
                body.includes("send confirmation") || 
                body.includes("log into another account") || 
                body.includes("we will send a confirmation code via sms to your phone.")) return "SUSPENDED_PHONE";
            
            if (body.includes("we noticed unusual activity") || 
                body.includes("change your password") || 
                body.includes("yêu cầu đổi mật khẩu")) return "REQUIRE_PASSWORD_CHANGE";
            
            if (body.includes("try another device") || 
                body.includes("try another device to continue") || 
                body.includes("can’t try another device?")) return "TRY_ANOTHER_DEVICE";

            if (body.includes("suspended") || body.includes("đình chỉ")) return "SUSPENDED";

            // --- 2. LOGIN FAILURES ---
            if (body.includes("the login information you entered is incorrect") || 
                body.includes("incorrect username or password") || 
                body.includes("thông tin đăng nhập bạn đã nhập không chính xác")) return "LOGIN_FAILED_INCORRECT";
            
            if (body.includes("something went wrong")) return "LOGIN_FAILED_SOMETHING_WENT_WRONG";

            // --- 3. SUCCESS / INTERMEDIATE STEPS ---
            if (body.includes("select your birthday") || body.includes("add your birthday")) return "BIRTHDAY_SCREEN";
            
            if (body.includes("check your text messages") || body.includes("kiểm tra tin nhắn văn bản của bạn")) return "2FA_TEXT_MESSAGE";
            
            if (body.includes("allow the use of cookies")) return "COOKIE_CONSENT";
            
            if (body.includes("help us confirm it's you") || body.includes("xác nhận đó là bạn")) return "CONFIRM_YOUR_IDENTITY";
            
            // Success Check 1
            if (body.includes("posts") || body.includes("followers") || body.includes("search") || body.includes("home")) return "LOGGED_IN_SUCCESS";
            
            // Success Check 2
            if (body.includes("save your login info?") || 
                body.includes("we can save your login info on this browser so you don't need to enter it again.") || 
                body.includes("lưu thông tin đăng nhập của bạn")) return "LOGGED_IN_SUCCESS";

            // --- 4. 2FA SPECIFIC (Giữ nguyên text bạn yêu cầu) ---
            // Text: "authentication app" -> Status: "2FA_SMS" (Theo đúng code gốc của bạn)
            if (body.includes("mã đăng nhập 6 chữ số được tạo bởi ứng dụng xác thực") || 
                body.includes("enter a 6-digit login code generated by an authentication app.")) return "2FA_SMS";
            
            if (body.includes("check your whatsapp messages") || body.includes("kiểm tra tin nhắn whatsapp của bạn")) return "2FA_WHATSAPP";
            
            if (body.includes("confirm your info on the app")) return "2FA_APP";
            
            if (body.includes("use another profile") || body.includes("log into instagram")) return "FAIL_LOGIN_REDIRECTED_TO_PROFILE_SELECTION";

            // Retry Check (Input password còn tồn tại)
            if (document.querySelectorAll("input[type='password']").length > 0) return "LOGIN_FAILED_RETRY";

            if (body.includes("check your notifications") || 
                body.includes("xem thông báo của bạn") || 
                body.includes("check your notifications there and approve the login to continue.")) return "2FA_NOTIFICATIONS";
            
            // Help Log In (Đặt cuối để tránh nhận diện nhầm với các lỗi khác)
            if (body.includes("you need to request help logging in") || 
                body.includes("to secure your account, you need to request help logging in")) return "GET_HELP_LOG_IN";
            
            // Unusual Login Attempt
            if (body.includes("we detected an unusual login attempt") || 
                body.includes("to secure your account, we'll send you a security code.")) return "CONTINUE_UNUSUAL_LOGIN";

            // --- 5. BỔ SUNG: CONTENT UNAVAILABLE (Chỉ thêm mới để fix lỗi popup trắng, không sửa code cũ) ---
            if (body.includes("content is no longer available")) return "CONTENT_UNAVAILABLE";

            return "LOGGED_IN_UNKNOWN_STATE";
            """
            return self.driver.execute_script(js_script)
        except Exception as e:
            return f"ERROR_DETECT_EXCEPTION: {str(e)}"