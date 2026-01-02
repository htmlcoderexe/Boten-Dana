import time
from datetime import datetime

import UserInfo
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

    @staticmethod
    def make_scopes(date: datetime = None):
        if date is None:
            date = datetime.now()
        year = date.strftime("%Y")
        month = date.strftime("%Y-%m")
        week = date.strftime("%Y-w%W")
        day = date.strftime("%Y-%m-%d")
        return "all", year, month, week, day

    @staticmethod
    def make_scope(scope: str, date: datetime = None):
        scope_names = ("all", "year", "month", "week", "day")
        if scope not in scope_names:
            scope = "all"
        index = scope_names.index(scope)
        scopes = ScoreHelper.make_scopes(date)
        return scopes[index]

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
            amount = int(row[0])
            data3 = (amount + delta, self.chatid, self.userid, scorename, scope)
            BotState.DBLink.execute("""UPDATE scores
                SET amount = ?
                WHERE chatid = ?
                AND userid = ?
                AND scorename = ?
                AND scope = ?
                """, data3)
            BotState.write()

    def add(self, scorename: str, delta: int = 1) -> int:
        for scope in ScoreHelper.make_scopes(self.today):
            self.add_scope(scorename, scope, delta)
        return self.get_scope(scorename, "all")

    def get_scope(self, scorename: str, scope: str):
        if self.chatid == 0:
            res = BotState.DBLink.execute("""
            SELECT amount 
            FROM scores 
            WHERE userid = ? 
            AND scorename = ? 
            AND scope = ? """, (self.userid, scorename, scope))
            rows = res.fetchall()
            if not rows:
                return 0
            result = 0
            for row in rows:
                result += int(row[0])
            return result
        else:
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

    def get(self, scorename: str, date: datetime = None):
        if date is None:
            date = self.today
        return tuple([self.get_scope(scorename, scope) for scope in ScoreHelper.make_scopes(date)])

    def get_top(self, scorename: str, count: int = 1, scope: str = "all"):
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

    def get_scoreboard(self, count: int = 1, scope: str = "all", scores=None, date: datetime = None):
        """

        @param count:
        @param scope:
        @param scores:
        @param date:
        @return:
        """
        scope = ScoreHelper.make_scope(scope,date)
        if not scores:
            return []
        extras1 = ", extrascore{0}.amount as score{0}"
        extras2 = """
            LEFT JOIN 
            (SELECT amount, userid FROM scores
            WHERE scorename = :score{0}
            AND chatid = :chatid
            AND scope = :noscope
            ) extrascore{0}
        ON scores.userid = extrascore{0}.userid"""
        extras3 = ", score{0} DESC"
        query = """SELECT scores.userid, scores.amount as score0{extras1}
        FROM "scores" 
        {extras2}
        WHERE scope = :noscope 
        AND scorename = :score0 
        AND chatid = :chatid
        ORDER BY score0 DESC{extras3}
        LIMIT :cunt"""
        mainscore = scores[0]
        params = {"chatid": self.chatid, "noscope": scope, "score0": mainscore, "cunt": count}
        e1 = e2 = e3 = ""
        for i, score in enumerate(scores):
            if i == 0:
                continue
            e1 = e1 + extras1.format(i)
            e2 = e2 + extras2.format(i)
            e3 = e3 + extras3.format(i)
            params["score" + str(i)] = score
        q = query.format(extras1=e1, extras2=e2, extras3=e3)
        res = BotState.DBLink.execute(q, params)
        rows = res.fetchall()
        return rows


class ActionScoreBoard(TriggeredAction, action_name="sxxxxcore_board"):
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
        ss = ScoreHelper(message.from_user.id, message.chat.id)
        board = ss.get_top(self.data[0], int(self.data[1]))
        self.write_param(2,board)
        return ""


class ActionScoreUp(TriggeredAction, action_name="score_up"):
    """Ups a score
    param 0: uid
    param 1: score name
    param 2: amount, can be *pointer
    param 3: variable to store into
    param 4: optional timestamp
    """

    async def run_action(self, message: TGMessage) -> str:
        uid = self.read_param(0)
        scorename = self.read_param(1)
        amount = self.read_int(2)
        timestamp = self.read_int(4)
        if timestamp == -1:
            timestamp = time.time()
        ss = ScoreHelper(uid, self.varstore["__chat_id"], datetime.fromtimestamp(timestamp))
        score = ss.add(scorename, amount)
        self.write_param(3,score)
        return ""


class ActionScoreSet(TriggeredAction, action_name="score_set"):
    """Sets a score
    param 0: uid
    param 1: score name
    param 2: amount, can be *pointer
    param 3: variable to store into
    param 4: optional timestamp
    """

    async def run_action(self, message: TGMessage) -> str:
        uid = self.read_param(0)
        scorename = self.read_param(1)
        amount = self.read_int(2)
        timestamp = self.read_int(4)
        if timestamp == -1:
            timestamp = time.time()
        ss = ScoreHelper(uid, self.varstore["__chat_id"], datetime.fromtimestamp(timestamp))
        score = ss.add(scorename, 0)
        amount = amount - score
        score = ss.add(scorename, amount)
        self.write_param(3, score)
        return ""


class ActionScoreGet(TriggeredAction, action_name="score_get"):
    """Gets a score
    param 0: uid, -1 = current
    param 1: score name
    param 2: variable to store into
    param 3: optional scope from "all" (default), "day", "week", "month", "year"
    param 4: optional timestamp
    """

    async def run_action(self, message: TGMessage) -> str:
        uid = self.read_param(0)
        if uid == -1:
            uid = self.varstore["__uid"]
        scorename = self.read_param(1)
        scope = self.read_string(3)
        timestamp = self.read_int(4)
        if timestamp == -1:
            timestamp = time.time()
        date = datetime.fromtimestamp(timestamp)
        scopes = ("all", "year", "month", "week", "day")
        if scope not in scopes:
            scope = "all"
        ss = ScoreHelper(uid, self.varstore["__chat_id"], date)
        score = ss.get(scorename)
        index = scopes.index(scope)
        self.write_param(2, score[index])
        return ""

    class GetScoreBoard(TriggeredAction, action_name="scoreboard"):
        """
        Gets a scoreboard
        param 0: out resulting board
        param 1: chatid, -1 = from __chat_id
        param 2: scope, from "all" (default), "day", "week", "month", "year"
        param 3: timestamp, -1 = today
        param 4: count
        param X: score names
        """

        async def run_action(self, message: TGMessage) -> str:
            chatid = self.read_int(1)
            if chatid == -1:
                chatid = self.varstore["__chat_id"]
            scope = self.read_string(2)
            timestamp = self.read_int(3)
            count = self.read_int(4)
            if count < 0:
                count = 10
            scores = self.read_to_end(5)
            if timestamp == -1:
                timestamp = time.time()
            date = datetime.fromtimestamp(timestamp)
            sh = ScoreHelper(0,chatid,date)
            data = sh.get_scoreboard(count, scope, scores,date)
            board = []
            for line in data:
                uid = line[0]
                rest = [val if val is not None else 0 for val in line[1:]]
                usr = UserInfo.User(uid, chatid)
                line2 = [usr.current_nick] + list(rest)
                board.append(line2)
            self.write_param(0,board)
            return ""
