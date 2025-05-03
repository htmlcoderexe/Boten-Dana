from datetime import datetime
from actions import TriggeredAction
from telegram import Message as TGMessage
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

    def add(self,scorename:str,delta: int = 1) -> int:
        year = self.today.strftime("%Y")
        yearmonth = self.today.strftime("%Y-%m")
        yearmonthday = self.today.strftime("%Y-%m-%d")
        yearweek = self.today.strftime("%Y-w%W")
        self.add_scope(scorename=scorename,delta=delta,scope="all")
        self.add_scope(scorename=scorename,delta=delta,scope=year)
        self.add_scope(scorename=scorename,delta=delta,scope=yearmonth)
        self.add_scope(scorename=scorename,delta=delta,scope=yearmonthday)
        self.add_scope(scorename=scorename,delta=delta,scope=yearweek)
        return self.get_scope(scorename,"all")

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


class ActionScoreBoard(TriggeredAction, action_name="score_board"):
    """Shows a top scoreboard
    param 0: score to show
    param 1: number of winners
    param 2: variable to store the board in
    """

    async def run_action(self, message: TGMessage) -> str:
        if self.target_reply:
            if not message.reply_to_message:
                return "scoreboard_no_target"
            message = message.reply_to_message
        ss = ScoreHelper(message.from_user.id,message.chat.id)
        board = ss.get_top(self.data[0], int(self.data[1]))
        self.varstore[self.data[2]] = board
        return ""


class ActionScoreUp(TriggeredAction, action_name="score_up"):
    """Ups a score
    param 0: uid
    param 1: score name
    param 2: amount, can be *pointer
    param 3: variable to store into
    """
    async def run_action(self, message: TGMessage) -> str:
        uid = self.read_param(0)
        scorename = self.read_param(1)
        scoreamount = self.read_param(2)
        outvar = self.read_param(3)
        ss = ScoreHelper(uid, message.chat.id)
        amount = int(scoreamount)
        score = ss.add(scorename, amount)
        self.varstore[outvar] = score
        return ""


class ActionScoreGet(TriggeredAction, action_name="score_get"):
    """Gets a score
    param 0: uid
    param 1: score name
    param 2: variable to store into
    """
    async def run_action(self, message: TGMessage) -> str:
        uid = self.read_param(0)
        scorename = self.read_param(1)
        outvar = self.read_param(2)
        ss = ScoreHelper(uid, message.chat.id)
        score = ss.get(scorename)
        self.varstore[outvar] = score
        return ""
