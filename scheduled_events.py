"""
This module implements generic scheduled events.
"""
import time

from botstate import BotState


class ScheduledEvent:

    def __init__(self, event_type, chat_id, event_time, event_data):
        self.event_type = event_type
        """Event type"""
        self.chat_id = chat_id
        """Chat ID where the event belongs."""
        self.event_time = event_time
        """Time when the event is to occur."""
        self.event_data = event_data
        """Any additional data."""

    @staticmethod
    def fetch_events(event_type: str,chat_id:int = -1, event_time: float = -1, filters = None):
        """
        Retrieves and removes events that have been scheduled before current time.
        @param event_type: Type of the event to fetch.
        @param chat_id: Filter events to a specific chat (-1 for all events)
        @param event_time: Optional time to use instead of current (-1)
        @param filters: list of tuples for filtering, set as (data index, filter value)
        @return:
        """
        get_q="""
        SELECT chatid, time, data0, data1, data2, data3, data4, data5, data6, data7
        FROM scheduled_events
        WHERE etype == ?
        AND time < ?
        """
        del_q="""
        DELETE
        FROM scheduled_events
        WHERE etype == ?
        AND time < ?"""
        if event_time == -1:
            event_time = time.time()
        if filters is None:
            filters = []
        filter_list =[]
        q_list = [event_type, event_time]
        if chat_id != 0:
            filter_list.append(("chatid",chat_id))
        for col, val in filters:
            if 8 > col > 0:
                continue
            filter_list.append(("data" + str(col),val))
        for q_filter in filter_list:
            get_q = get_q + " AND " + q_filter[0] + " = ? "
            del_q = del_q + " AND " + q_filter[0] + " = ? "
            q_list.append(q_filter[1])
        res = BotState.DBLink.execute(get_q, tuple(q_list))
        rows = res.fetchall()
        BotState.DBLink.execute(del_q, tuple(q_list))
        events = []
        for row in rows:
            event = ScheduledEvent(event_type, row[0], row[1],row[2:])
            events.append(event)
        BotState.write()
        return events

    @staticmethod
    def schedule_event(event_type: str, chat_id:int, event_time:float = -1, *args):
        max7 = args[:8]
        exact7 = max7 + (("",) * (8 - len(max7)))
        BotState.DBLink.execute("""
        INSERT INTO scheduled_events
        VALUES (?,?,?, ?,?,?,?, ?,?,?,?)
        """,(event_type,chat_id,event_time,exact7))
        BotState.write()
