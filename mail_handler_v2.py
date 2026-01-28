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

def _fetch_latest_unseen_mail(gmx_user, gmx_pass, subject_keywords, target_username = None, loop_duration=30):
    """
    Hàm Core Tối Ưu:
    - Quét mail một lần duy nhất (Single-scan).
    - Tự động đóng kết nối (Logout) ngay sau khi xong việc.
    - Raise GMX_DIE nếu lỗi login để lớp bên ngoài ngưng retry.
    """
    if not gmx_user or not gmx_pass: return None
    if "@" not in gmx_user: gmx_user += "@gmx.net"

    # Set timeout để tránh treo luồng nếu server GMX phản hồi chậm
    socket.setdefaulttimeout(15) 
    mail = None

    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(gmx_user, gmx_pass)
        
        # Select INBOX
        mail.select("INBOX")
        
        # Tìm mail CHƯA ĐỌC từ Instagram, sắp xếp theo ARRIVAL giảm dần (mới nhất trước)
        try:
            # Thử dùng SORT nếu server hỗ trợ
            status, messages = mail.sort('(REVERSE ARRIVAL)', 'UTF-8', '(UNSEEN FROM "Instagram")')
            if status == "OK" and messages[0]:
                mail_ids = messages[0].split()
            else:
                # Fallback to UID search
                status, messages = mail.uid('search', None, '(UNSEEN FROM "Instagram")')
                if status == "OK" and messages[0]:
                    mail_ids = messages[0].split()
                    # Sắp xếp giảm dần (mới nhất trước, UID cao hơn)
                    mail_ids.sort(key=int, reverse=True)
                else:
                    return None
        except:
            # Fallback to standard search
            status, messages = mail.search(None, '(UNSEEN FROM "Instagram")')
            if status == "OK" and messages[0]:
                mail_ids = messages[0].split()
            else:
                return None
        
        if not mail_ids:
            return None
        
        # Ưu tiên mail mới nhất (đầu tiên trong list đã sắp xếp)
        latest_id = mail_ids[0]
        
        # --- TỐI ƯU: Chỉ tải Header trước ---
        try:
            _, msg_header = mail.uid('fetch', latest_id, '(BODY.PEEK[HEADER])')
        except:
            # Fallback to fetch
            _, msg_header = mail.fetch(latest_id, '(BODY.PEEK[HEADER])')
        
        header_content = email.message_from_bytes(msg_header[0][1])
        subject = _decode_str(header_content.get("Subject", "")).lower()
        message_id = header_content.get("Message-ID", "")

        # Kiểm tra Subject nhanh
        if any(k.lower() in subject for k in subject_keywords):
            # Khớp subject mới tải toàn bộ Body
            try:
                _, msg_data = mail.uid('fetch', latest_id, "(RFC822)")
            except:
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

            # Kiểm tra Username (Đảm bảo mail đúng cho tài khoản đang check)
            if target_username and target_username.lower() not in body_lower:
                print(f"   [IMAP] Mismatch username in mail {latest_id}. Marking Seen.")
                try:
                    mail.uid('store', latest_id, '+FLAGS', '\\Seen')
                except:
                    mail.store(latest_id, '+FLAGS', '\\Seen')
                return None

            # Extract Code (6-8 số)
            m = re.search(r'\b(\d{6,8})\b', body)
            if m:
                code = m.group(1)
                # Đánh dấu đã đọc thành công
                try:
                    mail.uid('store', latest_id, '+FLAGS', '\\Seen')
                except:
                    mail.store(latest_id, '+FLAGS', '\\Seen')
                return code
                    
    except Exception as e:
        err_str = str(e).lower()
        print(f"   [IMAP Error] {err_str}")
        # Nếu sai pass/die mail, báo lỗi để lớp ngoài ngưng retry vô ích
        if any(x in err_str for x in ["authentication failed", "login failed", "invalid user", "credential"]):
            raise Exception("GMX_DIE")
    finally:
        if mail:
            try:
                mail.close() # Đóng mailbox
                mail.logout() # Ngắt kết nối
            except:
                pass
    
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