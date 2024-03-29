from imap_tools import (
    AND,
    NOT,
    MailBox,
    MailboxTaggedResponseError
)
import datetime
import logging
import requests


class MailBoxHandler:
    def __init__(self, host, user, passwd, folder, filter):
        self.host = host
        self.user = user
        self.passwd = passwd
        self.folder = folder
        self.filter = filter

        self.mailbox = None
        self.connect()
        self.poll_from_date = None
        self.already_seen_in_poll_period = []
        self.running = False

    def start_polling(self, prefill_data=None):
        if self.running:
            logging.warning("Already running")
            return
        self.running = True
        self.poll_from_date = datetime.datetime.now().date()
        msgs = self.poll()  # prefil already_seen_in_poll_period
        logging.debug(f"Skipping {[i.subject for i in msgs]}")

    def stop_polling(self):
        if not self.running:
            logging.warning("Was not running")
            return
        self.running = False
        self.poll_from_date = None
        self.already_seen_in_poll_period = []

    def disconnect(self):
        self.mailbox.logout()
        self.mailbox = None

    def connect(self):
        logging.info("(Re)connecting...")
        self.mailbox = MailBox(self.host)
        self.mailbox.login(self.user, self.passwd, self.folder)

    def poll(self):
        if self.mailbox is None:
            raise SystemError("Call connect method before polling")
        res = []
        future_poll_from_date = datetime.datetime.now().date()
        to_add_to_already_seen = []
        if not self.running:
            logging.error("Was not running")
            return
        try:
            self.mailbox.idle.wait(timeout=0)
        except MailboxTaggedResponseError:  # session expiration
            self.disconnect()
            self.connect()
        for msg in self.mailbox.fetch(
            AND(
                eval(self.filter),
                NOT(uid=self.already_seen_in_poll_period)
                if len(self.already_seen_in_poll_period)
                else AND(all=True),
                date_gte=self.poll_from_date,
            )
        ):
            to_add_to_already_seen.append(msg.uid)
            res.append(msg)
        if future_poll_from_date != self.poll_from_date:
            self.poll_from_date = future_poll_from_date
            self.already_seen_in_poll_period = []
        self.already_seen_in_poll_period.extend(to_add_to_already_seen)
        return res


def send_mail_to_discord(mail, webhook):
    from_name = mail.from_values.name
    msg_from = (
        f"{mail.from_values.name} ({mail.from_})"
        if mail.from_values.name != ""
        else mail.from_
    )
    formated_body = mail.text.rstrip(" \n").lstrip(" \n").replace("\n\n", "\n")
    message = f"*Mail à chvd@groups.io de {msg_from}*\n\n**{mail.subject}**\n\n{formated_body}"
    requests.post(
        webhook,
        json={
            "content": message,
        },
    )
