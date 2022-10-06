import time, socket, imaplib
from imap_tools import AND, NOT, MailBox, MailboxLoginError, MailboxLogoutError
import datetime
import logging
import config
import requests

class MailBoxHandler():
    def __init__(self, host, user, passwd, folder, filter):
        self.mailbox = MailBox(host)
        self.mailbox.login(user, passwd, folder)
        self.poll_from_date = None
        self.already_seen_in_poll_period = []
        self.running = False
        self.filter = filter

    def start_polling(self):
        if self.running:
            logging.warning("Already running")
            return
        self.running = True
        self.poll_from_date = datetime.datetime.now().date()
        self.poll() # prefil already_seen_in_poll_period

    def stop_polling(self):
        if not self.running:
            logging.warning("Was not running")
            return
        self.running = False
        self.poll_from_date = None
        self.already_seen_in_poll_period = []

    def poll(self):
        res = []
        future_poll_from_date = datetime.datetime.now().date()
        if not self.running:
            logging.error("Was not running")
            return
        for msg in self.mailbox.fetch(
            AND(
                config.IMAP_TOOLS_FILTER,
                NOT(uid=self.already_seen_in_poll_period) if len(self.already_seen_in_poll_period) else AND(all=True),
                date_gte=self.poll_from_date
            )
        ):
            self.already_seen_in_poll_period.append(msg.uid)
            res.append(msg)
        if future_poll_from_date != self.poll_from_date:
            self.poll_from_date = future_poll_from_date
            self.already_seen_in_poll_period = []
        return res


def send_mail_to_discord(mail):
    from_name = mail.from_values.name
    msg_from = f"{mail.from_values.name} ({mail.from_})" if mail.from_values.name != "" else mail.from_
    formated_body = mail.text.rstrip(" \n").lstrip(" \n").replace('\n\n', '\n')
    message = f"*Mail à chvd@groups.io de {msg_from}*\n\n**{mail.subject}**\n\n{formated_body}"
    requests.post(
        config.DISCORD_WEBHOOK, 
        json = {
            'content':message,
        }
    )

def main():
    mailbox = None
    try:
        mailbox = MailBoxHandler(
            config.MAIL_HOST, 
            config.MAIL_USER, 
            config.MAIL_PASSWORD, 
            config.MAIL_FOLDER,
            config.IMAP_TOOLS_FILTER
        )
        mailbox.start_polling()
        done = False
        while not done:
            msgs = mailbox.poll()
            for msg in msgs:
                send_mail_to_discord(msg)
            
            time.sleep(config.REFRESH_DELAY_SEC)

    except (TimeoutError, ConnectionError,
            imaplib.IMAP4.abort, MailboxLoginError, MailboxLogoutError,
            socket.herror, socket.gaierror, socket.timeout) as e:
        if mailbox is not None:
            mailbox.stop_polling()
        print(f"Error ({e}), reconnect in a minute")
        time.sleep(60)

if __name__ == "__main__":
    main()