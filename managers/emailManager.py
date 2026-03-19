"""Email manager using Resend API."""

from logger_config import get_logger

logger = get_logger("floosball.email")


def _getResendConfig():
    """Get Resend API key and sender from config."""
    try:
        from config_manager import get_config
        cfg = get_config()
        apiKey = cfg.get("resendApiKey", "")
        emailFrom = cfg.get("emailFrom", "Floosball <noreply@floosball.com>")
        return apiKey, emailFrom
    except Exception:
        return "", "Floosball <noreply@floosball.com>"


def sendEmail(to: str, subject: str, html: str) -> bool:
    """Send an email via Resend. Returns True on success."""
    apiKey, emailFrom = _getResendConfig()
    if not apiKey:
        logger.debug("Resend API key not configured, skipping email")
        return False

    try:
        import resend
        resend.api_key = apiKey
        resend.Emails.send({
            "from": emailFrom,
            "to": [to],
            "subject": subject,
            "html": html,
        })
        logger.info(f"Email sent to {to}: {subject}")
        return True
    except Exception as e:
        logger.warning(f"Failed to send email to {to}: {e}")
        return False


def sendAccessApprovedEmail(email: str) -> bool:
    """Send a notification that beta access has been granted."""
    subject = "You've been granted access to Floosball"
    html = """
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto; padding: 32px; background: #0f172a; color: #e2e8f0; border-radius: 12px;">
        <h1 style="font-size: 24px; color: #e2e8f0; margin-bottom: 8px;">Welcome to Floosball</h1>
        <p style="font-size: 16px; color: #94a3b8; line-height: 1.6;">
            Your request to join the closed beta has been approved. You can now sign in and start playing.
        </p>
        <div style="background: #1e293b; border-radius: 8px; padding: 16px; margin: 20px 0; text-align: center;">
            <a href="https://floosball.com" style="color: #3b82f6; font-size: 16px; font-weight: 600; text-decoration: none;">
                Sign in to Floosball
            </a>
        </div>
        <hr style="border: none; border-top: 1px solid #334155; margin: 24px 0;" />
        <p style="font-size: 11px; color: #475569;">
            You're receiving this because you requested access to Floosball.
        </p>
    </div>
    """
    return sendEmail(email, subject, html)


def sendPrizeNotification(email: str, rank: int, prize: int, context: str) -> bool:
    """Send a leaderboard prize email."""
    subject = f"You placed #{rank} — {context}"
    html = f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto; padding: 32px; background: #0f172a; color: #e2e8f0; border-radius: 12px;">
        <h1 style="font-size: 24px; color: #e2e8f0; margin-bottom: 8px;">Congratulations!</h1>
        <p style="font-size: 16px; color: #94a3b8; line-height: 1.6;">
            You placed <strong style="color: #f59e0b;">#{rank}</strong> on the {context}!
        </p>
        <div style="background: #1e293b; border-radius: 8px; padding: 16px; margin: 20px 0; text-align: center;">
            <div style="font-size: 32px; font-weight: 700; color: #eab308;">+{prize}</div>
            <div style="font-size: 14px; color: #a16207; margin-top: 4px;">Floobits</div>
        </div>
        <p style="font-size: 13px; color: #64748b; line-height: 1.5;">
            Log in to Floosball to see your updated balance and keep competing!
        </p>
        <hr style="border: none; border-top: 1px solid #334155; margin: 24px 0;" />
        <p style="font-size: 11px; color: #475569;">
            You're receiving this because you have a Floosball account. To opt out, update your preferences in the app.
        </p>
    </div>
    """
    return sendEmail(email, subject, html)


def sendPrizeEmails(session, weekRanked: list, prizeMap: dict, context: str, topN: int = 3):
    """Send prize emails to top-N finishers who haven't opted out."""
    from database.models import User

    for i, entry in enumerate(weekRanked[:topN]):
        userId = entry.get('userId')
        rank = i + 1
        prize = prizeMap.get(rank)
        if not prize:
            continue

        try:
            user = session.query(User).filter_by(id=userId).first()
            if not user or user.email_opt_out:
                continue
            # Skip placeholder emails
            if user.email.endswith('@clerk.user'):
                continue
            sendPrizeNotification(user.email, rank, prize, context)
        except Exception as e:
            logger.warning(f"Error sending prize email to user {userId}: {e}")
