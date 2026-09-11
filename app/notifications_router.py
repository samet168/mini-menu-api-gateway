import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

logger = logging.getLogger("notifications_router")

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])

DB_PATH = os.environ.get("NOTIFICATIONS_DB_PATH", "/app/notifications.db")
# Fallback local path if running outside container
if not os.path.exists("/app") and not os.path.isabs(DB_PATH):
    DB_PATH = os.path.join(os.path.dirname(__file__), "notifications.db")


def get_db_connection() -> sqlite3.Connection:
    """Provides an SQLite connection with Row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initializes the notifications table and seeds initial records if empty."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS notifications (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    type TEXT NOT NULL,
                    target TEXT NOT NULL DEFAULT 'broadcast',
                    read INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    href TEXT,
                    action_label TEXT,
                    metadata_json TEXT
                )
                """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notif_created_at ON notifications(created_at DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notif_type ON notifications(type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notif_read ON notifications(read)")
            conn.commit()

            # Seed if empty
            cursor.execute("SELECT COUNT(*) as cnt FROM notifications")
            row = cursor.fetchone()
            if row and row["cnt"] == 0:
                logger.info("Seeding initial notifications in SQLite backend database...")
                now_iso = datetime.now(timezone.utc).isoformat()
                initial_seeds = [
                    (
                        f"notif-{uuid.uuid4().hex[:8]}",
                        "New Order #104 Received",
                        "Table 04 placed an order for 2x Iced Americano ($5.50).",
                        "order",
                        "kitchen",
                        0,
                        now_iso,
                        "/orders",
                        "View Order",
                        json.dumps({"orderId": "104", "table": "04", "amount": 5.50}),
                    ),
                    (
                        f"notif-{uuid.uuid4().hex[:8]}",
                        "Bakong KHQR Payment Confirmed",
                        "Received $5.50 from Samet Moeun via ABA KHQR for Table 04.",
                        "payment",
                        "finance",
                        0,
                        now_iso,
                        "/payments",
                        "Verify Settlement",
                        json.dumps({"trxId": "aba-khqr-7782", "currency": "USD", "amount": 5.50}),
                    ),
                    (
                        f"notif-{uuid.uuid4().hex[:8]}",
                        "Kitchen Expediter Alert",
                        "Kitchen display has 3 orders pending prep for over 8 minutes.",
                        "kitchen",
                        "kitchen",
                        0,
                        now_iso,
                        "/kitchen",
                        "Open KDS",
                        json.dumps({"urgentCount": 3}),
                    ),
                    (
                        f"notif-{uuid.uuid4().hex[:8]}",
                        "Table Status Updated",
                        "Table 02 turned Active. Guests seated.",
                        "system",
                        "staff",
                        1,
                        now_iso,
                        "/tables",
                        "Manage Tables",
                        json.dumps({"table": "02", "status": "ACTIVE"}),
                    ),
                    (
                        f"notif-{uuid.uuid4().hex[:8]}",
                        "System Health Normal",
                        "All microservices, KHQR gateway, and order printer relay operating normally.",
                        "system",
                        "broadcast",
                        1,
                        now_iso,
                        "/analytics",
                        "System Status",
                        json.dumps({"health": "operational"}),
                    ),
                ]
                cursor.executemany(
                    """
                    INSERT INTO notifications (id, title, message, type, target, read, created_at, href, action_label, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    initial_seeds,
                )
                conn.commit()
    except Exception as e:
        logger.error(f"Error initializing notifications DB: {e}")


# Run DB initialization on import
init_db()


# ==============================================================================
# SCHEMAS
# ==============================================================================

class CreateNotificationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=1000)
    type: str = Field(default="system")  # "order" | "payment" | "kitchen" | "system"
    target: str = Field(default="broadcast")  # "broadcast" | "kitchen" | "staff" | "finance"
    href: Optional[str] = None
    actionLabel: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class NotificationResponse(BaseModel):
    id: str
    title: str
    message: str
    type: str
    target: str
    read: bool
    createdAt: str
    href: Optional[str] = None
    actionLabel: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class NotificationListResponse(BaseModel):
    notifications: List[NotificationResponse]
    total: int
    unreadCount: int


# ==============================================================================
# ENDPOINTS
# ==============================================================================

@router.get("", response_model=NotificationListResponse)
def list_notifications(
    type: Optional[str] = Query(None, description="Filter by type: order, payment, kitchen, system"),
    read: Optional[str] = Query(None, description="Filter by read status: all, true, false, unread, read"),
    target: Optional[str] = Query(None, description="Filter by target: broadcast, kitchen, staff, finance"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Retrieves all notifications matching filters, ordered by most recent first."""
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()

        query_clauses = []
        params: List[Any] = []

        if type and type != "all":
            query_clauses.append("type = ?")
            params.append(type)

        if read:
            if read.lower() in ("false", "unread", "0"):
                query_clauses.append("read = 0")
            elif read.lower() in ("true", "read", "1"):
                query_clauses.append("read = 1")

        if target and target != "all":
            query_clauses.append("target = ?")
            params.append(target)

        where_sql = ("WHERE " + " AND ".join(query_clauses)) if query_clauses else ""

        # Count total matching
        count_sql = f"SELECT COUNT(*) as total FROM notifications {where_sql}"
        cursor.execute(count_sql, params)
        total = cursor.fetchone()["total"]

        # Count unread
        cursor.execute("SELECT COUNT(*) as unread FROM notifications WHERE read = 0")
        unread_count = cursor.fetchone()["unread"]

        # Fetch records
        select_sql = f"""
            SELECT id, title, message, type, target, read, created_at, href, action_label, metadata_json
            FROM notifications
            {where_sql}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        cursor.execute(select_sql, params + [limit, offset])
        rows = cursor.fetchall()

        results = []
        for r in rows:
            meta = None
            if r["metadata_json"]:
                try:
                    meta = json.loads(r["metadata_json"])
                except Exception:
                    pass
            results.append(
                NotificationResponse(
                    id=r["id"],
                    title=r["title"],
                    message=r["message"],
                    type=r["type"],
                    target=r["target"],
                    read=bool(r["read"]),
                    createdAt=r["created_at"],
                    href=r["href"],
                    actionLabel=r["action_label"],
                    metadata=meta,
                )
            )

        return NotificationListResponse(
            notifications=results,
            total=total,
            unreadCount=unread_count,
        )


@router.post("", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
def create_notification(req: CreateNotificationRequest):
    """Creates and persists a new notification into SQLite backend database."""
    init_db()
    notif_id = f"notif-{uuid.uuid4().hex[:10]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    meta_json = json.dumps(req.metadata) if req.metadata else None

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO notifications (id, title, message, type, target, read, created_at, href, action_label, metadata_json)
            VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
            """,
            (
                notif_id,
                req.title,
                req.message,
                req.type,
                req.target,
                now_iso,
                req.href,
                req.actionLabel,
                meta_json,
            ),
        )
        conn.commit()

    return NotificationResponse(
        id=notif_id,
        title=req.title,
        message=req.message,
        type=req.type,
        target=req.target,
        read=False,
        createdAt=now_iso,
        href=req.href,
        actionLabel=req.actionLabel,
        metadata=req.metadata,
    )


@router.patch("/{notif_id}/read", response_model=Dict[str, Any])
def mark_notification_read(notif_id: str):
    """Marks a single notification as read."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE notifications SET read = 1 WHERE id = ?", (notif_id,))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "ok", "id": notif_id, "read": True}


@router.post("/mark-all-read", response_model=Dict[str, Any])
def mark_all_notifications_read():
    """Marks all notifications as read."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE notifications SET read = 1 WHERE read = 0")
        updated_count = cursor.rowcount
        conn.commit()
    return {"status": "ok", "markedCount": updated_count}


@router.delete("/{notif_id}", response_model=Dict[str, Any])
def delete_notification(notif_id: str):
    """Deletes a specific notification."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM notifications WHERE id = ?", (notif_id,))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "ok", "deletedId": notif_id}


@router.delete("", response_model=Dict[str, Any])
def clear_notifications(type: Optional[str] = Query(None)):
    """Deletes all notifications, optionally filtering by type."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if type and type != "all":
            cursor.execute("DELETE FROM notifications WHERE type = ?", (type,))
        else:
            cursor.execute("DELETE FROM notifications")
        deleted_count = cursor.rowcount
        conn.commit()
    return {"status": "ok", "deletedCount": deleted_count}
