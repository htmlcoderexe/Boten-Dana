from datetime import datetime

from botstate import BotState


class ScoreHelper:
    chatid = 0
    userid = 0
    today = datetime.now()

    def __init__(self, userid, chatid, today: datetime = None):
        self.userid = userid
        self.chatid = chatid
        self.today = today if today is not None else datetime.now()

    def add_scope(self, scorename: str, scope: str, delta: int):
        data1 = (self.userid, self.chatid, scorename, scope)
        data2 = (self.chatid, self.userid, scorename, scope, delta)
        res = BotState.DBLink.execute(
            "SELECT amount FROM scores where userid = ? AND chatid = ? AND scorename = ? AND scope = ? ", data1)
        row = res.fetchone()
        if row is None:
            BotState.DBLink.execute("INSERT INTO scores VALUES (?,?,?,?,?)", data2)
            BotState.write()
        else:
            amount = row[0]
            data3 = (amount + delta, self.chatid, self.userid, scorename, scope)
            BotState.DBLink.execute("""UPDATE scores
                SET amount = ?
                WHERE chatid = ?
                AND userid = ?
                AND scorename = ?
                AND scope = ?
                """, data3)
            BotState.write()

    def add(self,scorename:str,delta: int = 1):
        year = self.today.strftime("%Y")
        yearmonth = self.today.strftime("%Y-%m")
        yearmonthday = self.today.strftime("%Y-%m-%d")
        yearweek = self.today.strftime("%Y-w%W")
        self.add_scope(scorename=scorename,delta=delta,scope="all")
        self.add_scope(scorename=scorename,delta=delta,scope=year)
        self.add_scope(scorename=scorename,delta=delta,scope=yearmonth)
        self.add_scope(scorename=scorename,delta=delta,scope=yearmonthday)
        self.add_scope(scorename=scorename,delta=delta,scope=yearweek)

    def get_scope(self, scorename: str, scope: str):
        res = BotState.DBLink.execute("""
            SELECT amount 
            FROM scores 
            WHERE userid = ? 
            AND chatid = ? 
            AND scorename = ? 
            AND scope = ? """, (self.userid, self.chatid, scorename, scope))
        row = res.fetchone()
        if row is None:
            return 0
        else:
            return row[0]

    def get(self,scorename: str):
        year = self.today.strftime("%Y")
        yearmonth = self.today.strftime("%Y-%m")
        yearmonthday = self.today.strftime("%Y-%m-%d")
        yearweek = self.today.strftime("%Y-w%W")
        return \
            self.get_scope(scorename=scorename, scope="all"), \
            self.get_scope(scorename=scorename, scope=year), \
            self.get_scope(scorename=scorename, scope=yearmonth), \
            self.get_scope(scorename=scorename, scope=yearweek), \
            self.get_scope(scorename=scorename, scope=yearmonthday)

    def get_top(self,scorename: str, count: int = 1, scope: str = "all"):
        res = BotState.DBLink.execute("""
            SELECT ue.event_data as name, amount, userid
            FROM scores
            WHERE chatid = ?
            AND scorename = ?
            AND scope = ?
            LEFT JOIN 
                (SELECT event_data, userid, MAX(time) maxtime, time
                FROM user_events
                WHERE event_data <> "message"
                GROUP BY userid
                ORDER BY time DESC
                ) as ue 
            ORDER BY amount DESC
            LIMIT ? """, (self.chatid, scorename, scope, count))
        return res.fetchall()
