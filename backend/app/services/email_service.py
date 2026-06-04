"""
Email service for sending emails via Resend API.
"""
import logging
import resend
from typing import Optional
from ..config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails via Resend."""

    @staticmethod
    def send_password_setup_email(
        recipient_email: str,
        password_reset_url: str,
        user_name: Optional[str] = None
    ) -> bool:
        """
        Send password setup email to a user.

        Args:
            recipient_email: User's email address
            password_reset_url: URL for password reset (from Auth0 ticket)
            user_name: User's name (optional, defaults to email prefix)

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            display_name = user_name or recipient_email.split('@')[0]

            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                    }}
                    .container {{
                        background-color: #f9f9f9;
                        border-radius: 8px;
                        padding: 30px;
                        margin: 20px 0;
                    }}
                    .header {{
                        text-align: center;
                        margin-bottom: 30px;
                    }}
                    .header h1 {{
                        color: #2563eb;
                        margin: 0;
                    }}
                    .content {{
                        background-color: white;
                        padding: 25px;
                        border-radius: 6px;
                        margin: 20px 0;
                    }}
                    .button {{
                        display: inline-block;
                        padding: 12px 30px;
                        background-color: #2563eb;
                        color: white !important;
                        text-decoration: none;
                        border-radius: 6px;
                        margin: 20px 0;
                        font-weight: bold;
                    }}
                    .button:hover {{
                        background-color: #1d4ed8;
                    }}
                    .footer {{
                        text-align: center;
                        margin-top: 30px;
                        color: #666;
                        font-size: 12px;
                    }}
                    .link {{
                        color: #2563eb;
                        word-break: break-all;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Welcome to Trinity Platform</h1>
                    </div>

                    <div class="content">
                        <p>Hello {display_name},</p>

                        <p>You've been invited to join Trinity Platform! To get started, please set up your password by clicking the button below:</p>

                        <div style="text-align: center;">
                            <a href="{password_reset_url}" class="button">Set Up Password</a>
                        </div>

                        <p>Or copy and paste this link into your browser:</p>
                        <p><a href="{password_reset_url}" class="link">{password_reset_url}</a></p>

                        <p><strong>This link will expire in 5 days.</strong></p>

                        <p>If you didn't request this invitation, please ignore this email.</p>

                        <p>Best regards,<br>The Trinity Platform Team</p>
                    </div>

                    <div class="footer">
                        <p>This is an automated email. Please do not reply to this message.</p>
                    </div>
                </div>
            </body>
            </html>
            """

            text_body = f"""
Welcome to Trinity Platform!

Hello {display_name},

You've been invited to join Trinity Platform! To get started, please set up your password by visiting the link below:

{password_reset_url}

This link will expire in 5 days.

If you didn't request this invitation, please ignore this email.

Best regards,
The Trinity Platform Team
            """

            resend.api_key = settings.RESEND_API_KEY
            resend.Emails.send({
                "from": settings.RESEND_FROM_EMAIL,
                "to": [recipient_email],
                "reply_to": settings.RESEND_REPLY_TO,
                "subject": "Set Up Your Password - Trinity Platform",
                "html": html_body,
                "text": text_body,
            })

            logger.info(f"✅ Password setup email sent to {recipient_email}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to send password setup email to {recipient_email}: {e}")
            return False

    @staticmethod
    def send_client_added_notification(
        advisor_email: str,
        advisor_name: Optional[str],
        client_name: Optional[str],
        client_email: str,
        firm_name: Optional[str] = None,
    ) -> bool:
        """
        Send a notification email to a firm advisor when a new client is added
        and assigned as their primary client.

        Args:
            advisor_email: Advisor's email address
            advisor_name: Advisor's name (optional)
            client_name: Client's name (optional)
            client_email: Client's email address
            firm_name: Firm name (optional)

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            display_advisor_name = advisor_name or advisor_email.split("@")[0]
            display_client_name = client_name or client_email.split("@")[0]
            display_firm_name = firm_name or "your firm"

            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                    }}
                    .container {{
                        background-color: #f9f9f9;
                        border-radius: 8px;
                        padding: 30px;
                        margin: 20px 0;
                    }}
                    .header {{
                        text-align: center;
                        margin-bottom: 30px;
                    }}
                    .header h1 {{
                        color: #2563eb;
                        margin: 0;
                    }}
                    .content {{
                        background-color: white;
                        padding: 25px;
                        border-radius: 6px;
                        margin: 20px 0;
                    }}
                    .footer {{
                        text-align: center;
                        margin-top: 30px;
                        color: #666;
                        font-size: 12px;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>New Client Assigned</h1>
                    </div>

                    <div class="content">
                        <p>Hello {display_advisor_name},</p>

                        <p>A new client has been added to <strong>{display_firm_name}</strong> and assigned to you as the primary advisor:</p>

                        <ul>
                            <li><strong>Client Name:</strong> {display_client_name}</li>
                            <li><strong>Client Email:</strong> {client_email}</li>
                        </ul>

                        <p>You can log in to Trinity Platform to view and manage this client's engagements.</p>

                        <p>Best regards,<br>The Trinity Platform Team</p>
                    </div>

                    <div class="footer">
                        <p>This is an automated notification from Trinity Platform.</p>
                    </div>
                </div>
            </body>
            </html>
            """

            text_body = f"""
New Client Assigned - Trinity Platform

Hello {display_advisor_name},

A new client has been added to {display_firm_name} and assigned to you as the primary advisor:

  - Client Name: {display_client_name}
  - Client Email: {client_email}

You can log in to Trinity Platform to view and manage this client's engagements.

Best regards,
The Trinity Platform Team
            """

            resend.api_key = settings.RESEND_API_KEY
            resend.Emails.send({
                "from": settings.RESEND_FROM_EMAIL,
                "to": [advisor_email],
                "reply_to": settings.RESEND_REPLY_TO,
                "subject": "New Client Assigned to You - Trinity Platform",
                "html": html_body,
                "text": text_body,
            })

            logger.info(f"✅ Client added notification sent to {advisor_email}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to send client notification to {advisor_email}: {e}")
            return False
