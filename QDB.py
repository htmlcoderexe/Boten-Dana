import time

from botstate import BotState
from actions import TriggeredAction
from telegram import Message as TGMessage
import random
import UserInfo


class Quote:
    db_query = """
        SELECT  qid, quote, author, messageid, save_date,
                reply_text, reply_user, reply_id,
                chatid, userid,
                rating
        FROM    qdb"""

    def __init__(self,qid: int,text: str, userid: int, msgid: int, save_date: float,
                 reply_text:str = "", reply_user: int = 0, reply_id: int = 0,
                 chatid: int = 0, saver: int = 0,
                 rating: int = 0):
        self.id:int = qid
        """Unique ID of this quote."""
        self.text_raw:str = text
        """Text of the quote."""
        self.user_id:int = userid
        """UserID of the quote's author."""
        self.message_id:int = msgid
        """ID of the original message."""
        self.save_date:float = save_date
        """Datetime of the saving."""
        self.reply_to_text:str = reply_text
        """Text of a message this message is responding to, may be empty even if there is a parent message."""
        self.reply_to_msg:int = reply_id
        """ID of the message the quote is replying to. If 0, then the quote is standalone."""
        self.reply_to_user:int = reply_user
        """UserID of the replied message's author."""
        self.chatid:int = chatid
        """Chat ID where the quote was saved."""
        self.saved_by:int = saver
        """UserID of the user who saved the quote."""
        self.rating:int = rating
        """Amount of upvotes given to the quote."""

    def upvote(self, amount:int = 1):
        """

        @return:
        """


class Database:
    chatid = 0
    writing_user = 0

    def __init__(self,chatid: int, writing_user: int):
        self.chatid = chatid
        self.writing_user = writing_user

    @staticmethod
    def get_by_id(qid: int) -> Quote | None:
        """

        @param qid:
        @return:
        """
        query = Quote.db_query + """
        WHERE   qid = ?
        """
        res = BotState.DBLink.execute(query, (qid,))
        row = res.fetchone()
        if row:
            return Quote(*row)
        return None

    def exists(self,msgid: int) -> Quote | None:
        """
        Checks if a given message has already been saved to QDB in this chat.
        @param msgid: ID of the message to be checked
        @return: The Quote object if it exists
        """
        query = Quote.db_query + """
        WHERE   chatid = ?
        AND     messageid = ?
        """
        res = BotState.DBLink.execute(query, (self.chatid, msgid))
        row = res.fetchone()
        if row:
            return Quote(*row)
        return None

    def get_quotes(self,userid: int, local_only: bool = False) -> list[Quote]:
        """
        Get all quotes from a specific user
        @param userid: user ID to fetch the quotes from
        @param local_only: only consult this chat if True
        @return:
        """
        query = Quote.db_query + """
        WHERE   author = ?
        """
        if local_only:
            query += """
            AND     chatid = ?
            """
            res = BotState.DBLink.execute(query, (userid, self.chatid))
        else:
            res = BotState.DBLink.execute(query, (userid,))
        rows = res.fetchall()
        if rows:
            return [Quote(*row) for row in rows]
        return []

    def get_chat_quotes(self, min_score:int = 1, chat_id:int = 0) -> list[Quote]:
        """
        Gets quotes from a chat
        @param min_score: Minimum score for quotes to show, defaults to 1
        @param chat_id: Use a different chat
        @return: A list of Quotes if any are found matching the criteria
        """
        query = Quote.db_query + """
        WHERE chatid = ?
        AND rating >= ?
        """
        chatid = chat_id if chat_id else self.chatid
        res = BotState.DBLink.execute(query,(chatid,min_score))
        rows = res.fetchall()
        if rows:
            return [Quote(*row) for row in rows]
        return []

    def save_quote(self, text: str, msg_id: int, user_id: int, reply_id: int = 0, reply_user: int = 0, reply_text:str = "") -> Quote:
        """
        Saves a quote to the database.
        @param text: Quote text
        @param msg_id: Message ID of the quoted message
        @param user_id: User ID of the user quoted
        @param reply_id: ID of the message replied to, if available
        @param reply_user: User the quoted message replied to, if available
        @param reply_text: Text of the message this quote replies to, if any
        @return: The resulting Quote object
        """
        q = self.exists(msgid=msg_id)
        if q:
            return q
        now = time.time()
        query = """
        INSERT INTO     qdb
        VALUES          (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        RETURNING RowId
        """
        res = BotState.DBLink.execute(query,(text,user_id,msg_id,now,
                                      reply_id, reply_text, reply_user,
                                      self.chatid, self.writing_user,
                                      0))
        row = res.fetchone()
        BotState.write()
        return Database.get_by_id(row[0])


class ActionQDBSave(TriggeredAction):
    """
    Saves to QDB
    param 0: variable to store the resulting ID in
    param 1: variable to store the outcome
    """
    async def run_action(self, message: TGMessage) -> str:
        idvar = self.get_param(0)
        resultvar = self.get_param(1)
        uid = UserInfo.User.extract_uid(message)
        if self.target_reply:
            if not message.reply_to_message:
                self.varstore[idvar] = 0
                self.varstore[resultvar] = "no_text"
                return "qdb_save_no_target"
            message = message.reply_to_message

        if not message.text and not message.caption:
            self.varstore[idvar] = 0
            self.varstore[resultvar] = "no_text"
            return ""
        text = message.text_markdown_v2 if message.text else message.caption_markdown_v2
        author = UserInfo.User.extract_uid(message)
        msgid = message.id
        chatid = message.chat.id
        replyid = 0
        replytext = ""
        replyuser = 0
        # check if the quote already exists
        qdb = Database(message.chat.id, uid)
        q = qdb.exists(msgid)
        if q:
            self.varstore[resultvar] = "exists"
        else:
            # use pyro to get the context of the message being captured if possible
            pc = BotState.pyroclient
            fullmsg = await pc.get_messages(chatid,msgid)
            if fullmsg and fullmsg.reply_to_message:
                replyid = fullmsg.reply_to_message.id
                replyuser = UserInfo.User.extract_uid(fullmsg.reply_to_message)
                replytext = fullmsg.reply_to_message.text if fullmsg.reply_to_message.text else replytext
                replytext = fullmsg.reply_to_message.caption if fullmsg.reply_to_message.caption else replytext
            # save the quote
            q = qdb.save_quote(text=text, msg_id=msgid, user_id=author, reply_text=replytext, reply_user=replyuser, reply_id=replyid)
            self.varstore[resultvar] = "ok"
        self.varstore[idvar] = q.id
        return ""


class ActionQDBUpvote(TriggeredAction):
    """Modifies a given quote's score.
    param 0: quote ID
    param 1: delta
    param 2: variable to store the new score of the quote"""
    async def run_action(self, message: TGMessage) -> str:
        qid = int(self.get_param(0))
        delta = int(self.get_param(1))
        outvar = self.get_param(2)
        q = Database.get_by_id(qid)
        if not q:
            self.varstore[outvar] = -1
            return ""
        q.upvote(delta)
        self.varstore[outvar] = q.rating
        return ""


class ActionQDBGetUserQuotes(TriggeredAction):
    """
    Gets quotes for user
    param 0: userID
    param 1: variable to store the quotes in
    param 2: amount of quotes to get, -1 to get all
    param 3: "local" or "global" to get quotes from everywhere or just this chat.
    param 4: score threshold
    param 5: sorting mode: "score", "newest", "oldest", random
    """
    async def run_action(self, message: TGMessage) -> str:
        uid = int(self.get_param(0))
        outvar = self.get_param(1)
        amount = int(self.get_param(2))
        scope = self.get_param(3)
        # ensure scope is fixed
        if scope not in ("global", "local"):
            scope = "global"
        min_score = int(self.get_param(4))
        sortby = self.get_param(5)
        # constrain the options
        if sortby not in ("score","newest","oldest","random"):
            sortby = "oldest"
        qdb = Database(message.chat.id,uid)
        # fetch all quotes
        quotes = qdb.get_quotes(uid, scope == "local")
        # quotes are fetched with oldest first at the top so this is the default sort
        match sortby:
            case "newest":
                # reverse the list to get newest first
                quotes.reverse()
            case "random":
                # shuffle the list for random order
                random.shuffle(quotes)
            case "score":
                # sort by rating then reverse (higher scores first)
                quotes = sorted(quotes, key=lambda q: q.rating)
                quotes.reverse()
        # filter by score
        filtered_quotes = [q for q in quotes if q.rating >= min_score]
        # if -1 is specified, return everything so far, else only the first <amount>
        if amount == -1:
            quotes = filtered_quotes
        else:
            quotes = filtered_quotes[:amount]
        self.varstore[outvar] = quotes
        return ""


TriggeredAction.register("qdb_save",ActionQDBSave)
TriggeredAction.register("qdb_upvote",ActionQDBUpvote)
TriggeredAction.register("qdb_get_user", ActionQDBGetUserQuotes)