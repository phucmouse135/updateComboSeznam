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
        Chiến thuật 'Aggressive Scan' (Tối ưu hóa bằng JS):
        Gộp kiểm tra Popup và kiểm tra Home vào 1 lần gọi JS để tăng tốc độ.
        """
        print("   [Step 3] Starting Aggressive Popup Scan...")
        
        end_time = time.time() + 120  # Quét trong 120 giây 
        
        while time.time() < end_time:
            try:
                # ---------------------------------------------------------
                # 1. QUÉT TRẠNG THÁI (POPUP + HOME) BẰNG JS
                # ---------------------------------------------------------
                action_result = self.driver.execute_script("""
                    // 1. KIỂM TRA HOME TRƯỚC (Điều kiện thoát nhanh)
                    // Nếu thấy icon Home và không có dialog nào che -> Báo về Home ngay
                    var homeIcon = document.querySelector("svg[aria-label='Home']") || document.querySelector("svg[aria-label='Trang chủ']");
                    var dialogs = document.querySelectorAll("div[role='dialog']");
                    var hasVisibleDialog = Array.from(dialogs).some(d => d.offsetParent !== null);
                    
                    if (homeIcon && !hasVisibleDialog) {
                        return 'HOME_SCREEN_CLEAR';
                    }

                    // 2. TỪ KHÓA POPUP
                    const keywords = {
                        'get_started': ['get started', 'bắt đầu'],
                        'agree_confirm': ['agree', 'đồng ý', 'update', 'cập nhật', 'confirm', 'xác nhận'],
                        'next_step': ['next', 'tiếp'],
                        'use_data_opt': ['use data across accounts', 'sử dụng dữ liệu trên các tài khoản'],
                        'cookie': ['allow all cookies', 'cho phép tất cả'],
                        'popup': ['not now', 'lúc khác', 'cancel', 'ok', 'hủy'], 
                        'age_check': ['18 or older', '18 tuổi trở lên', 'trên 18 tuổi'],
                        'account_center_check': ['choose an option', 'accounts center', 'use data across accounts'] 
                    };
                    const bodyText = document.body.innerText.toLowerCase();

                    // --- ƯU TIÊN: POPUP "ACCOUNTS CENTER" ---
                    if (keywords.account_center_check.some(k => bodyText.includes(k))) {
                        let buttons = document.querySelectorAll('button, div[role="button"], span');
                        for (let btn of buttons) {
                            let t = btn.innerText.toLowerCase().trim();
                            if (t === 'next' || t === 'tiếp' || t === 'continue') {
                                btn.click();
                                if (btn.tagName === 'SPAN' && btn.parentElement) btn.parentElement.click();
                                return 'ACCOUNTS_CENTER_NEXT';
                            }
                        }
                    }
                    
                    // --- XỬ LÝ CHECKPOINT TUỔI (RADIO BUTTON) ---
                    let radio18 = document.querySelector('input[type="radio"][value="above_18"]');
                    if (radio18) {
                        radio18.click();
                        let container = radio18.closest('div[role="button"]');
                        if (container) container.click();
                        let visualCircle = radio18.previousElementSibling;
                        if (visualCircle) visualCircle.click();

                        // Auto click Agree sau 1s
                        setTimeout(() => {
                            let btns = document.querySelectorAll('button, div[role="button"]');
                            for(let b of btns) {
                                if(b.innerText.toLowerCase().includes('agree') || b.innerText.toLowerCase().includes('đồng ý')) { b.click(); }
                            }
                        }, 500); 
                        return 'AGE_CHECK_CLICKED';
                    }
                    
                    // Fallback tuổi theo text
                    let ageLabels = document.querySelectorAll("span, label");
                    for(let el of ageLabels) {
                        if (el.innerText.includes("18 or older") || el.innerText.includes("18 tuổi trở lên")) {
                             let parentBtn = el.closest('div[role="button"]');
                             if (parentBtn) { parentBtn.click(); return 'AGE_CHECK_CLICKED'; }
                        }
                    }

                    // A. TÌM VÀ CHỌN OPTION (Use Data)
                    const labels = document.querySelectorAll('div, span, label');
                    for (let el of labels) {
                        if (el.offsetParent === null) continue;
                        let txt = el.innerText.toLowerCase().trim();
                        if (keywords.use_data_opt.some(k => txt === k)) {
                            el.scrollIntoView({behavior: "instant", block: "center"});
                            el.click(); return 'OPTION_SELECTED';
                        }
                    }

                    // B. TÌM VÀ CLICK NÚT BẤM CHUNG
                    const elements = document.querySelectorAll('button, div[role="button"]');
                    for (let el of elements) {
                        if (el.offsetParent === null) continue; 
                        let txt = el.innerText.toLowerCase().trim();
                        if (!txt) continue;

                        if (keywords.get_started.some(k => txt === k)) {
                            el.scrollIntoView({behavior: "instant", block: "center"});
                            el.click(); return 'GET_STARTED_CLICKED';
                        }
                        if (keywords.agree_confirm.some(k => txt.includes(k))) {
                            el.scrollIntoView({behavior: "instant", block: "center"});
                            el.click(); return 'AGREE_CLICKED';
                        }
                        if (keywords.next_step.some(k => txt === k)) {
                            el.scrollIntoView({behavior: "instant", block: "center"});
                            el.click(); return 'NEXT_CLICKED';
                        }
                        if (keywords.cookie.some(k => txt.includes(k))) {
                            el.click(); return 'COOKIE_CLICKED';
                        }
                        if (keywords.popup.some(k => txt === k)) {
                            el.click(); return 'POPUP_CLICKED';
                        }
                    }
                    return null;
                """)

                if action_result == 'HOME_SCREEN_CLEAR':
                    print("   [Step 3] Home Screen Clear. Done.")
                    break # [EXIT LOOP] Đã thành công

                if action_result:
                    print(f"   [Step 3] Action triggered: {action_result}")
                    
                    if action_result == 'AGREE_CLICKED':
                        time.sleep(3); self._check_crash_recovery()
                    elif action_result == 'OPTION_SELECTED':
                        print("   [Step 3] Option selected. Waiting for Next button...")
                        time.sleep(1)
                    elif action_result == 'AGE_CHECK_CLICKED': 
                        print("   [Step 3] Handled Age Verification (18+). Waiting...")
                        time.sleep(3)
                    else:
                        time.sleep(1.5)
                    continue

                # ---------------------------------------------------------
                # 2. CHECK CRASH (Python side fallback)
                # ---------------------------------------------------------
                try:
                    curr_url = self.driver.current_url.lower()
                    if "ig_sso_users" in curr_url or "/api/v1/" in curr_url or "error" in curr_url:
                        print(f"   [Step 3] Crash URL detected. Reloading Home...")
                        self.driver.get("https://www.instagram.com/")
                        time.sleep(4); continue

                    body_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
                    if "page isn’t working" in body_text or "http error" in body_text:
                        print("   [Step 3] Crash Text detected. Reloading Home...")
                        self.driver.get("https://www.instagram.com/")
                        time.sleep(4); continue
                except: pass

                time.sleep(0.5)

            except Exception as e:
                time.sleep(1)

    def _check_crash_recovery(self):
        """Hàm phụ trợ check crash nhanh sau khi click Agree."""
        try:
            wait_dom_ready(self.driver, timeout=5)
        except: pass

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
        
        # Scroll down to load stats
        self.driver.execute_script("window.scrollTo(0, 500);")
        time.sleep(1)
        
        js_crawl = """
            function getInfo() {
                let res = {posts: "0", followers: "0", following: "0", source: "none"};
                
                // 1. DÙNG MỎ NEO LINK FOLLOWERS (Tương thích cả UL/LI và DIV)
                let folLink = document.querySelector("a[href*='followers']");
                
                if (folLink) {
                    // CÁCH A: Cấu trúc DIV
                    let wrapper = folLink.closest('div'); 
                    if (wrapper && wrapper.parentElement) {
                        let container = wrapper.parentElement;
                        let divs = Array.from(container.children).filter(el => el.tagName === 'DIV');
                        if (divs.length >= 3) {
                            res.posts = divs[0].innerText;
                            res.followers = divs[1].innerText;
                            res.following = divs[2].innerText;
                            res.source = "div_structure";
                            return res;
                        }
                    }
                    // CÁCH B: Cấu trúc UL/LI
                    let ulContainer = folLink.closest("ul");
                    if (ulContainer) {
                        let items = ulContainer.querySelectorAll("li");
                        if (items.length >= 3) {
                            res.posts = items[0].innerText;
                            res.followers = items[1].innerText;
                            res.following = items[2].innerText;
                            res.source = "ul_structure";
                            return res;
                        }
                    }
                }

                // 2. FALLBACK: META TAG
                try {
                    let meta = document.querySelector('meta[property="og:description"]') || document.querySelector('meta[name="description"]');
                    if (meta) {
                        res.raw_meta = meta.getAttribute('content');
                        res.source = "meta";
                        return res;
                    }
                } catch(e) {}

                return res;
            }
            return getInfo();
        """

        # Hàm làm sạch số (100 posts -> 100)
        def clean_num(val):
            if not val: return "0"
            val = str(val).replace("\n", " ").strip()
            m = re.search(r'([\d.,]+[kKmM]?)', val)
            return m.group(1) if m else "0"

        def parse_meta(text):
            if not text: return "0", "0", "0"
            text = text.lower().replace(",", "").replace(".", ".")
            p = re.search(r'(\d+[km]?)\s+(posts|bài viết|beiträge)', text)
            f1 = re.search(r'(\d+[km]?)\s+(followers|người theo dõi)', text)
            f2 = re.search(r'(\d+[km]?)\s+(following|đang theo dõi)', text)
            if not p: p = re.search(r'(posts|bài viết)\s+(\d+[km]?)', text)
            return (p.group(1) if p else "0"), (f1.group(1) if f1 else "0"), (f2.group(1) if f2 else "0")

        for i in range(1, 4):
            try:
                time.sleep(1.5)
                raw_js = self.driver.execute_script(js_crawl)
                
                p, f1, f2 = "0", "0", "0"
                
                # Ưu tiên nguồn cấu trúc (DIV hoặc UL)
                if raw_js and raw_js.get("source") in ["div_structure", "ul_structure"]:
                    p = clean_num(raw_js.get("posts"))
                    f1 = clean_num(raw_js.get("followers"))
                    f2 = clean_num(raw_js.get("following"))
                    print(f"   [Step 3] Crawled via DOM ({raw_js.get('source')}): P={p}, F1={f1}, F2={f2}")

                # Nguồn Meta Tag
                elif raw_js and raw_js.get("source") == "meta":
                    p, f1, f2 = parse_meta(raw_js.get("raw_meta"))
                    print(f"   [Step 3] Crawled via META: P={p}, F1={f1}, F2={f2}")

                temp_data = {"posts": p, "followers": f1, "following": f2}

                # Điều kiện chấp nhận: Ít nhất 1 trường có dữ liệu
                if temp_data["followers"] != "0" or temp_data["posts"] != "0" or temp_data["following"] != "0":
                    final_data = temp_data
                    print(f"   [Step 3] Success (Attempt {i}): {final_data}")
                    break
                else:
                    print(f"   [Step 3] Attempt {i}: Data empty. Retrying...")

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