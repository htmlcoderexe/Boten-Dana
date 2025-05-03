"""
This module interacts with editing sessions.
"""
import time

from botstate import BotState


class EditSession:
    session_timeout = 2 * 24 * 60 * 60
    """Session timeout in seconds."""

    @staticmethod
    def find_sessions(type_:str, user: int) -> list[str]:
        """
        Finds session of a specific type by user.
        @param type_: Session type.
        @param user: User to search for.
        @return: A list containing found session data as strings. May be empty.
        """
        res = BotState.DBLink.execute("""
            SELECT session_data FROM edit_sessions
            WHERE userid = ?
            AND session_type = ?
            """, (user, type_))
        return [row[0] for row in res.fetchall()]

    @staticmethod
    def clear_old_sessions() -> int:
        """
        Removes editing sessions with last activity older than the timeout.
        @return: Amount of sessions cleaned.
        """
        expiry = time.time() - EditSession.session_timeout
        res = BotState.DBLink.execute("""
        DELETE FROM edit_sessions
        WHERE last_active < ?
        """, (expiry,))
        print(f"Cleaned up {res.rowcount} inactive sessions.")
        return res.rowcount

    @staticmethod
    def exists(type_: str, user: int, data: str):
        res = BotState.DBLink.execute("""
                    SELECT session_data FROM edit_sessions
                    WHERE userid = ?
                    AND session_type = ?
                    AND session_data = ?
                    """, (user, type_, data))
        return len(res.fetchall()) > 0

    @staticmethod
    def refresh(type_: str, user: int, data: str) -> bool:
        """
        Resets a session's last activity time.
        @param type_: Session type
        @param user: User ID of the session's owner
        @param data: Data used to identify the specific session
        @return: True if a session was found and refreshed, False otherwise.
        """
        res = BotState.DBLink.execute("""
        UPDATE edit_sessions
        SET last_active = ?
        WHERE session_type = ?
        AND userid = ?
        AND session_data = ?
        """, (time.time(),type_, user, data))
        return res.rowcount > 0

    @staticmethod
    def begin(type_: str, user: int, data: str):
        """
        Begins a session. If a session already exists, refreshes it.
        @param type_: Session type
        @param user: User ID of the session's owner
        @param data: Data used to identify the specific session
        @return: True if session was begun or refreshed, False otherwise.
        """
        if EditSession.refresh(type_, user, data):
            return True
        res = BotState.DBLink.execute("""
        INSERT INTO edit_sessions
        VALUES (?, ?, ?, ?, ?)
        """,(user,type_, data, time.time(), time.time()))
        return res.rowcount > 0

    @staticmethod
    def end(type_: str, user: int, data: str):
        """
        Ends a session.
        @param type_: Session type
        @param user: User ID of the session's owner
        @param data: Data used to identify the specific session
        @return:
        """
        res = BotState.DBLink.execute("""
                DELETE FROM edit_sessions
                WHERE userid = ?
                AND session_type = ?
                AND session_data = ?
                """, (user, type_, data))
        return res.rowcount > 0
