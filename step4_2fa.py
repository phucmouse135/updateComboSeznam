# step4_2fa.py
import time
import re
import pyotp
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from config_utils import wait_dom_ready, wait_element, wait_and_click

# Import Mail Handler đã tối ưu (đây là phần duy nhất được tách ra)
from mail_handler_v2 import get_2fa_code_v2

class Instagram2FAStep:
    def __init__(self, driver):
        self.driver = driver
        self.target_url = "https://accountscenter.instagram.com/password_and_security/two_factor/"

    def setup_2fa(self, gmx_user, gmx_pass,target_username,  linked_mail=None):
        """
        Setup 2FA Flow - Logic gốc được giữ nguyên 100%.
        """
        print(f"   [Step 4] Accessing settings...")
        print(f"   [Step 4] Starting 2FA Setup for {target_username}...")
        self.driver.get(self.target_url)
        wait_dom_ready(self.driver, timeout=5)

        # --- 0. BYPASS 'DOWNLOAD APP' PAGE ---
        self._bypass_lite_page()

        # -------------------------------------------------
        # STEP 1: SELECT ACCOUNT
        # -------------------------------------------------
        print(f"   [Step 4] Step 1: Selecting Account for {target_username}...")
        self._select_account_center_profile()

        # -------------------------------------------------
        # STEP 2: SCAN STATE & HANDLE EXCEPTIONS
        # -------------------------------------------------
        print("   [Step 4] Scanning UI State...")
        state = "UNKNOWN"
        
        # Quét 15 lần như file gốc để bắt được trạng thái chính xác
        for _ in range(15):
            state = self._get_page_state()
            
            # UNUSUAL LOGIN FIX
            if state == 'UNUSUAL_LOGIN':
                print("   [Step 4] Detected 'Unusual Login'. Clicking 'This Was Me'...")
                if self._click_continue_robust():
                    print("   [Step 4] Clicked 'This Was Me'. Waiting...")
                    wait_dom_ready(self.driver, timeout=5)
                    if "two_factor" not in self.driver.current_url:
                        self.driver.get(self.target_url)
                        wait_dom_ready(self.driver, timeout=5)
                continue 

            if state == 'LITE_PAGE': 
                self.driver.get(self.target_url)
                wait_dom_ready(self.driver, timeout=5)
                continue
            
            # BLOCK UNSUPPORTED METHODS
            if state == 'WHATSAPP_REQUIRED': raise Exception("STOP_FLOW_2FA: WhatsApp Verification Required")
            if state == 'SMS_REQUIRED': raise Exception("STOP_FLOW_2FA: SMS Verification Required")
            
            # Thoát vòng lặp nếu trạng thái đã rõ ràng
            if state in ['SELECT_APP', 'CHECKPOINT', 'ALREADY_ON', 'RESTRICTED', 'OTP_INPUT_SCREEN']: 
                break
            
            time.sleep(0.5)

        print(f"   [Step 4] Detected State: {state}")

        if state == 'RESTRICTED': raise Exception("STOP_FLOW_2FA: RESTRICTED_DEVICE")
        if state == 'SUSPENDED': raise Exception("STOP_FLOW_2FA: ACCOUNT_SUSPENDED")
        if state == 'ALREADY_ON': 
            print("   [Step 4] 2FA is already ON.")
            return "ALREADY_2FA_ON"

        # -------------------------------------------------
        # STEP 2.5: HANDLE CHECKPOINT (INTERNAL)
        # -------------------------------------------------
        if state == 'CHECKPOINT':
            print(f"   [Step 4] Step 2.5: Handling Internal Checkpoint...")
            
            # Validate Mask
            if not self._validate_masked_email_robust(gmx_user, linked_mail):
                print("   [STOP] Script halted: Targeted email is not yours.")
                raise Exception("STOP_FLOW_2FA: EMAIL_MISMATCH") 
            
            # Giải Checkpoint
            self._solve_internal_checkpoint(gmx_user, gmx_pass, target_username)
            
            # Scan lại trạng thái sau khi giải
            state = self._get_page_state()

        # -------------------------------------------------
        # STEP 3: SELECT AUTH APP
        # -------------------------------------------------
        print("   [Step 4] Step 3: Selecting Auth App...")
        self._select_auth_app_method(state)

        # -------------------------------------------------
        # STEP 4: GET SECRET KEY (CHỐT CHẶN CỨNG - KHÔNG SKIP)
        # -------------------------------------------------
        wait_dom_ready(self.driver, timeout=5)
        print("   [Step 4] Step 4: Getting Secret Key (Blocking until captured)...")
        
        # Hàm này chứa vòng lặp while True và logic Back nếu lỡ skip
        secret_key = self._extract_secret_key()
        
        # IN KEY KIỂM SOÁT
        print(f"\n========================================\n[Step 4] !!! SECRET KEY FOUND: {secret_key}\n========================================\n")

        # -------------------------------------------------
        # STEP 5: CONFIRM OTP (FIXED INPUT)
        # -------------------------------------------------
        
        # 1. Click Next từ màn hình Copy Key
        print("   [Step 4] Clicking Next to Input OTP...")
        self._click_continue_robust()
        
        # 2. Tính toán OTP
        clean_key = "".join(secret_key.split())
        totp = pyotp.TOTP(clean_key, interval=30)
        otp_code = totp.now()
        
        # 3. Chờ ô Input xuất hiện
        print(f"   [Step 4] Waiting for OTP Input (Code: {otp_code})...")
        
        # 4. ĐIỀN OTP BẰNG HÀM ROBUST (Thử lại 10s)
        is_filled = False
        fill_end = time.time() + 10 
        while time.time() < fill_end:
            if self._robust_fill_input(otp_code):
                is_filled = True
                break
            print("   [Step 4] Retrying input fill...")
            time.sleep(1)
            
        if not is_filled: raise Exception("STOP_FLOW_2FA: OTP_INPUT_FAIL")
        
        print(f"   [Step 4] Input Filled. Confirming...")
        
        # 5. Confirm
        time.sleep(0.5)
        self._click_continue_robust()
        
        print("   [Step 4] Waiting for completion...")
        end_confirm = time.time() + 15
        success = False
        
        while time.time() < end_confirm:
            res = self.driver.execute_script("""
                var body = document.body.innerText.toLowerCase();
                if (body.includes("code isn't right") || body.includes("mã không đúng")) return 'WRONG_OTP';
                
                var doneBtns = document.querySelectorAll("span, div[role='button']");
                for(var b of doneBtns) {
                    if((b.innerText === 'Done' || b.innerText === 'Xong') && b.offsetParent !== null) {
                        b.click(); return 'SUCCESS';
                    }
                }
                if (body.includes("authentication is on")) return 'SUCCESS';
                return 'WAIT';
            """)
            
            if res == 'WRONG_OTP': 
                raise Exception("STOP_FLOW_2FA: OTP_REJECTED")
            if res == 'SUCCESS' or self._get_page_state() == 'ALREADY_ON': 
                success = True
                print("   [Step 4] => SUCCESS: 2FA Enabled.")
                break
            time.sleep(1)

        if not success: raise Exception("STOP_FLOW_2FA: TIMEOUT (Done button not found)")
        time.sleep(1)
        return secret_key

    # ==========================================
    # CORE HELPERS (GIỮ NGUYÊN TỪ two_fa_handler.py)
    # ==========================================

    def _bypass_lite_page(self):
        if "lite" in self.driver.current_url or len(self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Download Instagram Lite')]")) > 0:
            print("   [Step 4] Detected 'Download Lite' page. Attempting bypass...")
            try:
                btns = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Not now') or contains(text(), 'Lúc khác')]")
                if btns: 
                    btns[0].click()
                    wait_dom_ready(self.driver, timeout=5)
                else: 
                    self.driver.get(self.target_url)
                    wait_dom_ready(self.driver, timeout=5)
            except: pass

    def _select_account_center_profile(self):
        acc_selected = False
        for attempt in range(3):
            try:
                wait_element(self.driver, By.XPATH, "//div[@role='button'] | //a[@role='link']", timeout=5)
                clicked = self.driver.execute_script("""
                    var els = document.querySelectorAll('div[role="button"], a[role="link"]');
                    for (var i=0; i<els.length; i++) {
                        if (els[i].innerText.toLowerCase().includes('instagram')) { els[i].click(); return true; }
                    }
                    return false;
                """)
                if clicked: 
                    acc_selected = True
                    wait_dom_ready(self.driver, timeout=5)
                    break
                else:
                    time.sleep(1)
            except: time.sleep(1)
        if not acc_selected: print("   [Step 4] Warning: Select Account failed (May already be inside).")

    def _get_page_state(self):
        """
        Quét toàn bộ Body để xác định trạng thái hiện tại. (JS Sensor Gốc)
        """
        js_sensor = """
        function checkState() {
            var body = document.body.innerText.toLowerCase();
            var url = window.location.href;

            if (body.includes("download instagram lite") || url.includes("lite") || body.includes("download apk")) {
                return 'LITE_PAGE';
            }

            if (body.includes("unusual login") || body.includes("suspicious login") || (body.includes("this was me") && body.includes("this wasn't me"))) {
                return 'UNUSUAL_LOGIN';
            }
            
            if (body.includes("you can't make this change") || body.includes("change at the moment")) return 'RESTRICTED';
            if (body.includes("suspended") || body.includes("đình chỉ")) return 'SUSPENDED';
            if (body.includes("sorry, this page isn't available")) return 'BROKEN';

            if (body.includes("authentication is on") || body.includes("xác thực 2 yếu tố đang bật")) {
                 return 'ALREADY_ON';
            }
            
            if (body.includes("help protect your account") || body.includes("authentication app") || body.includes("ứng dụng xác thực")) {
                 return 'SELECT_APP';
            }

            if (body.includes("check your whatsapp") || body.includes("whatsapp account")) return 'WHATSAPP_REQUIRED';
            if (body.includes("check your sms") || body.includes("text message")) return 'SMS_REQUIRED';

            var inputs = document.querySelectorAll("input");
            for (var i=0; i<inputs.length; i++) {
                if (inputs[i].offsetParent !== null) {
                    var attr = (inputs[i].name + " " + inputs[i].placeholder + " " + inputs[i].getAttribute("aria-label")).toLowerCase();
                    if (attr.includes("code") || attr.includes("security") || inputs[i].type === "tel" || inputs[i].type === "number") {
                        return 'CHECKPOINT';
                    }
                }
            }
            
            if (body.includes("check your email") || body.includes("enter the code")) return 'CHECKPOINT';

            var hasInput = document.querySelector("input[name='code']") || document.querySelector("input[placeholder*='Code']");
            var hasNext = false;
            var btns = document.querySelectorAll("button, div[role='button']");
            for (var b of btns) { if (b.innerText.toLowerCase().includes("next") || b.innerText.toLowerCase().includes("tiếp")) hasNext = true; }

            if (hasInput && body.includes("authentication app") && hasNext) return 'OTP_INPUT_SCREEN';
            return 'UNKNOWN';
        }
        return checkState();
        """
        try: return self.driver.execute_script(js_sensor)
        except: return 'UNKNOWN'

    def _solve_internal_checkpoint(self, gmx_user, gmx_pass, target_ig_username):
        """
        Giải Checkpoint nội bộ.
        Cơ chế: Nếu nhập mã bị báo sai (do mail cũ), sẽ bấm gửi lại và chờ để lấy mã mới.
        """
        """Giải Checkpoint nội bộ (Step 4)."""
        print(f"   [Step 4] Solving Internal Checkpoint for {target_ig_username}...")
        checkpoint_passed = False
        
        for mail_attempt in range(1, 4):
            print(f"   [Step 4] Mail Retrieval Attempt {mail_attempt}/3...")
            
            # [UPDATE] Gọi hàm get_2fa_code_v2 với target_username
            # Hàm này sẽ tìm mail có subject 'Authenticate...' và chứa 'target_username'
            code = get_2fa_code_v2(gmx_user, gmx_pass, target_ig_username)
            
            if not code:
                # ... (Logic xử lý không thấy code giữ nguyên: Check State -> Click Get New -> Wait 5s) ...
                if self._get_page_state() in ['SELECT_APP', 'ALREADY_ON']: 
                    checkpoint_passed = True; break
                
                print("   [Step 4] Code not found. Clicking 'Get new code'...")
                self.driver.execute_script("var a=document.querySelectorAll('span, div[role=\"button\"]'); for(var e of a){if(e.innerText.toLowerCase().includes('get a new code')){e.click();break;}}")
                time.sleep(5) 
                continue 

            print(f"   [Step 4] Inputting Code: {code}")
            
            # 2. Nhập Code
            print(f"   [Step 4] Inputting Code: {code}")
            if self._robust_fill_input(code):
                self._click_continue_robust()
                
                # 3. Kiểm tra kết quả nhập
                is_wrong_code = False
                print("   [Step 4] Verifying...")
                time.sleep(2)

                # Thử xác nhận nhiều lần nếu chưa verify
                verify_attempts = 0
                while verify_attempts < 8:
                    time.sleep(1)
                    curr = self._get_page_state()
                    # Nếu qua ải thành công
                    if curr in ['SELECT_APP', 'ALREADY_ON']:
                        checkpoint_passed = True
                        print("   [Step 4] Checkpoint Passed!")
                        break
                    # Nếu báo Lỗi Mã (Đây là chỗ phát hiện đọc nhầm mail cũ)
                    err_msg = self.driver.execute_script("return document.body.innerText.toLowerCase()")
                    if "isn't right" in err_msg or "không đúng" in err_msg or "incorrect" in err_msg:
                        print(f"   [WARNING] Code {code} REJECTED (Likely old email).")
                        is_wrong_code = True
                        break
                    # Nếu chưa verify, thử lại thao tác xác nhận
                    print("   [Step 4] Not verified yet, retrying confirm...")
                    self._click_continue_robust()
                    verify_attempts += 1

                if checkpoint_passed:
                    break

                # NẾU MÃ SAI -> KÍCH HOẠT QUY TRÌNH LẤY LẠI
                if is_wrong_code:
                    print("   [Step 4] Triggering NEW code & Waiting 5s for delivery...")
                    # A. Bấm nút "Get a new code"
                    self.driver.execute_script("var a=document.querySelectorAll('span, div[role=\"button\"]'); for(var e of a){if(e.innerText.toLowerCase().includes('get a new code')){e.click();break;}}")
                    # B. Chờ 5s (Thời gian vàng để mail mới đè lên mail cũ)
                    time.sleep(5)
                    # C. Xóa ô nhập liệu cũ để chuẩn bị nhập lại
                    try:
                        input_el = self.driver.find_element(By.CSS_SELECTOR, "input[name='code'], input[placeholder*='Code']")
                        input_el.send_keys(Keys.CONTROL + "a")
                        input_el.send_keys(Keys.DELETE)
                    except: pass
                    # D. Quay lại đầu vòng lặp -> Gọi lại get_instagram_code_strict
                    # Lúc này mail mới đã về, ID cao hơn nên sẽ được lấy đúng.
                    continue
            else:
                time.sleep(1)
        
        if not checkpoint_passed: 
            raise Exception("STOP_FLOW_2FA: Checkpoint Failed after retries")

    def _select_auth_app_method(self, current_state):
        app_selected = False
        for attempt in range(3):
            try:
                if self._get_page_state() == 'ALREADY_ON': 
                    return
                
                self.driver.execute_script("""
                    var els = document.querySelectorAll("div[role='button'], label");
                    for (var i=0; i<els.length; i++) {
                         if (els[i].innerText.toLowerCase().includes("authentication app")) { els[i].click(); break; }
                    }
                """)
                time.sleep(1)
                self._click_continue_robust()
                time.sleep(4)
                
                if self._get_page_state() == 'ALREADY_ON': return
                if len(self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Copy key') or contains(text(), 'Sao chép')]")) > 0:
                    app_selected = True
                    break
            except: time.sleep(1)
    
        if not app_selected:
            if self._get_page_state() == 'ALREADY_ON': return
            # Nếu chưa thấy Copy Key, có thể do chưa vào được màn hình đó
            # Code gốc của bạn check rất kỹ ở đây, nếu không thấy key là báo lỗi
            if len(self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Copy key')]")) == 0:
                 # Thử chờ thêm chút
                 pass

    def _extract_secret_key(self):
        """Lấy Secret Key (Logic Blocking + Auto Back)."""
        secret_key = ""
        end_wait = time.time() + 60
        while time.time() < end_wait:
            try:
                current_state = self._get_page_state()
                if current_state == 'ALREADY_ON': return "ALREADY_2FA_ON"
                
                self.driver.execute_script("var els=document.querySelectorAll('span, div[role=\"button\"]'); for(var e of els){if(e.innerText.includes('Copy key')||e.innerText.includes('Sao chép')){e.click();break;}}")
                
                # 1. Tự sửa lỗi nếu bị nhảy sang màn OTP quá sớm mà chưa có Key (Code gốc)
                if current_state == 'OTP_INPUT_SCREEN' and not secret_key:
                    print("   [Step 4] Warning: Skiped to OTP screen! Clicking Back...")
                    self.driver.execute_script("var b = document.querySelector('div[role=\"button\"] svg'); if(b) b.closest('div[role=\"button\"]').click();")
                    time.sleep(1)
                    continue

                # 2. Quét mã từ Text Body
                full_text = self.driver.find_element(By.TAG_NAME, "body").text
                m = re.search(r'([A-Z2-7]{4}\s?){4,}', full_text) 
                if m:
                    clean = m.group(0).replace(" ", "").strip()
                    if len(clean) >= 16: secret_key = clean; break
                
                # 3. Quét mã từ các Input ẩn
                if not secret_key:
                    inputs = self.driver.find_elements(By.TAG_NAME, "input")
                    for inp in inputs:
                        val = inp.get_attribute("value")
                        if val:
                            clean_val = val.replace(" ", "").strip()
                            if len(clean_val) >= 16 and re.match(r'^[A-Z2-7]+$', clean_val):
                                secret_key = clean_val; break
                if secret_key: break
            except: pass
            time.sleep(1.5)
        
        if not secret_key: 
            raise Exception("STOP_FLOW_2FA: Secret Key NOT found! Blocking flow.")
        
        return secret_key

    def _validate_masked_email_robust(self, primary_email, secondary_email=None):
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            match = re.search(r'\b([a-zA-Z0-9][\w\*]*@[\w\*]+\.[a-zA-Z\.]+)\b', body_text)
            if not match: return True 
            masked = match.group(1).lower().strip()
            print(f"   [Step 4] Mask Hint: {masked}")
            
            def check(real, mask):
                if not real or "@" not in real: return False
                r_u, r_d = real.lower().split("@"); m_u, m_d = mask.lower().split("@")
                if m_d[0] != '*' and m_d[0] != r_d[0]: return False
                if "." in m_d and m_d.split('.')[-1] != r_d.split('.')[-1]: return False
                if m_u[0] != '*' and m_u[0] != r_u[0]: return False
                return True

            if check(primary_email, masked): return True
            if secondary_email and check(secondary_email, masked): return True
            print(f"   [CRITICAL] Hint {masked} mismatch!")
            return False
        except: return True

    def _click_continue_robust(self):
        js_click = """
        var keywords = ["Next", "Tiếp", "Continue", "Submit", "Xác nhận", "Confirm", "Done", "Xong", "This Was Me", "Đây là tôi", "Đúng là tôi"];
        var btns = document.querySelectorAll("button, div[role='button']");
        for (var b of btns) {
            var txt = b.innerText.trim();
            for(var k of keywords) { 
                if(txt.includes(k) && b.offsetParent !== null && !b.disabled && b.offsetHeight > 0) { 
                    b.click(); return true; 
                } 
            }
        }
        return false;
        """
        return self.driver.execute_script(js_click)

    def _robust_fill_input(self, text_value):
        input_el = None
        try:
            dialog_inputs = self.driver.find_elements(By.CSS_SELECTOR, "div[role='dialog'] input, div[role='main'] input")
            for inp in dialog_inputs:
                if inp.is_displayed(): input_el = inp; break
        except: pass

        if not input_el:
            selectors = ["input[name='code']", "input[placeholder*='Code']", "input[type='tel']", "input[maxlength='6']"]
            for sel in selectors:
                try:
                    el = self.driver.find_element(By.CSS_SELECTOR, sel)
                    if el.is_displayed(): input_el = el; break
                except: pass
        
        if not input_el: return False
        val = str(text_value).strip()

        try:
            ActionChains(self.driver).move_to_element(input_el).click().perform()
            time.sleep(0.1)
            input_el.send_keys(Keys.CONTROL + "a"); input_el.send_keys(Keys.DELETE)
            for char in val: 
                input_el.send_keys(char); time.sleep(0.03) 
            for _ in range(10):
                if input_el.get_attribute("value").replace(" ", "") == val: return True
                time.sleep(0.2)
        except: pass

        try:
            self.driver.execute_script("arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('input', {bubbles:true}));", input_el, val)
            time.sleep(0.5)
            return input_el.get_attribute("value").replace(" ", "") == val
        except: pass
        return False