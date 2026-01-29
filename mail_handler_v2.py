# mail_handler_v2.py
import imaplib
import email
import re
import time
import socket
from email.header import decode_header

# Cấu hình GMX
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
            else:
                text += str(content)
        return text.strip()
    except:
        return str(header_value)

def _fetch_latest_unseen_mail(gmx_user, gmx_pass, subject_keywords, target_username=None, target_email=None, loop_duration=30):
    if not gmx_user or not gmx_pass: return None
    if "@" not in gmx_user: gmx_user += "@gmx.net"

    mail = None
    start_time = time.time()
    code_pattern = re.compile(r'\b(\d{6,8})\b')

    try:
        socket.setdefaulttimeout(20)
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        try:
            mail.login(gmx_user, gmx_pass)
        except Exception as e:
            if any(k in str(e).lower() for k in ["authentication failed", "login failed", "credentials"]):
                raise Exception("GMX_DIE")
            raise e

        print(f"   [IMAP] Connected. Scanning for User: {target_username} | Mail: {target_email}...")

        while time.time() - start_time < loop_duration:
            try:
                mail.select("INBOX") 
                status, messages = mail.uid('search', None, '(UNSEEN FROM "Instagram")')
                
                if status != "OK" or not messages[0]:
                    time.sleep(2.5); continue

                mail_ids = messages[0].split()
                mail_ids.sort(key=int, reverse=True)

                for mail_id in mail_ids[:3]:
                    # --- LỚP 1: Check Header ---
                    _, msg_header = mail.uid('fetch', mail_id, '(BODY.PEEK[HEADER])')
                    header_content = email.message_from_bytes(msg_header[0][1])
                    
                    subject = _decode_str(header_content.get("Subject", "")).lower()
                    sender = _decode_str(header_content.get("From", "")).lower()
                    to_addr = _decode_str(header_content.get("To", "")).lower() # Lấy địa chỉ người nhận

                    is_relevant = any(k.lower() in subject for k in subject_keywords)
                    if not is_relevant: continue 

                    # MARK SEEN NGAY LẬP TỨC (Chống đọc lại)
                    try: 
                        mail.uid('store', mail_id, '+FLAGS', '\\Seen')
                        print(f"   [IMAP] Marked mail {mail_id} as seen")
                    except Exception as e:
                        print(f"   [IMAP] Failed to mark seen: {e}")

                    # --- LỚP 2: CHECK NGƯỜI NHẬN (QUAN TRỌNG NHẤT) ---
                    # Nếu có truyền vào target_email (linked_mail), bắt buộc phải khớp
                    if target_email:
                        clean_target_mail = target_email.lower().strip()
                        if clean_target_mail not in to_addr:
                            print(f"   [IMAP] Skipped mail {mail_id}. 'To': {to_addr} != Target: {clean_target_mail}")
                            continue
                    
                    # --- LỚP 3: Tải Body ---
                    _, msg_data = mail.uid('fetch', mail_id, "(RFC822)")
                    full_msg = email.message_from_bytes(msg_data[0][1])
                    body = ""
                    if full_msg.is_multipart():
                        for part in full_msg.walk():
                            if part.get_content_type() == "text/plain":
                                body += part.get_payload(decode=True).decode('utf-8', errors='ignore'); break
                    else:
                        body = full_msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                    
                    if not body: body = ""
                    
                    # --- LỚP 4: Validate Username (Fallback nếu không có target_email) ---
                    # Chỉ check username nếu không có target_email (vì mail tối giản không có username)
                    if target_username and not target_email:
                        if target_username.lower().replace("@","") not in body.lower():
                            print(f"   [IMAP] Skipped mail (Username mismatch).")
                            continue

                    # --- LỚP 5: Lấy Code ---
                    match = code_pattern.search(body)
                    if match:
                        code = match.group(1)
                        print(f"   [IMAP] FOUND CODE: {code} for {target_username}")
                        return code
                    
            except Exception as loop_e:
                print(f"   [IMAP Loop Warn] {loop_e}"); time.sleep(2)
        
        print("   [IMAP] Timeout: No new code found."); return None

    except Exception as e:
        if str(e) == "GMX_DIE": raise e
        print(f"   [IMAP Error] {e}"); return None
    finally:
        if mail:
            try: mail.close(); mail.logout()
            except: pass

# --- UPDATE API: Thêm tham số target_email ---

def get_verify_code_v2(gmx_user, gmx_pass, target_ig_username, target_email=None):
    keywords = ["verify", "xác thực", "confirm", "code", "security", "mã bảo mật", "is your instagram code"]
    return _fetch_latest_unseen_mail(gmx_user, gmx_pass, keywords, target_ig_username, target_email, loop_duration=30)

def get_2fa_code_v2(gmx_user, gmx_pass, target_ig_username, target_email=None):
    keywords = ["authenticate", "two-factor", "security", "bảo mật", "2fa", "login code", "mã đăng nhập"]
    return _fetch_latest_unseen_mail(gmx_user, gmx_pass, keywords, target_ig_username, target_email, loop_duration=30)