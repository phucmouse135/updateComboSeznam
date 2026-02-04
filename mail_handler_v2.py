# mail_handler_v2.py
import imaplib
import email
import re
import time
import socket
from email.header import decode_header

# --- CẤU HÌNH SEZNAM ---
IMAP_SERVER = "imap.seznam.cz"
IMAP_PORT = 993

# Danh sách folder cần quét
TARGET_FOLDERS = ["newsletters", "spam", "INBOX"]

def _decode_str(header_value):
    if not header_value: return ""
    try:
        decoded_list = decode_header(header_value)
        text = ""
        for content, encoding in decoded_list:
            if isinstance(content, bytes):
                text += content.decode(encoding or "utf-8", errors="ignore")
            else:
                text += str(content)
        return text.strip()
    except:
        return str(header_value)

def _fetch_latest_unseen_mail(email_user, email_pass, subject_keywords, target_username=None, target_email=None, loop_duration=45):
    """
    Phiên bản Fix: 
    1. Mark Seen ngay lập tức để không lặp lại.
    2. Regex chặn dấu chấm (.) để không bắt nhầm username dạng 78.969269
    3. Xóa username khỏi body trước khi scan.
    """
    if not email_user or not email_pass: return None
    if "@" not in email_user: email_user += "@seznam.cz" 

    mail = None
    start_time = time.time()

    # --- REGEX THÔNG MINH (STRICT MODE) ---
    # (?<![._\-\d]): Đằng trước KHÔNG ĐƯỢC là dấu chấm, gạch dưới, gạch ngang, hoặc số
    # (\d{6,8}|\d{3}\s\d{3}): Lấy 6-8 số hoặc dạng 123 456
    # (?![._\-\d]): Đằng sau KHÔNG ĐƯỢC là dấu chấm, gạch dưới, gạch ngang, hoặc số
    code_pattern = re.compile(r'(?<![._\-\d])\b(\d{6,8}|\d{3}\s\d{3})\b(?![._\-\d])')

    try:
        socket.setdefaulttimeout(30)
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        try:
            mail.login(email_user, email_pass)
        except Exception as e:
            if any(k in str(e).lower() for k in ["authentication failed", "login failed", "credentials"]):
                raise Exception("LOGIN_DIE")
            raise e

        while time.time() - start_time < loop_duration:
            
            for folder_name in TARGET_FOLDERS:
                try:
                    # Select folder (readonly=False để mark seen)
                    status, _ = mail.select(f'"{folder_name}"', readonly=False)
                    if status != "OK": continue

                    status, messages = mail.search(None, 'ALL')
                    if status != "OK" or not messages[0]: continue 

                    mail_ids = messages[0].split()
                    recent_ids = mail_ids[-6:]
                    recent_ids.reverse()

                    for mail_id in recent_ids:
                        # 1. Fetch Header & Flags
                        _, fetch_data = mail.fetch(mail_id, '(BODY.PEEK[HEADER] FLAGS)')
                        
                        # Check đã đọc (Tránh loop vĩnh viễn mail cũ)
                        is_read = False
                        for item in fetch_data:
                            if isinstance(item, bytes):
                                if b'\\Seen' in item or b'\\SEEN' in item: is_read = True; break
                            elif isinstance(item, tuple) and len(item) > 0:
                                if b'\\Seen' in item[0] or b'\\SEEN' in item[0]: is_read = True; break
                        
                        if is_read: continue 

                        # Parse Header
                        msg_header = None
                        for item in fetch_data:
                            if isinstance(item, tuple):
                                msg_header = email.message_from_bytes(item[1])
                                break
                        if not msg_header: continue

                        subject = _decode_str(msg_header.get("Subject", "")).lower()
                        sender = _decode_str(msg_header.get("From", "")).lower()
                        to_addr = _decode_str(msg_header.get("To", "")).lower()

                        # Filter cơ bản
                        if "instagram" not in sender: continue
                        if not any(k.lower() in subject for k in subject_keywords): continue 
                        if target_email and target_email.lower().strip() not in to_addr: continue
                        
                        # [LOCK] MARK AS SEEN NGAY LẬP TỨC
                        try: mail.store(mail_id, '+FLAGS', '\\Seen')
                        except: pass

                        # 2. Tải Body
                        _, msg_data = mail.fetch(mail_id, "(BODY.PEEK[])") 
                        full_msg = email.message_from_bytes(msg_data[0][1])
                        body = ""
                        if full_msg.is_multipart():
                            for part in full_msg.walk():
                                ctype = part.get_content_type()
                                if ctype == "text/plain":
                                    body += part.get_payload(decode=True).decode('utf-8', errors='ignore'); break
                                elif ctype == "text/html":
                                     body += part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        else:
                            body = full_msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                        
                        if not body: body = ""

                        # --- [BƯỚC VỆ SINH QUAN TRỌNG] ---
                        # Xóa sạch HTML tag
                        clean_body = re.sub(r'<[^>]+>', ' ', body)
                        # Chuyển về lowercase để xử lý
                        clean_body_lower = clean_body.lower()

                        # 3. XOÁ USERNAME KHỎI BODY (Tránh bắt nhầm số trong username)
                        if target_username:
                            u_name = target_username.lower().strip()
                            
                            # Xóa user nguyên bản (ví dụ: 78.969269)
                            if u_name:
                                clean_body_lower = clean_body_lower.replace(u_name, "")
                            
                            # Xóa user bỏ dấu (ví dụ: 78969269) đề phòng email hiển thị khác
                            u_name_no_dot = u_name.replace(".", "").replace("_", "")
                            if u_name_no_dot:
                                clean_body_lower = clean_body_lower.replace(u_name_no_dot, "")

                        # 4. Tìm Code bằng Regex "Khắt khe"
                        matches = code_pattern.findall(clean_body_lower)
                        
                        if matches:
                            for code_candidate in matches:
                                final_code = code_candidate.replace(" ", "")
                                
                                # Kiểm tra độ dài
                                if len(final_code) in [6, 8]:
                                    # Chặn các số năm (False positive phổ biến)
                                    if final_code in ["2024", "2025", "2026", "2027"]: 
                                        continue
                                    
                                    # Kiểm tra lại lần cuối: Đảm bảo code tìm được KHÔNG nằm trong username (Double check)
                                    if target_username and final_code in target_username.replace(".", ""):
                                        print(f"   [IMAP Warning] Ignored code {final_code} because it looks like part of username.")
                                        continue

                                    print(f"   [IMAP] FOUND CODE: {final_code} for {target_username} in '{folder_name}'")
                                    return final_code
                    
                except Exception:
                    continue
            
            time.sleep(2.5)
            try: mail.noop()
            except: pass
        
        elapsed = time.time() - start_time
        print(f"   [IMAP] Timeout {elapsed:.1f}s: No new code found")
        return None

    except Exception as e:
        if "LOGIN_DIE" in str(e): raise e
        print(f"   [IMAP Error] {e}"); return None
    finally:
        if mail:
            try: mail.close(); mail.logout()
            except: pass

# ... (Các hàm get_verify_code_v2, get_2fa_code_v2 giữ nguyên) ...
def get_verify_code_v2(gmx_user, gmx_pass, target_ig_username, target_email=None):
    keywords = ["verify", "xác thực", "confirm", "code", "security", "mã bảo mật", "is your instagram code", "bạn vừa yêu cầu"]
    return _fetch_latest_unseen_mail(gmx_user, gmx_pass, keywords, target_ig_username, target_email, loop_duration=30)

def get_2fa_code_v2(gmx_user, gmx_pass, target_ig_username, target_email=None):
    keywords = ["authenticate", "two-factor", "security", "bảo mật", "2fa", "login code", "mã đăng nhập"]
    return _fetch_latest_unseen_mail(gmx_user, gmx_pass, keywords, target_ig_username, target_email, loop_duration=30)