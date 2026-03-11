"""Repository for user notification operations."""

import json
from typing import List, Optional
from sqlalchemy.orm import Session

from database.models import UserNotification


class NotificationRepository:
    """Repository for user notification CRUD operations."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, userId: int, notifType: str, title: str, message: str,
               data: Optional[dict] = None) -> UserNotification:
        """Create a new notification for a user."""
        notif = UserNotification(
            user_id=userId,
            type=notifType,
            title=title,
            message=message,
            data=json.dumps(data) if data else None,
        )
        self.session.add(notif)
        return notif

    def getUnread(self, userId: int, limit: int = 50) -> List[UserNotification]:
        """Get unread notifications for a user, newest first."""
        return (
            self.session.query(UserNotification)
            .filter_by(user_id=userId, is_read=False)
            .order_by(UserNotification.created_at.desc())
            .limit(limit)
            .all()
        )

    def getRecent(self, userId: int, limit: int = 20) -> List[UserNotification]:
        """Get recent notifications for a user (read and unread), newest first."""
        return (
            self.session.query(UserNotification)
            .filter_by(user_id=userId)
            .order_by(UserNotification.created_at.desc())
            .limit(limit)
            .all()
        )

    def getUnreadCount(self, userId: int) -> int:
        """Get the count of unread notifications for a user."""
        return (
            self.session.query(UserNotification)
            .filter_by(user_id=userId, is_read=False)
            .count()
        )

    def markRead(self, userId: int, notificationId: int) -> bool:
        """Mark a single notification as read. Returns True if found and updated."""
        notif = (
            self.session.query(UserNotification)
            .filter_by(id=notificationId, user_id=userId)
            .first()
        )
        if notif:
            notif.is_read = True
            return True
        return False

    def markAllRead(self, userId: int) -> int:
        """Mark all unread notifications as read. Returns count updated."""
        count = (
            self.session.query(UserNotification)
            .filter_by(user_id=userId, is_read=False)
            .update({"is_read": True})
        )
        return count
