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
    inner = """
        <h1 style="font-size: 24px; color: #e2e8f0; margin-bottom: 8px;">Welcome to Floosball</h1>
        <p style="font-size: 16px; color: #94a3b8; line-height: 1.6;">
            Your request to join the closed beta has been approved. You can now sign in and start playing.
        </p>
        <div style="background: #1e293b; border-radius: 8px; padding: 16px; margin: 20px 0; text-align: center;">
            <a href="https://floosball.com" style="color: #3b82f6; font-size: 16px; font-weight: 600; text-decoration: none;">
                Sign in to Floosball
            </a>
        </div>
    """
    return sendEmail(email, subject, _wrapEmailHtml(inner))


def sendOnboardingReminderEmail(email: str) -> bool:
    """Send a reminder to users who signed up but haven't completed onboarding."""
    subject = "Finish setting up your Floosball account"
    inner = """
        <h1 style="font-size: 22px; color: #e2e8f0; margin-bottom: 8px;">You're almost there</h1>
        <p style="font-size: 15px; color: #94a3b8; line-height: 1.6;">
            You created a Floosball account but haven't finished setting up yet.
            Pick a username and choose a favorite team to start playing.
        </p>
        <div style="background: #1e293b; border-radius: 8px; padding: 16px; margin: 20px 0; text-align: center;">
            <a href="https://floosball.com" style="color: #3b82f6; font-size: 16px; font-weight: 600; text-decoration: none;">
                Finish Setup
            </a>
        </div>
    """
    return sendEmail(email, subject, _wrapEmailHtml(inner))


def _buildStatRow(label: str, value: str, color: str = "#e2e8f0") -> str:
    """Build a single stat row for email templates."""
    return f"""
    <tr>
        <td style="padding: 8px 0; font-size: 13px; color: #94a3b8; border-bottom: 1px solid #1e293b;">{label}</td>
        <td style="padding: 8px 0; font-size: 13px; color: {color}; font-weight: 600; text-align: right; border-bottom: 1px solid #1e293b;">{value}</td>
    </tr>"""


_EMAIL_FONT = "'Inconsolata', 'Courier New', monospace"
_FONT_IMPORT = '@import url("https://fonts.googleapis.com/css2?family=Inconsolata:wght@400;600;700");'


_LOGO_URL = "https://floosball.com/logo192.png"


def _wrapEmailHtml(innerHtml: str) -> str:
    """Wrap email body with font import, logo header, and outer container."""
    return f"""
    <style>{_FONT_IMPORT}</style>
    <div style="font-family: {_EMAIL_FONT}; max-width: 480px; margin: 0 auto; padding: 32px; background: #0f172a; color: #e2e8f0; border-radius: 12px;">
        <div style="text-align: center; margin-bottom: 20px;">
            <img src="{_LOGO_URL}" alt="Floosball" width="40" height="40" style="display: inline-block;" />
        </div>
        {innerHtml}
        <hr style="border: none; border-top: 1px solid #334155; margin: 24px 0;" />
        <p style="font-size: 11px; color: #475569;">
            You're receiving this because you have a Floosball account. To change email preferences, visit your profile settings in the app.
        </p>
    </div>
    """


def _buildTeamSection(favTeam: dict, isSeasonEnd: bool = False) -> str:
    """Build the favorite team section for email templates."""
    if not favTeam:
        return ""

    record = f"{favTeam['wins']}-{favTeam['losses']}"
    if favTeam.get('ties', 0) > 0:
        record += f"-{favTeam['ties']}"

    rows = f'<div style="font-size: 13px; color: #94a3b8; margin-bottom: 6px;">Record: <span style="color: #e2e8f0; font-weight: 600;">{record}</span></div>'

    if isSeasonEnd and favTeam.get('playoffResult'):
        rows += f'<div style="font-size: 13px; color: #c084fc; font-weight: 600; margin-bottom: 6px;">{favTeam["playoffResult"]}</div>'

    # Playoff qualification (day 4 email)
    if 'madePlayoffs' in favTeam:
        if favTeam['madePlayoffs']:
            rows += '<div style="font-size: 13px; color: #4ade80; font-weight: 600; margin-bottom: 6px;">Qualified for Playoffs</div>'
        else:
            rows += '<div style="font-size: 13px; color: #f87171; font-weight: 600; margin-bottom: 6px;">Eliminated from Playoff Contention</div>'

    todayGames = favTeam.get('todayGames', [])
    for g in todayGames:
        result = "W" if g['won'] else "L"
        resultColor = "#4ade80" if g['won'] else "#f87171"
        homeAway = "vs" if g['isHome'] else "@"
        rows += f'<div style="font-size: 13px; margin-top: 4px;"><span style="color: {resultColor}; font-weight: 600;">{result}</span> <span style="color: #94a3b8;">{homeAway} {g["opponent"]}</span> <span style="color: #e2e8f0;">{g["score"]}</span></div>'

    return f"""
    <div style="background: #1e293b; border-radius: 8px; padding: 14px; margin-top: 16px;">
        <div style="font-size: 14px; font-weight: 600; color: #e2e8f0; margin-bottom: 8px;">{favTeam['name']}</div>
        {rows}
    </div>"""


def sendDayReport(email: str, data: dict) -> bool:
    """Send a game day recap email."""
    season = data['season']
    dayNum = data['dayNum']
    dayFP = data.get('dayFP', 0)
    seasonFP = data.get('seasonFP', 0)
    seasonRank = data.get('seasonRank', 0)
    totalUsers = data.get('totalUsers', 0)
    floobitsEarned = data.get('floobitsEarned', 0)
    leaderboardPrizes = data.get('leaderboardPrizes', [])
    pickEm = data.get('pickEm', {})
    favTeam = data.get('favoriteTeam')
    leaderboardTop = data.get('leaderboardTop', [])
    pickEmLeaderboardTop = data.get('pickEmLeaderboardTop', [])
    userPickEmSeasonRank = data.get('userPickEmSeasonRank', 0)
    pickEmTotalUsers = data.get('pickEmTotalUsers', 0)
    achievementsToday = data.get('achievementsToday', [])
    isDay4 = (dayNum == 4)

    if isDay4:
        subject = f"Regular Season Complete \u2014 Season {season}"
    else:
        subject = f"Day {dayNum} Report \u2014 Season {season}"

    # Build stats table rows
    statsRows = _buildStatRow("Fantasy Points Today", f"+{dayFP:.1f} FP", "#4ade80")
    statsRows += _buildStatRow("Season Total", f"{seasonFP:.1f} FP")
    if totalUsers > 0:
        statsRows += _buildStatRow("Season Rank", f"#{seasonRank} of {totalUsers}")
    if floobitsEarned > 0:
        statsRows += _buildStatRow("Floobits Earned", f"+{floobitsEarned}", "#eab308")

    # Leaderboard prizes
    prizeHtml = ""
    if leaderboardPrizes:
        prizeItems = ""
        for p in leaderboardPrizes:
            prizeItems += f'<div style="font-size: 13px; color: #e2e8f0; padding: 4px 0;"><span style="color: #f59e0b; font-weight: 600;">#{p["rank"]}</span> Week {p["week"]} \u2014 <span style="color: #eab308; font-weight: 600;">+{p["prize"]} Floobits</span></div>'
        prizeHtml = f"""
        <div style="background: rgba(234,179,8,0.08); border: 1px solid rgba(234,179,8,0.2); border-radius: 8px; padding: 12px; margin-top: 16px;">
            <div style="font-size: 12px; color: #a16207; font-weight: 600; margin-bottom: 6px;">Leaderboard Finishes</div>
            {prizeItems}
        </div>"""

    # Pick-em section
    if pickEm.get('total', 0) > 0:
        correct = pickEm.get('correct', 0)
        total = pickEm['total']
        pct = round(correct / total * 100) if total > 0 else 0
        pickEmRow = f'{correct}/{total} correct ({pct}%)'
        pickEmFloobits = pickEm.get('floobitsEarned', 0)
        statsRows += _buildStatRow("Pick-Em", pickEmRow)
        if pickEmFloobits > 0:
            statsRows += _buildStatRow("Pick-Em Floobits", f"+{pickEmFloobits}", "#eab308")

    # Favorite team
    teamHtml = _buildTeamSection(favTeam)

    # Day 4: season fantasy leaderboard
    leaderboardHtml = ""
    if isDay4 and leaderboardTop:
        userRank = data.get('userSeasonRank', 0)
        lbRows = ""
        for entry in leaderboardTop:
            isUser = (entry['rank'] == userRank)
            nameColor = "#818cf8" if isUser else "#e2e8f0"
            rowBg = "rgba(99,102,241,0.08)" if isUser else "transparent"
            lbRows += f"""<tr style="background: {rowBg};">
                <td style="padding: 5px 8px; font-size: 12px; color: #94a3b8; font-weight: 600;">#{entry['rank']}</td>
                <td style="padding: 5px 8px; font-size: 12px; color: {nameColor}; font-weight: {'700' if isUser else '400'};">{entry['username']}</td>
                <td style="padding: 5px 8px; font-size: 12px; color: #e2e8f0; font-weight: 600; text-align: right;">{entry['seasonTotal']}</td>
            </tr>"""
        leaderboardHtml = f"""
        <div style="background: #1e293b; border-radius: 8px; padding: 14px; margin-top: 16px;">
            <div style="font-size: 13px; font-weight: 700; color: #e2e8f0; margin-bottom: 10px;">Season Fantasy Leaderboard</div>
            <table style="width: 100%; border-collapse: collapse;">{lbRows}</table>
            {f'<div style="font-size: 12px; color: #94a3b8; margin-top: 8px; text-align: center;">Your rank: <span style="color: #818cf8; font-weight: 600;">#{userRank}</span> of {totalUsers}</div>' if userRank > 10 else ''}
        </div>"""

    # Prognostication leaderboard (all days)
    pickEmLeaderboardHtml = ""
    if pickEmLeaderboardTop:
        peRows = ""
        for entry in pickEmLeaderboardTop:
            isUser = (entry['rank'] == userPickEmSeasonRank)
            nameColor = "#818cf8" if isUser else "#e2e8f0"
            rowBg = "rgba(99,102,241,0.08)" if isUser else "transparent"
            record = f"{entry['correct']}/{entry['total']}"
            peRows += f"""<tr style="background: {rowBg};">
                <td style="padding: 5px 8px; font-size: 12px; color: #94a3b8; font-weight: 600;">#{entry['rank']}</td>
                <td style="padding: 5px 8px; font-size: 12px; color: {nameColor}; font-weight: {'700' if isUser else '400'};">{entry['username']}</td>
                <td style="padding: 5px 8px; font-size: 12px; color: #64748b; text-align: right;">{record}</td>
                <td style="padding: 5px 8px; font-size: 12px; color: #e2e8f0; font-weight: 600; text-align: right;">{entry['points']}</td>
            </tr>"""
        userRankFooter = ""
        if userPickEmSeasonRank > 10 and pickEmTotalUsers > 0:
            userRankFooter = f'<div style="font-size: 12px; color: #94a3b8; margin-top: 8px; text-align: center;">Your rank: <span style="color: #818cf8; font-weight: 600;">#{userPickEmSeasonRank}</span> of {pickEmTotalUsers}</div>'
        pickEmLeaderboardHtml = f"""
        <div style="background: #1e293b; border-radius: 8px; padding: 14px; margin-top: 16px;">
            <div style="font-size: 13px; font-weight: 700; color: #e2e8f0; margin-bottom: 10px;">Prognostication Leaderboard</div>
            <table style="width: 100%; border-collapse: collapse;">{peRows}</table>
            {userRankFooter}
        </div>"""

    # Achievements unlocked today
    achievementsHtml = ""
    if achievementsToday:
        achRows = ""
        for ach in achievementsToday:
            achRows += f"""
            <div style="padding: 8px 0; border-bottom: 1px solid #1e293b;">
                <div style="font-size: 13px; color: #fbbf24; font-weight: 700;">{ach['name']}</div>
                <div style="font-size: 12px; color: #94a3b8; margin-top: 2px;">{ach['description']}</div>
            </div>"""
        achievementsHtml = f"""
        <div style="background: rgba(251,191,36,0.06); border: 1px solid rgba(251,191,36,0.2); border-radius: 8px; padding: 14px; margin-top: 16px;">
            <div style="font-size: 13px; font-weight: 700; color: #fbbf24; margin-bottom: 4px;">Achievements Unlocked</div>
            {achRows}
        </div>"""

    heading = "Regular Season Complete" if isDay4 else f"Day {dayNum} Report"
    subheading = f"Season {season} \u2014 Playoffs begin tomorrow" if isDay4 else f"Season {season}"

    inner = f"""
        <h1 style="font-size: 22px; color: #e2e8f0; margin-bottom: 4px;">{heading}</h1>
        <p style="font-size: 13px; color: #64748b; margin-bottom: 20px;">{subheading}</p>

        <table style="width: 100%; border-collapse: collapse;">
            {statsRows}
        </table>

        {prizeHtml}
        {achievementsHtml}
        {leaderboardHtml}
        {pickEmLeaderboardHtml}
        {teamHtml}

        <div style="margin-top: 24px; text-align: center;">
            <a href="https://floosball.com" style="color: #3b82f6; font-size: 14px; font-weight: 600; text-decoration: none;">
                View Full Standings
            </a>
        </div>
    """
    return sendEmail(email, subject, _wrapEmailHtml(inner))


def sendSeasonReport(email: str, data: dict) -> bool:
    """Send a season-end summary email (after playoffs)."""
    season = data['season']
    totalFloobitsEarned = data.get('totalFloobitsEarned', 0)
    bestWeeklyRank = data.get('bestWeeklyRank')
    seasonPrize = data.get('seasonPrize')
    pickEm = data.get('pickEm', {})
    favTeam = data.get('favoriteTeam')
    champion = data.get('champion')

    subject = f"Season {season} Final Report"

    # Build stats table
    statsRows = ""
    if totalFloobitsEarned > 0:
        statsRows += _buildStatRow("Floobits Earned (Season)", f"+{totalFloobitsEarned}", "#eab308")
    if bestWeeklyRank:
        statsRows += _buildStatRow("Best Weekly Finish", f"#{bestWeeklyRank}")
    if seasonPrize:
        statsRows += _buildStatRow("Season Leaderboard Prize", f"+{seasonPrize} Floobits", "#f59e0b")

    # Pick-em (full season including playoffs)
    if pickEm.get('total', 0) > 0:
        correct = pickEm.get('correct', 0)
        total = pickEm['total']
        pct = round(correct / total * 100) if total > 0 else 0
        statsRows += _buildStatRow("Pick-Em Record", f'{correct}/{total} ({pct}%)')

    # Champion announcement
    championHtml = ""
    if champion:
        championHtml = f"""
        <div style="background: rgba(234,179,8,0.08); border: 1px solid rgba(234,179,8,0.25); border-radius: 8px; padding: 14px; margin-bottom: 16px; text-align: center;">
            <div style="font-size: 11px; color: #a16207; font-weight: 600; margin-bottom: 4px;">Floosbowl Champions</div>
            <div style="font-size: 16px; color: #fbbf24; font-weight: 700;">{champion}</div>
        </div>"""

    # Favorite team
    teamHtml = _buildTeamSection(favTeam, isSeasonEnd=True)

    statsTable = f"""
        <table style="width: 100%; border-collapse: collapse;">
            {statsRows}
        </table>""" if statsRows else ""

    inner = f"""
        <h1 style="font-size: 22px; color: #e2e8f0; margin-bottom: 4px;">Season {season} Complete</h1>
        <p style="font-size: 13px; color: #64748b; margin-bottom: 20px;">The Floosbowl has been decided.</p>

        {championHtml}
        {statsTable}
        {teamHtml}

        <div style="margin-top: 24px; text-align: center;">
            <a href="https://floosball.com" style="color: #3b82f6; font-size: 14px; font-weight: 600; text-decoration: none;">
                View Season Results
            </a>
        </div>
    """
    return sendEmail(email, subject, _wrapEmailHtml(inner))
