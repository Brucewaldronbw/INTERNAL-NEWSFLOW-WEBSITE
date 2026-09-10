"""Delivery of the morning brief.

Three transports, tried in the order configured. All of them send the same
multipart/related message so the charts appear inline (cid:) rather than as
attachments the reader has to open - which is what Outlook needs.

  SMTP    - SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, MAIL_FROM
            (works with Microsoft 365, Google Workspace, SendGrid, Resend SMTP)
  Graph   - GRAPH_TENANT_ID, GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET, MAIL_FROM
            (Microsoft 365 app-only sending, no password needed)
  Resend  - RESEND_API_KEY, MAIL_FROM
"""
from __future__ import annotations

import base64
import logging
import mimetypes
import os
import pathlib
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

import requests

from . import config

LOG = logging.getLogger("newsflow.mailer")

FROM_NAME = os.environ.get("MAIL_FROM_NAME", "Moyne Roberts Newsflow")
GRAPH_SCOPE = "https://graph.microsoft.com/.default"


class MailNotConfigured(RuntimeError):
    """No transport has credentials - the caller decides whether that is fatal."""


def configured_transport() -> str | None:
    if os.environ.get("SMTP_HOST") and os.environ.get("MAIL_FROM"):
        return "smtp"
    if all(os.environ.get(k) for k in ("GRAPH_TENANT_ID", "GRAPH_CLIENT_ID",
                                       "GRAPH_CLIENT_SECRET", "MAIL_FROM")):
        return "graph"
    if os.environ.get("RESEND_API_KEY") and os.environ.get("MAIL_FROM"):
        return "resend"
    return None


def build_message(subject: str, html: str, text: str, images: dict[str, pathlib.Path],
                  recipients: list[str], sender: str) -> tuple[EmailMessage, dict[str, str]]:
    """Return the message plus the cid map actually used (html must already
    reference `cid:<key>` placeholders - we substitute real Message-IDs)."""
    cids = {key: make_msgid(domain="newsflow.moyneroberts")[1:-1] for key in images}
    for key, cid in cids.items():
        html = html.replace(f"cid:{key}", f"cid:{cid}")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((FROM_NAME, sender))
    msg["To"] = ", ".join(recipients)
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")

    html_part = msg.get_payload()[-1]
    for key, path in images.items():
        if not path.exists():
            continue
        ctype, _ = mimetypes.guess_type(path.name)
        maintype, _, subtype = (ctype or "image/png").partition("/")
        html_part.add_related(path.read_bytes(), maintype=maintype, subtype=subtype,
                              cid=f"<{cids[key]}>", filename=path.name)
    return msg, cids


def _send_smtp(msg: EmailMessage) -> None:
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASS")
    context = ssl.create_default_context()

    if port == 465:
        server = smtplib.SMTP_SSL(host, port, timeout=60, context=context)
    else:
        server = smtplib.SMTP(host, port, timeout=60)
    with server:
        server.ehlo()
        if port != 465:
            try:
                server.starttls(context=context)
                server.ehlo()
            except smtplib.SMTPNotSupportedError:
                LOG.warning("SMTP server does not advertise STARTTLS")
        if user and password:
            server.login(user, password)
        server.send_message(msg)
    LOG.info("brief sent via SMTP %s:%s", host, port)


def _graph_token() -> str:
    tenant = os.environ["GRAPH_TENANT_ID"]
    resp = requests.post(
        f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
        data={
            "client_id": os.environ["GRAPH_CLIENT_ID"],
            "client_secret": os.environ["GRAPH_CLIENT_SECRET"],
            "scope": GRAPH_SCOPE,
            "grant_type": "client_credentials",
        },
        timeout=45,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _send_graph(msg: EmailMessage, sender: str) -> None:
    token = _graph_token()
    resp = requests.post(
        f"https://graph.microsoft.com/v1.0/users/{sender}/sendMail",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "text/plain"},
        data=base64.b64encode(msg.as_bytes()),
        timeout=90,
    )
    if resp.status_code not in (200, 202):
        raise RuntimeError(f"Graph sendMail failed: {resp.status_code} {resp.text[:400]}")
    LOG.info("brief sent via Microsoft Graph as %s", sender)


def _send_resend(subject: str, html: str, text: str, images: dict[str, pathlib.Path],
                 recipients: list[str], sender: str) -> None:
    attachments = []
    for key, path in images.items():
        if not path.exists():
            continue
        html = html.replace(f"cid:{key}", f"cid:{path.name}")
        attachments.append({
            "filename": path.name,
            "content": base64.b64encode(path.read_bytes()).decode(),
            "content_id": path.name,
            "disposition": "inline",
        })
    resp = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {os.environ['RESEND_API_KEY']}"},
        json={"from": f"{FROM_NAME} <{sender}>", "to": recipients, "subject": subject,
              "html": html, "text": text, "attachments": attachments},
        timeout=90,
    )
    if resp.status_code >= 300:
        raise RuntimeError(f"Resend failed: {resp.status_code} {resp.text[:400]}")
    LOG.info("brief sent via Resend")


def send(subject: str, html: str, text: str, images: dict[str, pathlib.Path],
         recipients: list[str] | None = None) -> str:
    recipients = recipients or config.RECIPIENTS
    transport = configured_transport()
    if transport is None:
        raise MailNotConfigured(
            "No email transport configured. Set SMTP_HOST/SMTP_USER/SMTP_PASS/MAIL_FROM "
            "(or GRAPH_* / RESEND_API_KEY) as repository secrets."
        )
    sender = os.environ["MAIL_FROM"]

    if transport == "resend":
        _send_resend(subject, html, text, images, recipients, sender)
        return transport

    msg, _ = build_message(subject, html, text, images, recipients, sender)
    if transport == "smtp":
        _send_smtp(msg)
    else:
        _send_graph(msg, sender)
    return transport
