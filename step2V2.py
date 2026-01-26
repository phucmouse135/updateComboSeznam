# step2_exceptions.py
import time
import re
import random
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
# Import ActionChains for advanced interactions
from selenium.webdriver import ActionChains

# Import các hàm utils
from config_utils import wait_element, wait_and_send_keys, wait_dom_ready, wait_and_click
from mail_handler_v2 import get_verify_code_v2

class InstagramExceptionStep:
    def __init__(self, driver):
        self.driver = driver
        # Callback for password change, can be set externally
        self.on_password_changed = self._default_on_password_changed

    def _default_on_password_changed(self, new_password):
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
            for _ in range(3):
                try:
                    body_text = self.driver.find_element(By.TAG_NAME, "body").text
                    if "@" in body_text: break
                except: time.sleep(1)
            
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
        # Timeout protection for password change (max 120s)
        start_time = time.time()
        TIMEOUT = 120
        print(f"   [Step 2] Handling Require Password Change (New password: {new_password})...")
        try:
            # Tìm 2 input: New password và Confirm new password
            new_pass_input = wait_element(self.driver, By.CSS_SELECTOR, "input[type='password'], input[name='new_password']", timeout=20)
            if time.time() - start_time > TIMEOUT:
                raise Exception("TIMEOUT_REQUIRE_PASSWORD_CHANGE: Input fields")
            confirm_pass_input = None
            inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='password']")
            if len(inputs) >= 2:
                confirm_pass_input = inputs[1]
            else:
                confirm_pass_input = wait_element(self.driver, By.CSS_SELECTOR, "input[name='confirm_new_password']", timeout=20)
                if time.time() - start_time > TIMEOUT:
                    raise Exception("TIMEOUT_REQUIRE_PASSWORD_CHANGE: Confirm input")
            # Nhập password vào cả 2 ô
            if new_pass_input:
                wait_and_click(self.driver, By.CSS_SELECTOR, "input[type='password'], input[name='new_password']", timeout=20)
                new_pass_input.clear(); new_pass_input.send_keys(new_password); time.sleep(0.5)
            if confirm_pass_input:
                wait_and_click(self.driver, By.CSS_SELECTOR, "input[name='confirm_new_password']", timeout=20)
                confirm_pass_input.clear(); confirm_pass_input.send_keys(new_password); time.sleep(0.5)

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
                            if wait_and_click(self.driver, by, sel, timeout=20):
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
            time.sleep(2)
            wait_dom_ready(self.driver)
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
        
        if status == "CONTINUE_UNUSUAL_LOGIN":
            # Timeout protection for unusual login (max 30s)
            start_time = time.time()
            TIMEOUT = 120
            print("   [Step 2] Handling Unusual Login (Clicking Continue/This Was Me)...")
            
            try:
                # Tìm tất cả các thẻ label (vì cấu trúc bạn gửi là <label ...> Text <input> ... </label>)
                labels = self.driver.find_elements(By.TAG_NAME, "label")
                email_selected = False
                
                if len(labels) > 0:
                    for label in labels:
                        try:
                            # Lấy text của label (bao gồm cả text node con)
                            txt = label.text.lower()
                            
                            # Nếu chứa ký tự @ (dấu hiệu của email)
                            if "@" in txt:
                                print(f"   [Step 2] Found Email Option: '{txt}'")
                                
                                # Tìm input nằm bên trong label đó
                                try:
                                    inp = label.find_element(By.TAG_NAME, "input")
                                    
                                    # Nếu chưa được chọn thì click
                                    if not inp.is_selected():
                                        # Chiến thuật click 3 lớp: Div -> Label -> Input (JS)
                                        try:
                                            # Ưu tiên 1: Click vào div trang trí bên trong (thường là cái hình tròn)
                                            inner_div = label.find_element(By.TAG_NAME, "div")
                                            wait_and_click(self.driver, By.TAG_NAME, "div", timeout=20)
                                            print("   [Step 2] Clicked via inner DIV.")
                                        except:
                                            try:
                                                # Ưu tiên 2: Click vào chính Label
                                                wait_and_click(self.driver, By.TAG_NAME, "label", timeout=20)
                                                print("   [Step 2] Clicked via LABEL.")
                                            except:
                                                # Ưu tiên 3: JS click thẳng vào Input
                                                wait_and_click(self.driver, By.TAG_NAME, "input", timeout=20)
                                                print("   [Step 2] Clicked via JS Input.")
                                    else:
                                        print("   [Step 2] Email option already selected.")
                                    
                                    email_selected = True
                                    break 
                                except: pass
                        except: pass
                    
                    if not email_selected:
                        print("   [Step 2] No explicit email radio found (May be single choice).")
                else:
                    print("   [Step 2] No labels found. Proceeding to click Continue.")

            except Exception as e:
                print(f"   [Step 2] Radio selection warning: {e}")

            time.sleep(1) # Chờ UI update nhẹ
            
            # Tìm nút Continue hoặc This Was Me
            keywords = ["continue", "tiếp tục", "this was me", "đây là tôi"]
            
            # Quét buttons
            btns = self.driver.find_elements(By.TAG_NAME, "button")
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
                divs = self.driver.find_elements(By.XPATH, "//div[@role='button']")
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
            wait_dom_ready(self.driver, timeout=5)
            time.sleep(2)
            new_status = self._check_verification_result()
            print(f"   [Step 2] Status after Continue: {new_status}")
            return self.handle_status(new_status, ig_username, gmx_user, gmx_pass, linked_mail, ig_password, depth + 1)

        if status == "REQUIRE_PASSWORD_CHANGE":
            # Timeout protection for password change (max 60s)
            start_time = time.time()
            TIMEOUT = 120
            print("   [Step 2] Handling Require Password Change...")
            if ig_password:
                new_pass = ig_password + "@"
                self._handle_require_password_change(new_pass)
                if time.time() - start_time > TIMEOUT:
                    raise Exception("TIMEOUT_REQUIRE_PASSWORD_CHANGE: End")
                # Cập nhật lại password mới lên GUI NGAY LẬP TỨC trước khi gọi các bước tiếp theo
                if hasattr(self, "on_password_changed") and callable(self.on_password_changed):
                    self.on_password_changed(new_pass)
                # Đảm bảo các bước sau luôn dùng mật khẩu mới
                ig_password = new_pass
                # de quy kiem tra lai trang thai
                new_status = self._check_verification_result()
                print(f"   [Step 2] Status after Password Change: {new_status}")
                return self.handle_status(new_status, ig_username, gmx_user, gmx_pass, linked_mail, ig_password, depth + 1)
            else:
                raise Exception("STOP_FLOW_REQUIRE_PASSWORD_CHANGE: No password provided")
    

        # XỬ LÝ BIRTHDAY
        if status == "BIRTHDAY_SCREEN":
            wait_dom_ready(self.driver, timeout=20)
            time.sleep(2)
            if self._handle_birthday_screen():
                # get new status after handling birthday
                wait_dom_ready(self.driver, timeout=20)
                new_status = self._check_verification_result()
                print(f"   [Step 2] Status after Birthday: {new_status}")

                # de quy kiem tra lai trang thai
                return self.handle_status(new_status, ig_username, gmx_user, gmx_pass, linked_mail, ig_password, depth + 1)
            else:   
                return self._handle_birthday_screen()

        # XỬ LÝ CHECKPOINT MAIL
        if status == "CHECKPOINT_MAIL":
            # Timeout protection for email checkpoint (max 60s)
            start_time = time.time()
            TIMEOUT = 120
            print("   [Step 2] Handling Email Checkpoint...")
            result = self._solve_email_checkpoint(ig_username, gmx_user, gmx_pass, linked_mail, ig_password)
            if time.time() - start_time > TIMEOUT:
                raise Exception("TIMEOUT_CHECKPOINT_MAIL: End")
            return result

        # NHÓM FAIL
        fail_statuses = [
            "UNUSUAL_LOGIN", "TRY_ANOTHER_DEVICE", "2FA_REQUIRED", "SUSPENDED",
            "LOGIN_FAILED_INCORRECT", "2FA_SMS", "2FA_WHATSAPP", "GET_HELP_LOG_IN",
            "2FA_APP", "2FA_APP_CONFIRM", "FAIL_LOGIN_REDIRECTED_TO_PROFILE_SELECTION",
            "LOGIN_FAILED_RETRY", "2FA_NOTIFICATIONS", "LOGGED_IN_UNKNOWN_STATE",
            "TIMEOUT_LOGIN_CHECK", "PAGE_BROKEN", "SUSPENDED_PHONE","LOG_IN_ANOTHER_DEVICE", 
            "LOGIN_FAILED_SOMETHING_WENT_WRONG", "CONFIRM_YOUR_IDENTITY", "2FA_TEXT_MESSAGE", 
            "ACCOUNT_DISABLED"
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

        raise Exception(f"STOP_FLOW_UNKNOWN_STATUS: {status}")

    # ==========================================
    # 3. LOGIC XỬ LÝ BIRTHDAY (STRICT VERIFY YEAR)
    # ==========================================
    def _handle_birthday_screen(self):
        # Timeout protection for birthday screen (max 120s)
        start_time = time.time()
        TIMEOUT = 120
        print("   [Step 2] Handling Birthday Screen...")
        
        # --- HÀM CON: DIỆT POPUP (NUKE POPUP) ---
        def nuke_real_birthday_popup():
            try:
                # 1. TÌM HỘP THOẠI (DIALOG)
                dialogs = self.driver.find_elements(By.CSS_SELECTOR, "div[role='dialog']")
                active_dialog = None
                for d in dialogs:
                    if d.is_displayed():
                        active_dialog = d
                        break
                
                # Fallback text check
                if not active_dialog:
                    body_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
                    if "real birthday" not in body_text and "sinh nhật thật" not in body_text:
                        return False
                
                print("   [Step 2] Found Birthday Dialog/Text. Targeting OK Button...")

                # 2. TÌM NÚT OK (Quét nhiều Selector)
                target_btn = None
                selectors = [
                    "button._a9--._ap36._asz1",      # Class chính xác
                    "button._a9--",                  
                    "div._a9-z > button",            
                    "button[tabindex='0']",          
                    "//button[text()='OK']"          
                ]

                search_context = active_dialog if active_dialog else self.driver
                
                for sel in selectors:
                    try:
                        if sel.startswith("//"): btns = search_context.find_elements(By.XPATH, sel)
                        else: btns = search_context.find_elements(By.CSS_SELECTOR, sel)
                        
                        for btn in btns:
                            if btn.is_displayed():
                                target_btn = btn
                                print(f"   [Step 2] Locked on button via: {sel}")
                                break
                            if time.time() - start_time > TIMEOUT:
                                raise Exception("TIMEOUT_BIRTHDAY_POPUP: Button find")
                    except: pass
                    if target_btn: break
                
                if not target_btn:
                    return False

                # Chờ ổn định animation trước khi click
                time.sleep(0.5)

                # Retry click để chống lỗi StaleElementReferenceException
                click_success = False
                for retry in range(5):
                    try:
                        # Cách 1: JS Focus + Enter
                        self.driver.execute_script("arguments[0].focus();", target_btn)
                        target_btn.send_keys(Keys.ENTER)
                        click_success = True
                        break
                    except Exception as e:
                        # Nếu lỗi StaleElementReferenceException thì tìm lại nút
                        try:
                            if sel.startswith("//"):
                                btns = search_context.find_elements(By.XPATH, sel)
                            else:
                                btns = search_context.find_elements(By.CSS_SELECTOR, sel)
                            for btn in btns:
                                if btn.is_displayed():
                                    target_btn = btn
                                    break
                                if time.time() - start_time > TIMEOUT:
                                    raise Exception("TIMEOUT_BIRTHDAY_POPUP: Button retry")
                        except:
                            pass
                        time.sleep(0.2)
                        continue
                if not click_success:
                    # Cách 2: JS Click
                    for retry in range(5):
                        try:
                            self.driver.execute_script("arguments[0].click();", target_btn)
                            click_success = True
                            break
                        except Exception as e:
                            try:
                                if sel.startswith("//"):
                                    btns = search_context.find_elements(By.XPATH, sel)
                                else:
                                    btns = search_context.find_elements(By.CSS_SELECTOR, sel)
                                for btn in btns:
                                    if btn.is_displayed():
                                        target_btn = btn
                                        break
                                    if time.time() - start_time > TIMEOUT:
                                        raise Exception("TIMEOUT_BIRTHDAY_POPUP: JS click retry")
                            except:
                                pass
                            time.sleep(0.2)
                            continue
                if not click_success:
                    # Cách 3: ActionChains
                    for retry in range(5):
                        try:
                            ActionChains(self.driver).move_to_element(target_btn).click().perform()
                            click_success = True
                            break
                        except Exception as e:
                            try:
                                if sel.startswith("//"):
                                    btns = search_context.find_elements(By.XPATH, sel)
                                else:
                                    btns = search_context.find_elements(By.CSS_SELECTOR, sel)
                                for btn in btns:
                                    if btn.is_displayed():
                                        target_btn = btn
                                        break
                                    if time.time() - start_time > TIMEOUT:
                                        raise Exception("TIMEOUT_BIRTHDAY_POPUP: ActionChains retry")
                            except:
                                pass
                            time.sleep(0.2)
                            continue

                time.sleep(1)
                try:
                    if not target_btn.is_displayed(): return True
                except: return True

                return True
            except Exception as e:
                print(f"   [Step 2] Nuke Error: {e}")
                return False

        try:
            # VÒNG LẶP CHÍNH (3 Lần)
            for attempt in range(3):
                if time.time() - start_time > TIMEOUT:
                    raise Exception("TIMEOUT_BIRTHDAY_SCREEN: Main loop")
                print(f"   [Step 2] Birthday Attempt {attempt+1}/3...")
                
                # BƯỚC 1: DIỆT POPUP
                # if nuke_real_birthday_popup():
                #     print("   [Step 2] Popup handled. Waiting for UI...")
                #     time.sleep(2)
                
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
                    next_xpaths = [
                        "//button[contains(text(), 'Next')]", 
                        "//div[contains(text(), 'Next') and @role='button']",
                        "//button[contains(text(), 'Tiếp')]"
                    ]
                    
                    for xpath in next_xpaths:
                        if wait_and_click(self.driver, By.XPATH, xpath, timeout=20):
                            next_clicked = True; break
                        if time.time() - start_time > TIMEOUT:
                            raise Exception("TIMEOUT_BIRTHDAY_SCREEN: Next button click")
                    
                    time.sleep(2)

                    # # BƯỚC 4: CHECK LẠI (NẾU BỊ ĐẨY VỀ LẠI)
                    # if nuke_real_birthday_popup():
                    #     print("   [Step 2] Popup appeared AGAIN after Next! Loop continues...")
                    #     continue 

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

            wait_dom_ready(self.driver, timeout=20)
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

    def _solve_email_checkpoint(self, ig_username, gmx_user, gmx_pass, linked_mail=None, ig_password=None):
        # Timeout protection for email checkpoint (max 120s)
        start_time = time.time()
        TIMEOUT = 120
        print(f"   [Step 2] Detected Email Checkpoint...")
        
        # --- GIAI ĐOẠN 0: RADIO BUTTON ---
        try:
            radios = self.driver.find_elements(By.CSS_SELECTOR, "input[type='radio']")
            if len(radios) > 0:
                print(f"   [Step 2] Found {len(radios)} options. Selecting 1st radio...")
                
                # Click radio đầu tiên
                wait_and_click(self.driver, By.CSS_SELECTOR, "input[type='radio']", timeout=20)
                time.sleep(1)
                
                # Click Send/Next
                send_btns = self.driver.find_elements(By.CSS_SELECTOR, "button[type='submit'], button._acan, div[role='button'][tabindex='0']")
                for btn in send_btns:
                    txt = btn.text.lower()
                    if btn.is_displayed() and any(k in txt for k in ["send", "gửi", "next", "tiếp", "continue"]):
                        print(f"   [Step 2] Clicked confirmation: {txt}")
                        wait_and_click(self.driver, By.CSS_SELECTOR, "button[type='submit'], button._acan, div[role='button'][tabindex='0']", timeout=20)
                        time.sleep(2)
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
                code = get_verify_code_v2(gmx_user, gmx_pass, ig_username)
                return code
            except Exception as e:
                print(f"   [Step 2] Error getting code: {e}")
                if "GMX_LOGIN_FAIL" in str(e):
                    raise Exception("GMX_DIE")
                raise Exception("GMX_DIE")
        def input_code(code):
            code_input = None
            input_css_list = ["#_r_7_", "input[name='email']", "input[name='security_code']", "input[type='text']", "input[name='verificationCode']"]
            for _ in range(3):
                for sel in input_css_list:
                    el = wait_element(self.driver, By.CSS_SELECTOR, sel, timeout=20)
                    if el:
                        code_input = el
                        break
                if code_input:
                    break
                time.sleep(1)
            if code_input:
                try:
                    wait_and_click(self.driver, By.CSS_SELECTOR, code_input.get_attribute('css selector') or "input[type='text']", timeout=20)
                    code_input.send_keys(Keys.CONTROL + "a"); code_input.send_keys(Keys.DELETE)
                    code_input.send_keys(code)
                    time.sleep(0.5)
                    code_input.send_keys(Keys.ENTER)
                    time.sleep(1)
                    if "security_code" in self.driver.current_url:
                        wait_and_click(self.driver, By.XPATH, "//button[@type='submit'] | //button[contains(text(), 'Confirm')] | //button[contains(text(), 'Xác nhận')]")
                except:
                    pass
            else:
                raise Exception("STOP_FLOW_CHECKPOINT: Cannot find code input")
        check_result = self._check_mail_flow(get_code, input_code, max_retries=5, timeout=TIMEOUT)
        print(f"   [Step 2] Email Checkpoint code verification result: {check_result}")
        # Xử lý kết quả trả về
        if check_result == "SUCCESS":
            print("   [Step 2] Code accepted. Doing final Post-Verify check...")
            for _ in range(5):
                time.sleep(2)
                if time.time() - start_time > TIMEOUT:
                    raise Exception("TIMEOUT_EMAIL_CHECKPOINT: Post-verify check")
                print("   [Step 2] Checking for Birthday or Change Password screens...")
                # Check Birthday
                if self._check_is_birthday_screen():
                    print("   [Step 2] Caught Birthday Screen after Verify!")
                    return self._handle_birthday_screen()
                # Check Change Password
                try:
                    body = self.driver.find_element(By.TAG_NAME, "body").text.lower()
                    if "change password" in body or "new password" in body:
                        if ig_password:
                            self._handle_change_password(ig_password + "@")
                        return "CHECKPOINT_SOLVED"
                except:
                    pass
            return "CHECKPOINT_SOLVED"
        elif check_result == "CHANGE_PASSWORD":
            if ig_password:
                self._handle_change_password(ig_password)
                return "CHECKPOINT_SOLVED"
            else:
                print("   [Step 2] Warning: Change password requested but no password provided.")
                return "CHECKPOINT_SOLVED"
        elif check_result == "BIRTHDAY_SCREEN":
            wait_dom_ready(self.driver, timeout=20)
            time.sleep(2)
            if time.time() - start_time > TIMEOUT:
                raise Exception("TIMEOUT_EMAIL_CHECKPOINT: Birthday screen")
            return self._handle_birthday_screen()
        elif check_result == "WRONG_CODE":
            raise Exception("STOP_FLOW_CHECKPOINT: All codes rejected.")
        elif check_result == "SUSPENDED":
            raise Exception("STOP_FLOW_CHECKPOINT: Suspended after code")
        elif check_result == "SUSPENDED_PHONE":
            raise Exception("STOP_FLOW_CHECKPOINT: Suspended after phone")
        else:
            raise Exception("STOP_FLOW_CHECKPOINT: Timeout verifying code")

    # ==========================================
    # 5. LOGIC CHECK MAIL (REUSE, ANTI-INFINITE LOOP)
    # ==========================================
    def _check_mail_flow(self, get_code_func, input_code_func, max_retries=5, timeout=120):
        """
        Chuẩn hóa logic check mail: lấy code, nhập code, kiểm tra kết quả, chống lặp vô hạn.
        get_code_func: hàm lấy code (lambda)
        input_code_func: hàm nhập code (lambda code)
        """
        start_time = time.time()
        for attempt in range(1, max_retries + 1):
            if time.time() - start_time > timeout:
                raise Exception("TIMEOUT_CHECK_MAIL_FLOW: Code input loop")
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
                    time.sleep(2)
                    continue
                else:
                    raise Exception("STOP_FLOW_CHECK_MAIL: No code found in mail")
            print(f"   [Step 2] Inputting code {code}...")
            input_code_func(code)
            print("   [Step 2] Waiting for UI to update after code input...")
            wait_and_click(self.driver, By.CSS_SELECTOR, "button[type='submit']", timeout=20)
            # Tăng thời gian chờ sau khi nhấn submit để tránh check mail quá sớm khi UI còn đang xử lý
            wait_dom_ready(self.driver, timeout=120)
            time.sleep(10)  # tăng từ 5s lên 15s để đảm bảo UI xử lý xong
            print("   [Step 2] Verifying code...")
            check_result = self._check_verification_result()
            print(f"   [Step 2] Result: {check_result}")
            if check_result == "CHECKPOINT_MAIL":
                if attempt < max_retries:
                    print("   [Step 2] Still at CHECKPOINT_MAIL, will retry if attempts remain...")
                    continue
                else:
                    raise Exception("STOP_FLOW_CHECK_MAIL: All codes tried but still at CHECKPOINT_MAIL")
            return check_result

    def _handle_change_password(self, old_password):
        # Timeout protection for change password (max 120s)
        start_time = time.time()
        TIMEOUT = 120
        print(f"   [Step 2] Handling Password Change (Re-using old password)...")
        try:
            pass_input = wait_element(self.driver, By.CSS_SELECTOR, 
                "input[name='password'], input[name='new_password'], input[type='password']", timeout=20)
            
            if pass_input:
                pass_input.click(); pass_input.clear(); pass_input.send_keys(old_password); time.sleep(1)
                submit_clicked = False
                if wait_and_click(self.driver, By.CSS_SELECTOR, "button[type='submit']", timeout=20): submit_clicked = True
                if not submit_clicked:
                    btns = self.driver.find_elements(By.TAG_NAME, "button")
                    for b in btns:
                        if any(k in b.text.lower() for k in ["change", "submit", "continue"]) and b.is_displayed():
                            b.click(); submit_clicked = True; break
                        if time.time() - start_time > TIMEOUT:
                            raise Exception("TIMEOUT_CHANGE_PASSWORD: Button click")
                
                print("   [Step 2] Submitted old password.")
                time.sleep(2) 
                wait_dom_ready(self.driver, timeout=120)
                if time.time() - start_time > TIMEOUT:
                    raise Exception("TIMEOUT_CHANGE_PASSWORD: End")
            else:
                print("   [Step 2] Error: Could not find New Password input.")
        except Exception as e:
            print(f"   [Step 2] Error handling password change: {e}")

    def _check_verification_result(self):
        # Timeout protection for verification result (max 120s)
        TIMEOUT = 120
        end_time = time.time() + TIMEOUT
        while time.time() < end_time:
            try:
                body = self.driver.find_element(By.TAG_NAME, "body").text.lower()
                if "the 6-digit code we sent to the email address" in body or "mã 6 chữ số mà chúng tôi đã gửi đến địa chỉ email" in body:
                    return "CHECKPOINT_MAIL"
                
                if "change password" in body or "new password" in body or "create a strong password" in body or "change your password to secure your account" in body:
                    return "CHANGE_PASSWORD"
                if "add phone number" in body or "send confirmation" in body or "log into another account" in body: return "SUSPENDED_PHONE"
                if "select your birthday" in body or "add your birthday" in body: return "BIRTHDAY_SCREEN"
                if "allow the use of cookies" in body or "posts" in body or "save your login info" in body: return "SUCCESS"
                if "suspended" in body or "đình chỉ" in body: return "SUSPENDED"
                if "please check the security code" in body or "code isn't right" in body: return "WRONG_CODE"
                if "instagram.com/" in self.driver.current_url and "challenge" not in self.driver.current_url: return "SUCCESS"
            # Nếu đã vào trong (có Post/Follower/Nav bar)
                if "posts" in body or "followers" in body or "search" in body or "home" in body:
                    return "LOGGED_IN_SUCCESS"

                if("save your login info?" in body or "we can save your login info on this browser so you don't need to enter it again." in body or "lưu thông tin đăng nhập của bạn" in body):
                    return "LOGGED_IN_SUCCESS"
            except: pass
            time.sleep(1)
        return "TIMEOUT"