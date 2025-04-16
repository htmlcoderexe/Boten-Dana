from botstate import BotState


class Quote:
    qid = 0
    chatid = 0
    text_raw = ""
    message_id = 0
    user_id = 0
    reply_to_msg = 0
    reply_to_user = 0
    reply_to_text = ""
    saved_by = 0
    rating = 0

    db_query = """
        SELECT  qid,quote,author,messageid,
                reply_text,reply_user,reply_id,
                chatid,userid,
                rating
        FROM    qdb"""

    def __init__(self,qid: int,text: str, userid: int, msgid: int,
                 reply_text:str = "", reply_user: int = 0, reply_id: int = 0,
                 chatid: int = 0, saver: int = 0,
                 rating: int = 0):
        self.id = qid
        self.text_raw = text
        self.user_id = userid
        self.message_id = msgid
        self.reply_to_text = reply_text
        self.reply_to_msg = reply_id
        self.reply_to_user = reply_user
        self.chatid = chatid
        self.saved_by = saver
        self.rating = rating

    def upvote(self):
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
            q.upvote()
            return q
        query = """
        INSERT INTO     qdb
        VALUES          (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        RETURNING RowId
        """
        res = BotState.DBLink.execute(query,(self.chatid, self.writing_user,
                                      user_id,msg_id,text,
                                      reply_id, reply_text, reply_user,
                                      0))
        row = res.fetchone()
        BotState.write()
        return Database.get_by_id(row[0])
