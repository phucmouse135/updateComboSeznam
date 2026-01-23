# mail_handler_v2.py
import imaplib
import email
import re
import time
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

def _fetch_latest_unseen_mail(gmx_user, gmx_pass, subject_keywords, target_username):
    """
    Hàm Core: Lấy mail UNSEEN + Khớp Subject + Khớp Username trong Body.
    """
    if not gmx_user or not gmx_pass: return None
    if "@" not in gmx_user: gmx_user += "@gmx.net"

    mail = None
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(gmx_user, gmx_pass)
        mail.select("INBOX")
        
        # 1. Tìm mail CHƯA ĐỌC từ Instagram
        status, messages = mail.search(None, '(UNSEEN FROM "Instagram")')
        
        if status == "OK" and messages[0]:
            mail_ids = messages[0].split()
            # Sort giảm dần (Mới nhất lên đầu)
            mail_ids.sort(key=lambda x: int(x), reverse=True)
            
            # Quét tối đa 3 mail mới nhất
            for mid in mail_ids[:3]:
                _, msg_data = mail.fetch(mid, "(RFC822)")
                full_msg = email.message_from_bytes(msg_data[0][1])
                
                # A. Check Subject
                subject = _decode_str(full_msg["Subject"]).lower()
                if not any(k in subject for k in subject_keywords):
                    continue # Bỏ qua nếu tiêu đề không đúng loại

                # B. Parse Body
                body = ""
                if full_msg.is_multipart():
                    for part in full_msg.walk():
                        if part.get_content_type() == "text/plain":
                            body += part.get_payload(decode=True).decode('utf-8', errors='ignore')
                            break # Ưu tiên Plain Text
                        elif part.get_content_type() == "text/html":
                            body += part.get_payload(decode=True).decode('utf-8', errors='ignore')
                else:
                    body = full_msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                
                body_lower = body.lower()

                # C. Check Username (QUAN TRỌNG: BẮT BUỘC PHẢI KHỚP)
                if target_username:
                    if target_username.lower() not in body_lower:
                        print(f"   [IMAP] Skipped mail ID {mid}: Username '{target_username}' not found in body.")
                        continue 

                # D. Extract Code (6 đến 8 số)
                # Regex: \b(\d{6,8})\b -> Bắt số có độ dài từ 6 đến 8 ký tự nằm riêng biệt
                m = re.search(r'\b(\d{6,8})\b', body)
                
                if m:
                    found_code = m.group(1)
                    print(f"   [IMAP] => FOUND CODE: {found_code} (Subject: {subject})")
                    
                    # Đánh dấu đã đọc để không lấy lại lần sau
                    mail.store(mid, '+FLAGS', '\\Seen')
                    return found_code
                    
    except Exception as e:
        print(f"   [IMAP Error] {e}")
    finally:
        try: mail.logout()
        except: pass
    
    return None

# --- API CHO CÁC BƯỚC ---

def get_verify_code_v2(gmx_user, gmx_pass, target_ig_username):
    """
    Dùng cho Step 2: Verify Account (6 số).
    Subject keywords: verify, confirm, login code...
    """
    keywords = ["verify", "xác thực", "confirm", "login code"]
    return _fetch_latest_unseen_mail(gmx_user, gmx_pass, keywords, target_ig_username)

def get_2fa_code_v2(gmx_user, gmx_pass, target_ig_username):
    """
    Dùng cho Step 4: Authenticate Account (6 hoặc 8 số).
    Subject keywords: authenticate, two-factor, security code...
    """
    keywords = ["authenticate", "two-factor", "security", "bảo mật", "2fa"]
    return _fetch_latest_unseen_mail(gmx_user, gmx_pass, keywords, target_ig_username)