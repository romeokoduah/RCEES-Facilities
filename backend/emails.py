"""RCEES Facilities - Email Notification Service"""
import uuid, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from .database import get_db
from .config import (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM,
                     SMTP_ENABLED, SERVER_URL, ORG_NAME, ORG_SHORT, ORG_PHONE)


def _log_email(to, subject, preview, booking_id=""):
    conn = get_db()
    conn.execute("INSERT INTO email_log (id,to_email,subject,body_preview,related_booking) VALUES (?,?,?,?,?)",
                 (str(uuid.uuid4()), to, subject, preview[:200], booking_id))
    conn.commit(); conn.close()


def _send(to, subject, html_body):
    """Send email via SMTP or log if not configured."""
    preview = html_body[:200].replace("<", "").replace(">", "")
    if not SMTP_ENABLED:
        print(f"  📧 [SIMULATED] To: {to} | Subject: {subject}")
        _log_email(to, subject, preview)
        return True
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{ORG_SHORT} <{SMTP_FROM}>"
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(SMTP_FROM, to, msg.as_string())
        _log_email(to, subject, preview)
        return True
    except Exception as e:
        print(f"  ❌ Email failed: {e}")
        _log_email(to, subject, f"FAILED: {e}")
        return False


def _base(content):
    return f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:600px;margin:0 auto;background:#fff;border:1px solid #e5e5e5;border-radius:12px;overflow:hidden">
      <div style="background:#1a4731;color:#fff;padding:24px 28px">
        <h1 style="margin:0;font-size:20px;font-weight:600">{ORG_SHORT}</h1>
        <p style="margin:4px 0 0;font-size:12px;opacity:.6">{ORG_NAME}</p>
      </div>
      <div style="padding:28px">{content}</div>
      <div style="background:#f8f8f6;padding:16px 28px;font-size:11px;color:#888;border-top:1px solid #eee">
        {ORG_SHORT} · {ORG_PHONE}<br>This is an automated message. Please do not reply directly.
      </div>
    </div>"""


def send_booking_confirmation(booking, facility_name):
    """Send when a booking is first submitted."""
    to = booking.get("guest_email") or ""
    if not to:
        return
    name = booking.get("guest_name") or "Valued Guest"
    ref = booking["ref"]
    status = booking["status"]

    msg = "Your booking has been <strong>confirmed</strong>." if status == "confirmed" else "Your booking has been <strong>submitted and is awaiting approval</strong>. You will receive another email once approved."

    html = _base(f"""
        <h2 style="color:#1a4731;margin:0 0 16px">Booking {status.title()}!</h2>
        <p>Dear {name},</p>
        <p>{msg}</p>
        <table style="width:100%;border-collapse:collapse;margin:20px 0">
          <tr><td style="padding:8px 0;border-bottom:1px solid #eee;color:#888;width:140px">Reference</td>
              <td style="padding:8px 0;border-bottom:1px solid #eee;font-weight:700;font-family:monospace;font-size:16px;color:#1a4731">{ref}</td></tr>
          <tr><td style="padding:8px 0;border-bottom:1px solid #eee;color:#888">Facility</td>
              <td style="padding:8px 0;border-bottom:1px solid #eee;font-weight:600">{facility_name}</td></tr>
          <tr><td style="padding:8px 0;border-bottom:1px solid #eee;color:#888">Date</td>
              <td style="padding:8px 0;border-bottom:1px solid #eee">{booking["booking_date"]}</td></tr>
          <tr><td style="padding:8px 0;border-bottom:1px solid #eee;color:#888">Time</td>
              <td style="padding:8px 0;border-bottom:1px solid #eee">{booking["start_time"]} – {booking["end_time"]}</td></tr>
          <tr><td style="padding:8px 0;border-bottom:1px solid #eee;color:#888">Amount</td>
              <td style="padding:8px 0;border-bottom:1px solid #eee;font-weight:700">GH₵{booking["final_amount"]:.2f}</td></tr>
          <tr><td style="padding:8px 0;color:#888">Status</td>
              <td style="padding:8px 0"><span style="background:#fdf3d7;color:#92400e;padding:3px 12px;border-radius:20px;font-size:12px">{status}</span></td></tr>
        </table>
        <p style="color:#666;font-size:13px">You can track your booking anytime using reference <strong>{ref}</strong> on our website.</p>
    """)
    _send(to, f"Booking {status.title()} — {ref}", html)


def send_approval_with_payment_link(booking, facility_name):
    """Send when admin approves — includes payment link."""
    to = booking.get("guest_email") or ""
    if not to:
        return
    name = booking.get("guest_name") or "Valued Guest"
    ref = booking["ref"]
    token = booking.get("payment_token", "")
    pay_url = f"{SERVER_URL}/#pay/{token}" if token else f"{SERVER_URL}"

    html = _base(f"""
        <h2 style="color:#1a4731;margin:0 0 16px">\u2705 Booking Approved!</h2>
        <p>Dear {name},</p>
        <p>Great news! Your booking for <strong>{facility_name}</strong> has been <strong>approved</strong>.</p>
        <table style="width:100%;border-collapse:collapse;margin:20px 0">
          <tr><td style="padding:8px 0;border-bottom:1px solid #eee;color:#888;width:140px">Reference</td>
              <td style="padding:8px 0;border-bottom:1px solid #eee;font-weight:700;font-family:monospace;color:#1a4731">{ref}</td></tr>
          <tr><td style="padding:8px 0;border-bottom:1px solid #eee;color:#888">Date</td>
              <td style="padding:8px 0;border-bottom:1px solid #eee">{booking["booking_date"]}</td></tr>
          <tr><td style="padding:8px 0;border-bottom:1px solid #eee;color:#888">Time</td>
              <td style="padding:8px 0;border-bottom:1px solid #eee">{booking["start_time"]} – {booking["end_time"]}</td></tr>
          <tr><td style="padding:8px 0;color:#888">Amount Due</td>
              <td style="padding:8px 0;font-weight:700;font-size:18px;color:#1a4731">GH₵{booking["final_amount"]:.2f}</td></tr>
        </table>
        <p>Please proceed to make payment using the button below:</p>
        <div style="text-align:center;margin:24px 0">
          <a href="{pay_url}" style="background:#1a4731;color:#fff;padding:14px 36px;border-radius:10px;text-decoration:none;font-weight:600;font-size:15px;display:inline-block">
            💳 Proceed to Payment
          </a>
        </div>
        <p style="color:#666;font-size:13px">If the button doesn't work, copy this link: <a href="{pay_url}">{pay_url}</a></p>
    """)
    _send(to, f"Approved! Pay Now — {ref}", html)


def send_rejection(booking, facility_name, reason=""):
    """Send when admin rejects a booking."""
    to = booking.get("guest_email") or ""
    if not to:
        return
    name = booking.get("guest_name") or "Valued Guest"
    reason_html = f"<p><strong>Reason:</strong> {reason}</p>" if reason else ""

    html = _base(f"""
        <h2 style="color:#b91c1c;margin:0 0 16px">\u274c Booking Not Approved</h2>
        <p>Dear {name},</p>
        <p>We regret to inform you that your booking request <strong>{booking['ref']}</strong> for <strong>{facility_name}</strong> was not approved.</p>
        {reason_html}
        <p>You are welcome to submit a new booking for a different date or facility.</p>
        <div style="text-align:center;margin:24px 0">
          <a href="{SERVER_URL}" style="background:#1a4731;color:#fff;padding:12px 28px;border-radius:10px;text-decoration:none;font-weight:600;display:inline-block">Browse Facilities</a>
        </div>
    """)
    _send(to, f"Booking Not Approved — {booking['ref']}", html)


def send_payment_receipt(booking, facility_name, invoice_no):
    """Send payment receipt with invoice reference."""
    to = booking.get("guest_email") or ""
    if not to:
        return
    name = booking.get("guest_name") or "Valued Guest"
    ref = booking["ref"]

    html = _base(f"""
        <h2 style="color:#1a4731;margin:0 0 16px">\U0001f9fe Payment Received!</h2>
        <p>Dear {name},</p>
        <p>Your payment for booking <strong>{ref}</strong> has been received. Here are your details:</p>
        <table style="width:100%;border-collapse:collapse;margin:20px 0">
          <tr><td style="padding:8px 0;border-bottom:1px solid #eee;color:#888;width:140px">Booking Ref</td>
              <td style="padding:8px 0;border-bottom:1px solid #eee;font-weight:700;font-family:monospace">{ref}</td></tr>
          <tr><td style="padding:8px 0;border-bottom:1px solid #eee;color:#888">Invoice No</td>
              <td style="padding:8px 0;border-bottom:1px solid #eee;font-weight:600">{invoice_no}</td></tr>
          <tr><td style="padding:8px 0;border-bottom:1px solid #eee;color:#888">Facility</td>
              <td style="padding:8px 0;border-bottom:1px solid #eee">{facility_name}</td></tr>
          <tr><td style="padding:8px 0;border-bottom:1px solid #eee;color:#888">Date</td>
              <td style="padding:8px 0;border-bottom:1px solid #eee">{booking["booking_date"]} · {booking["start_time"]}–{booking["end_time"]}</td></tr>
          <tr><td style="padding:8px 0;color:#888">Amount Paid</td>
              <td style="padding:8px 0;font-weight:700;font-size:18px;color:#1a4731">GH₵{booking["final_amount"]:.2f}</td></tr>
        </table>
        <p>You can view and print your invoice/receipt at any time from our platform.</p>
        <div style="text-align:center;margin:24px 0">
          <a href="{SERVER_URL}/#invoice/{booking['id']}" style="background:#1a4731;color:#fff;padding:12px 28px;border-radius:10px;text-decoration:none;font-weight:600;display:inline-block">View Invoice</a>
        </div>
    """)
    _send(to, f"Payment Receipt — {invoice_no}", html)
