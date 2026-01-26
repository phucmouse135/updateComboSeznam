# mail_handler_v2.py
import imaplib
import email
import re
import time
import socket
from email.header import decode_header

IMAP_SERVER = "imap.gmx.net"
IMAP_PORT = 993

def _decode_str(header_value):
    if not header_value: return ""
    try:
        decoded_list = decode_header(header_value)
        text = ""
        for content, encoding in decoded_list:
            if isinstance(content, bytes):
                text += content.decode(encoding or "utf-8", errors="ignore")
            else: text += str(content)
        return text
    except: return str(header_value)

def _fetch_latest_unseen_mail(gmx_user, gmx_pass, subject_keywords, target_username, loop_duration=15):
    """
    Hàm Core Tối Ưu:
    - Giữ kết nối IMAP trong `loop_duration` giây.
    - Quét liên tục (Polling) để bắt mail ngay khi nó đến.
    """
    if not gmx_user or not gmx_pass: return None
    if "@" not in gmx_user: gmx_user += "@gmx.net"

    # Set timeout socket để tránh treo tool nếu mạng lag
    socket.setdefaulttimeout(20) 
    mail = None

    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(gmx_user, gmx_pass)
        
        # Vòng lặp quét mail (Polling) trong một kết nối duy nhất
        end_time = time.time() + loop_duration
        
        while time.time() < end_time:
            # Select INBOX mỗi lần lặp để làm mới danh sách mail
            mail.select("INBOX")
            
            # Tìm mail CHƯA ĐỌC từ Instagram
            status, messages = mail.search(None, '(UNSEEN FROM "Instagram")')
            
            if status == "OK" and messages[0]:
                mail_ids = messages[0].split()
                # Lấy mail mới nhất (ID lớn nhất nằm cuối)
                latest_id = mail_ids[-1] 
                
                # --- TỐI ƯU: CHỈ TẢI HEADER TRƯỚC ĐỂ CHECK SUBJECT ---
                _, msg_header = mail.fetch(latest_id, '(BODY.PEEK[HEADER])')
                header_content = email.message_from_bytes(msg_header[0][1])
                subject = _decode_str(header_content["Subject"]).lower()

                # Check Subject nhanh
                if any(k in subject for k in subject_keywords):
                    # Nếu Subject khớp, mới tải Body
                    _, msg_data = mail.fetch(latest_id, "(RFC822)")
                    full_msg = email.message_from_bytes(msg_data[0][1])
                    
                    body = ""
                    if full_msg.is_multipart():
                        for part in full_msg.walk():
                            if part.get_content_type() == "text/plain":
                                body += part.get_payload(decode=True).decode('utf-8', errors='ignore')
                                break
                    else:
                        body = full_msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                    
                    body_lower = body.lower()

                    # Check Username (Bắt buộc phải có trong nội dung mail)
                    if target_username and target_username.lower() not in body_lower:
                        print(f"   [IMAP] Mismatch username in mail {latest_id}. Skipping.")
                        # Đánh dấu đã đọc để không check lại mail sai này nữa
                        mail.store(latest_id, '+FLAGS', '\\Seen')
                        continue

                    # Extract Code (6-8 số)
                    m = re.search(r'\b(\d{6,8})\b', body)
                    if m:
                        code = m.group(1)
                        print(f"   [IMAP] => FOUND CODE: {code}")
                        # Đánh dấu đã đọc
                        mail.store(latest_id, '+FLAGS', '\\Seen')
                        return code
            
            # Nếu chưa thấy mail, ngủ ngắn 1.5s rồi quét lại (vẫn giữ kết nối, không logout)
            time.sleep(1.5)

    except Exception as e:
        print(f"   [IMAP Error] {e}")
        error_msg = str(e).lower()
        if "authentication failed" in error_msg or "login failed" in error_msg:
            raise Exception("GMX_DIE")
    finally:
        try: mail.logout()
        except: pass
    
    return None

# --- API CHO CÁC BƯỚC (GIỮ NGUYÊN KEYWORDS CỦA BẠN) ---

def get_verify_code_v2(gmx_user, gmx_pass, target_ig_username):
    """
    Dùng cho Step 2: Verify Account (6 số).
    Keywords gốc: verify, xác thực, confirm, login code
    """
    keywords = ["verify", "xác thực", "confirm", "login code", "security code"]
    # Loop 15s là đủ cho Verify mail (thường về nhanh)
    return _fetch_latest_unseen_mail(gmx_user, gmx_pass, keywords, target_ig_username, loop_duration=15)

def get_2fa_code_v2(gmx_user, gmx_pass, target_ig_username):
    """
    Dùng cho Step 4: Authenticate Account (6 hoặc 8 số).
    Keywords gốc: authenticate, two-factor, security, bảo mật, 2fa, verify
    """
    keywords = ["authenticate", "two-factor", "security", "bảo mật", "2fa", "verify", "login code"]
    # Loop 15s, Step 4 sẽ gọi hàm này nhiều lần nếu chưa thấy
    return _fetch_latest_unseen_mail(gmx_user, gmx_pass, keywords, target_ig_username, loop_duration=15)