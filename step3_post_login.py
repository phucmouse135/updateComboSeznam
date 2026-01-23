# step3_post_login.py
import time
import re
from selenium.webdriver.common.by import By
from config_utils import wait_element, wait_and_click, wait_dom_ready

class InstagramPostLoginStep:
    def __init__(self, driver):
        self.driver = driver

    def process_post_login(self, username):
        """
        Luồng chính xử lý sau khi Login thành công:
        1. Xử lý các màn hình chắn (Cookie, Terms, Lỗi Page, Popup...).
        2. Điều hướng vào Profile.
        3. Crawl Dữ liệu (Post, Follower, Following).
        4. Trích xuất Cookie mới.
        """
        print(f"   [Step 3] Processing Post-Login for {username}...")
        
        # 1. Xử lý các Popup/Màn hình chắn (Vòng lặp check)
        self._handle_interruptions()
        
        # 2. Điều hướng vào Profile
        self._navigate_to_profile(username)
        
        # 3. Crawl Dữ liệu
        data = self._crawl_data(username)
        
        # 4. Lấy Cookie mới
        data['cookie'] = self._get_cookie_string()
        
        return data

    def _handle_interruptions(self):
        """
        Chiến thuật 'Aggressive Scan' (Đã cập nhật Confirm Accounts):
        1. Quét Get Started / Confirm Accounts.
        2. Quét Use Data Across Accounts.
        3. Quét Terms/Cookie như cũ.
        """
        print("   [Step 3] Starting Aggressive Popup Scan...")
        
        end_time = time.time() + 60 
        
        while time.time() < end_time:
            try:
                # ---------------------------------------------------------
                # 1. QUÉT VÀ CLICK NÚT BẰNG JS (ALL-IN-ONE)
                # ---------------------------------------------------------
                clicked_action = self.driver.execute_script("""
                    const keywords = {
                        // Nhóm 1: Xác nhận tài khoản / Terms (Ưu tiên cao)
                        'get_started': ['get started', 'bắt đầu'],
                        'agree_confirm': ['agree', 'đồng ý', 'update', 'cập nhật', 'confirm', 'xác nhận'],
                        'next_step': ['next', 'tiếp'],
                        
                        // Nhóm 2: Lựa chọn Option (Click vào text để chọn radio button)
                        'use_data_opt': ['use data across accounts', 'sử dụng dữ liệu trên các tài khoản'],

                        // Nhóm 3: Cookie & Popup rác
                        'cookie': ['allow all cookies', 'cho phép tất cả'],
                        'popup': ['not now', 'lúc khác', 'cancel', 'ok', 'hủy']
                    };

                    // A. TÌM VÀ CHỌN OPTION TRƯỚC (Nếu đang ở màn hình chọn Data)
                    // Tìm thẻ label hoặc div chứa text lựa chọn
                    const labels = document.querySelectorAll('div, span, label');
                    for (let el of labels) {
                        if (el.offsetParent === null) continue;
                        let txt = el.innerText.toLowerCase().trim();
                        
                        // Nếu thấy dòng "Use data across accounts" -> Click để chọn
                        if (keywords.use_data_opt.some(k => txt === k)) {
                            // Chỉ click nếu chưa được chọn (logic này optional, cứ click cho chắc)
                            el.scrollIntoView({behavior: "instant", block: "center"});
                            el.click();
                            return 'OPTION_SELECTED';
                        }
                    }

                    // B. TÌM VÀ CLICK NÚT BẤM
                    const elements = document.querySelectorAll('button, div[role="button"]');
                    
                    for (let el of elements) {
                        if (el.offsetParent === null) continue; 
                        let txt = el.innerText.toLowerCase().trim();
                        if (!txt) continue;

                        // 1. Get Started (Màn hình Confirm Accounts)
                        if (keywords.get_started.some(k => txt === k)) {
                            el.scrollIntoView({behavior: "instant", block: "center"});
                            el.click(); return 'GET_STARTED_CLICKED';
                        }

                        // 2. Agree / Confirm
                        if (keywords.agree_confirm.some(k => txt.includes(k))) {
                            el.scrollIntoView({behavior: "instant", block: "center"});
                            el.click(); return 'AGREE_CLICKED';
                        }
                        
                        // 3. Next
                        if (keywords.next_step.some(k => txt === k)) {
                            el.scrollIntoView({behavior: "instant", block: "center"});
                            el.click(); return 'NEXT_CLICKED';
                        }

                        // 4. Cookie
                        if (keywords.cookie.some(k => txt.includes(k))) {
                            el.click(); return 'COOKIE_CLICKED';
                        }

                        // 5. Popup rác
                        if (keywords.popup.some(k => txt === k)) {
                            el.click(); return 'POPUP_CLICKED';
                        }
                    }
                    return null;
                """)

                if clicked_action:
                    print(f"   [Step 3] Action triggered: {clicked_action}")
                    
                    if clicked_action == 'AGREE_CLICKED':
                        # Confirm xong dễ bị crash hoặc load lâu
                        time.sleep(3); self._check_crash_recovery()
                    elif clicked_action == 'GET_STARTED_CLICKED':
                        # Chuyển sang màn chọn Option
                        time.sleep(2)
                    elif clicked_action == 'OPTION_SELECTED':
                        # Chọn xong thì chờ nút Next sáng lên để vòng lặp sau click Next
                        print("   [Step 3] Option selected. Waiting for Next button...")
                        time.sleep(1)
                    else:
                        time.sleep(1.5)
                    
                    continue

                # ---------------------------------------------------------
                # 2. CHECK CRASH
                # ---------------------------------------------------------
                try:
                    # Check URL lạ
                    curr_url = self.driver.current_url.lower()
                    if "ig_sso_users" in curr_url or "/api/v1/" in curr_url or "error" in curr_url:
                        print(f"   [Step 3] Crash URL detected. Reloading Home...")
                        self.driver.get("https://www.instagram.com/")
                        time.sleep(4); continue

                    # Check Body
                    body_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
                    if "page isn’t working" in body_text or "http error" in body_text:
                        print("   [Step 3] Crash Text detected. Reloading Home...")
                        self.driver.get("https://www.instagram.com/")
                        time.sleep(4); continue
                except: pass

                # ---------------------------------------------------------
                # 3. CHECK HOME (Final Condition)
                # ---------------------------------------------------------
                home_icons = self.driver.find_elements(By.CSS_SELECTOR, "svg[aria-label='Home'], svg[aria-label='Trang chủ']")
                if len(home_icons) > 0:
                    dialogs = self.driver.find_elements(By.CSS_SELECTOR, "div[role='dialog']")
                    visible_dialogs = [d for d in dialogs if d.is_displayed()]
                    
                    if len(visible_dialogs) > 0:
                        time.sleep(1); continue 
                    else:
                        print("   [Step 3] Home Screen Clear. Done.")
                        break

                time.sleep(0.5)

            except Exception as e:
                time.sleep(1)
    def _navigate_to_profile(self, username):
        """Click vào biểu tượng Profile để vào trang cá nhân."""
        print("   [Step 3] Navigating to Profile...")
        
        profile_selectors = [
            f"a[href='/{username}/']",          # Link trực tiếp
            "img[alt$='profile picture']",      # Ảnh Avatar nhỏ
            "svg[aria-label='Profile']",        # Icon Profile
            "svg[aria-label='Trang cá nhân']"
        ]
        
        clicked = False
        for sel in profile_selectors:
            el = wait_element(self.driver, By.CSS_SELECTOR, sel, timeout=3)
            if el:
                try: 
                    el.click()
                    clicked = True
                    break
                except: pass
        
        # Nếu click thất bại, truy cập thẳng URL
        if not clicked:
            print("   [Step 3] Click failed. Forcing URL navigation...")
            self.driver.get(f"https://www.instagram.com/{username}/")
        
        wait_dom_ready(self.driver)
        # Chờ Username xuất hiện (Confirm đã vào đúng trang)
        wait_element(self.driver, By.XPATH, f"//*[contains(text(), '{username}')]", timeout=5)

    def _crawl_data(self, username):
        print(f"   [Step 3] Crawling data for {username}...")
        
        final_data = {"posts": "0", "followers": "0", "following": "0"}
        
        # Script JS lấy dữ liệu (không đổi)
        js_crawl = """
            function getInfo() {
                let data = {posts: "0", followers: "0", following: "0"};
                let folLink = document.querySelector("a[href*='followers']");
                if (folLink) data.followers = folLink.innerText || folLink.getAttribute('title');
                let folingLink = document.querySelector("a[href*='following']");
                if (folingLink) data.following = folingLink.innerText;
                let listItems = document.querySelectorAll("header ul li");
                if (listItems.length >= 3) {
                    data.posts = listItems[0].innerText;
                    if (!data.followers || data.followers === "0") data.followers = listItems[1].innerText;
                    if (!data.following || data.following === "0") data.following = listItems[2].innerText;
                }
                return data;
            }
            return getInfo();
        """

        def extract_num(txt):
            if not txt: return "0"
            match = re.search(r'[\d.,kKmM]+', str(txt))
            return match.group(0) if match else "0"

        # --- CƠ CHẾ RETRY (THỬ LẠI) ---
        for i in range(1, 4): # Thử 3 lần
            try:
                # [UPDATE] Chậm lại 1 chút mỗi lần quét
                time.sleep(2) 
                
                raw_data = self.driver.execute_script(js_crawl)
                
                temp_data = {
                    "posts": extract_num(raw_data.get("posts")),
                    "followers": extract_num(raw_data.get("followers")),
                    "following": extract_num(raw_data.get("following"))
                }

                # Nếu lấy được dữ liệu khác 0, chốt luôn và thoát
                if temp_data["followers"] != "0" or temp_data["following"] != "0":
                    final_data = temp_data
                    print(f"   [Step 3] Extracted (Attempt {i}): {final_data}")
                    break
                else:
                    print(f"   [Step 3] Attempt {i}: Data is 0. Retrying...")
            
            except Exception as e:
                print(f"   [Step 3] Crawl Error (Attempt {i}): {e}")

        return final_data

    def _get_cookie_string(self):
        """Lấy toàn bộ cookie hiện tại và gộp thành chuỗi."""
        try:
            cookies = self.driver.get_cookies()
            return "; ".join([f"{c['name']}={c['value']}" for c in cookies])
        except:
            return ""