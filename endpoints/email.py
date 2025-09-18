import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import HTTPException
from sqlalchemy.orm import Session
import os
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class EmailService:
    def __init__(self):
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", 587))
        self.sender_email = os.getenv("emilylanga752@gmail.com")
        self.sender_password = os.getenv("uezuptqldijonugo")

        # Validate configuration
        if not all([self.sender_email, self.sender_password]):
            logger.warning("Email credentials not configured. Emails will not be sent.")

    async def send_email(self, to_email: str, subject: str, body: str) -> bool:
        """
        Send email using Gmail SMTP
        """
        # Check if email credentials are configured
        if not all([self.sender_email, self.sender_password]):
            logger.warning(f"Email not sent to {to_email}: Email credentials not configured")
            return False

        try:
            logger.info(f"Attempting to send email to {to_email} with subject: {subject}")

            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = to_email
            msg['Subject'] = subject

            # Add body to email
            msg.attach(MIMEText(body, 'html'))

            # Create server connection and send email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.ehlo()
            server.starttls()
            server.login(self.sender_email, self.sender_password)
            text = msg.as_string()
            server.sendmail(self.sender_email, to_email, text)
            server.quit()

            logger.info(f"Email successfully sent to {to_email}")
            return True

        except Exception as e:
            logger.error(f"Error sending email to {to_email}: {str(e)}")
            return False

    async def send_user_registration_email(self, user) -> bool:
        """Send email when user registers"""
        subject = "Welcome to Our Parking Service!"
        body = f"""
        <html>
        <body>
            <h2>Welcome, {user.username}!</h2>
            <p>Thank you for registering with our parking service.</p>
            <p>Your account has been successfully created.</p>
            <br>
            <p>Best regards,<br>Parking Service Team</p>
        </body>
        </html>
        """
        return await self.send_email(user.email, subject, body)

    async def send_vehicle_added_email(self, user, vehicle_plate: str) -> bool:
        """Send email when user adds a vehicle"""
        subject = "Vehicle Added Successfully"
        body = f"""
        <html>
        <body>
            <h2>Vehicle Added</h2>
            <p>Hello {user.username},</p>
            <p>Your vehicle with plate number <strong>{vehicle_plate}</strong> has been successfully added to your account.</p>
            <br>
            <p>Best regards,<br>Parking Service Team</p>
        </body>
        </html>
        """
        return await self.send_email(user.email, subject, body)

    async def send_dispute_email(self, user, ticket_id: int) -> bool:
        """Send email when user disputes a ticket"""
        subject = "Ticket Dispute Submitted"
        body = f"""
        <html>
        <body>
            <h2>Dispute Submitted</h2>
            <p>Hello {user.username},</p>
            <p>Your dispute for ticket #{ticket_id} has been submitted successfully.</p>
            <p>We will review your dispute and get back to you within 3-5 business days.</p>
            <br>
            <p>Best regards,<br>Parking Service Team</p>
        </body>
        </html>
        """
        return await self.send_email(user.email, subject, body)

    async def send_topup_email(self, user, amount: float, new_balance: float) -> bool:
        """Send email when user tops up balance"""
        subject = "Balance Top-up Successful"
        body = f"""
        <html>
        <body>
            <h2>Top-up Confirmation</h2>
            <p>Hello {user.username},</p>
            <p>Your account has been topped up with <strong>${amount:.2f}</strong>.</p>
            <p>Your new balance is: <strong>${new_balance:.2f}</strong></p>
            <br>
            <p>Best regards,<br>Parking Service Team</p>
        </body>
        </html>
        """
        return await self.send_email(user.email, subject, body)

    async def send_parking_start_email(self, user, session_id: int, location: str) -> bool:
        """Send email when user starts parking session"""
        subject = "Parking Session Started"
        body = f"""
        <html>
        <body>
            <h2>Parking Session Active</h2>
            <p>Hello {user.username},</p>
            <p>Your parking session (#{session_id}) has started at {location}.</p>
            <p>You will be charged based on the duration of your stay.</p>
            <br>
            <p>Best regards,<br>Parking Service Team</p>
        </body>
        </html>
        """
        return await self.send_email(user.email, subject, body)


def send_email_sync(self, to_email: str, subject: str, body: str) -> bool:
    """Synchronous version for debugging"""
    try:
        logger.info(f"SYNC: Attempting to send email to {to_email}")

        msg = MIMEMultipart()
        msg['From'] = self.sender_email
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))

        with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(self.sender_email, self.sender_password)
            server.sendmail(self.sender_email, to_email, msg.as_string())

        logger.info(f"SYNC: Email sent successfully to {to_email}")
        return True

    except Exception as e:
        logger.error(f"SYNC: Error sending email: {str(e)}")
        return False


# Create global email service instance
email_service = EmailService()
