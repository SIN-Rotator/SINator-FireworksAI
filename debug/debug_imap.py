import imaplib

HOST = "imap.gmx.net"
PORT = 993
PASS = "ZOE.jerry2024"

emails_to_try = [
    "zukunftsorientierte.energie@gmx.de",
    "zukunftsorientierte.energie@gmx.net",
    "zukunftsorientierte.energie@gmail.com",
]

for email_addr in emails_to_try:
    try:
        print(f"\n--- Trying {email_addr} ---")
        mail = imaplib.IMAP4_SSL(HOST, PORT)
        mail.login(email_addr, PASS)
        print(f"SUCCESS! Logged in as {email_addr}")
        
        mail.select("inbox")
        status, messages = mail.search(None, 'FROM', 'fireworks')
        if status == "OK" and messages[0]:
            msg_ids = messages[0].split()
            print(f"Found {len(msg_ids)} Fireworks emails")
        else:
            print("No Fireworks emails found")
        
        mail.logout()
        break
    except Exception as e:
        print(f"Failed: {e}")
