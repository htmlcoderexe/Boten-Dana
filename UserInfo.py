import time

import telegram

import botutils
import scores
from botstate import BotState


class ChatUserInfo:
    """

    """
    def __init__(self, uid: int, chatid: int):
        """

        @param uid:
        @param chatid:
        """
        # basic init
        self.userid = uid
        """Userid concerned."""
        self.chatid = chatid
        """chatid associated with this UserInfo"""
        # end basic init

        ######################################################################

        # get "last seen" stat
        res = BotState.DBLink.execute("""
            SELECT last 
            FROM userseen 
            WHERE userid=? 
            AND chatid=?
            """, (self.userid, self.chatid))
        row = res.fetchone()
        self.last_seen = 0 if not row else row[0]
        """Timestamp of the last time this user was seen here"""
        # end get "last seen" stat

        ######################################################################

        # get reputation
        self.reputation = self.mod_rep(0)
        """User reputation in this chat"""
        # end get reputation

        ######################################################################
        joininfo = ChatUserInfo.get_join(self.chatid,self.userid)
        joindate = 0
        fake = True
        if joininfo is not None:
            joindate, fake = joininfo
        # set the resulting values
        self.joindate = float(joindate)
        """First time the user was seen in the chat."""
        self.joindate_is_fake = bool(fake)
        """Indicates whether the know join date is real (from an actual chat join) or fake (first time the user is seen by the bot)."""
        # end get joindate

        ######################################################################

        # get how many times user joined this particular chat
        res = BotState.DBLink.execute("""
            SELECT time
            FROM user_events
            WHERE userid=?
            AND chatid=?
            AND event_type="joined"
            ORDER BY time DESC
            """, (self.userid, self.chatid))
        rows = res.fetchall()
        if not rows:
            joins = [self.joindate]
        else:
            joins = [float(i[0]) for i in rows]
        self.joins = joins
        """Contains all dates of the user joining this chat."""
        # end get how many times user joined this particular chat

        ######################################################################

        #

    def mod_rep(self, delta: int) -> int:
        """
        Change ths User's reputation in a given chat.
        @param delta: Amount to change the reputation by.
        @return: The new amount of reputation this User has in this chat.
        """
        res = BotState.DBLink.execute("SELECT rep FROM repuser where userid=? AND chatid=?", (self.userid, self.chatid))
        row = res.fetchone()
        # if user has not rep yet, create an entry and change it from 0
        if row is None:
            BotState.DBLink.execute("""INSERT INTO repuser VALUES
            (?, ?, ?, 0)
            """, (self.chatid, self.userid, delta))
            BotState.write()
            self.reputation = delta
        # change user's rep
        else:
            rep = row[0] + delta
            BotState.DBLink.execute("""
            UPDATE repuser
            SET rep = ?
            WHERE userid = ?
            AND chatid= ?
            """, (rep, self.chatid, self.userid))
            BotState.write()
            self.reputation = rep
        return self.reputation

    def msg_counter(self):
        sh = scores.ScoreHelper(self.userid,self.chatid)
        sh.add("msgcount")
        res = BotState.DBLink.execute("SELECT msg FROM repuser where userid=? AND chatid=?", (self.userid, self.chatid))
        row = res.fetchone()
        # if user has not rep yet, create an entry and change it from 0
        if row is None:
            BotState.DBLink.execute("""INSERT INTO repuser VALUES
                (?, ?, 0, 1)
                """, (self.chatid, self.userid))
            BotState.write()
            return 1
        # change user's rep
        else:
            if row[0] is None:
                rep = 1
            else:
                rep = row[0] + 1
            BotState.DBLink.execute("""
                UPDATE repuser
                SET msg = ?
                WHERE userid = ?
                AND chatid= ?
                """, (rep, self.userid, self.chatid))
            BotState.write()
            return rep

    @staticmethod
    def set_join(chatid:int, userid:int, fake: bool = False):
        """Logs a joindate for the specific user/chat pair."""
        last = time.time()
        BotState.DBLink.execute("""
            INSERT INTO join_dates 
            VALUES (?,?,?,?)
            """, (chatid, userid, last, "true" if fake else "false"))
        BotState.write()

    @staticmethod
    def get_join(chatid:int, userid:int):
        res = BotState.DBLink.execute("""
            SELECT time,fake
            FROM join_dates
            WHERE userid=? 
            AND chatid=?
            """, (userid, chatid))
        row = res.fetchone()
        # if found use that
        if row:
            return row
        # if not found log a join now
        else:
            print(f"WHAT THE FUCK!!! {chatid}/{userid}")
            return None


class User:

    def __init__(self, user_id: int, chat_id: int):
        self.id = user_id
        """Telegram userID of this user"""
        self.known_chats = []
        """List of chats this user has been seen in"""
        self.chatinfos = {}
        """Contains user's information indexed by chatID"""
        self.chatinfos[chat_id] = ChatUserInfo(uid=user_id, chatid=chat_id)
        self.current_chat = self.chatinfos[chat_id]
        """Contains 'current' chat info"""
        # get nicknames
        res = BotState.DBLink.execute("""
            SELECT event_data, time, MAX(time) maxtime
            FROM user_events
            WHERE userid = ?
            AND event_type = "renamed"
            GROUP BY event_data
            ORDER BY time DESC
        """, (self.id,))
        rows = res.fetchall()
        self.nicknames = [] if not rows else [botutils.MD(row[0],2) for row in rows]
        """List of known nicknames for this user"""
        self.current_nick = botutils.MD("MissingNo.&%!▮",2) if not self.nicknames else self.nicknames[0]
        """Most recent known nickname"""
        if self.nicknames:
            self.nicknames.pop()
        # print("'"+self.current_nick+"'")
        # print(repr(self.nicknames))

    def chatid_or_default(self, chat_id: int = -1) -> int:
        """Obtains the correct chatID for indexing into chat-specific functions
        to be used by functions which allow omitting the chatID for brevity."""
        # check if specific chat_id is set
        if chat_id in self.chatinfos:
            return chat_id
        # else try default
        if chat_id == -1 and self.chatinfos:
            return list(self.chatinfos.keys())[0]
        # else load the new chat info and return
        self.chatinfos[chat_id] = ChatUserInfo(uid=self.id, chatid=chat_id)
        return chat_id

    def mod_rep(self, amount: int, chat_id: int = -1) -> int:
        """
        Change this User's reputation
        @param amount: Amount to change by
        @param chat_id: ChatID, defaults to the ID this User was initialised with.
        @return: resulting amount of reputation, negative on fail
        """
        return self.chatinfos[self.chatid_or_default(chat_id=chat_id)].mod_rep(amount)

    def msg_uptick(self, chat_id: int = -1) -> int:
        """
        Up the user's message counter
        @param chat_id: ChatID, defaults to the ID this User was initialised with.
        @return: resulting amount of messages, negative on fail
        """
        return self.chatinfos[self.chatid_or_default(chat_id=chat_id)].msg_counter()

    def score_add(self, scorename:str, amount:int = 1, chat_id:int = -1):
        """
        Adds to the user's score
        @param scorename:
        @param amount:
        @param chat_id:
        @return:
        """
        sh = scores.ScoreHelper(self.id, self.chatid_or_default(chat_id))
        sh.add(scorename, amount)

    def log_event(self, event_type: str, data: str, chat_id: int = -1):
        """
        Log an event relevant to the user and specific chat.
        @param event_type: type of the event to log
        @param data: event data
        @param chat_id: chat of concern
        @return:
        """
        BotState.DBLink.execute("""INSERT INTO user_events VALUES
    (?,?,?,?,?)
    """,(self.chatid_or_default(chat_id), self.id,time.time(), event_type, data))
        BotState.write()
        print(f"Event of type <{event_type}> logged for user {self.id}@{self.chatid_or_default(chat_id)} with data <{data}>.")

    def refresh_nick(self, nick: str) -> bool:
        """
        Update user's nickname if necessary
        @param nick: new nickname
        @return: Whether a refresh happened or not.
        """
        print("'"+nick+"'")
        # if user has no known names yet, update
        if not self.nicknames and not self.current_nick:
            self.log_event(event_type="renamed", data=nick)
            self.nicknames = [nick]
            self.current_nick = nick
            return True
        # if doesn't match current most recent name
        if self.current_nick != botutils.MD(nick,2):
            print(f"<{self.current_nick}> is not equal to <{nick}>.")
            self.log_event(event_type="renamed", data=nick)
            self.nicknames = [nick] + self.nicknames
            self.current_nick = nick
            return True
        # no update was needed
        return False

    @classmethod
    def refresh(cls, user_id: int, chat_id: int, true_join: bool = False):
        """
        Refreshes user's presence and known names.
        @param true_join:
        @param user_id: UserID of the user to refresh
        @param chat_id: ChatID of the chat to refresh
        @return: the User with updated stats
        """
        last = time.time()
        joininfo = ChatUserInfo.get_join(chat_id, user_id)
        if joininfo is None:
            print("set new join info!")
            ChatUserInfo.set_join(chat_id, user_id, true_join)
        res = BotState.DBLink.execute("SELECT last FROM userseen where userid=? AND chatid=?", (user_id, chat_id))
        row = res.fetchone()
        if row is None:
            # print(f"user {userid} set to {last} ")
            BotState.DBLink.execute("INSERT INTO userseen VALUES (?,?,?,0,'')", (chat_id, user_id, last))
        else:
            # print(f"user {userid} updated to {last} ")
            BotState.DBLink.execute("UPDATE userseen SET last=? WHERE  chatid=? AND userid=?", (last, chat_id, user_id))
        BotState.write()
        usr = cls(user_id, chat_id)
        if joininfo is None and not true_join:
            usr.log_event("joined","message")
        return usr

    @staticmethod
    def extract_uid(message:telegram.Message) -> int:
        """
        Extracts a unique identifier from a Message - userID for regular message, channel ID for messages sent from channels.
        @param message:
        @return:
        """
        if not message.from_user:
            if not message.sender_chat:
                return 0
            return message.sender_chat.id
        uid = message.from_user.id
        if uid in (telegram.constants.ChatID.ANONYMOUS_ADMIN, telegram.constants.ChatID.SERVICE_CHAT, telegram.constants.ChatID.FAKE_CHANNEL):
            uid = message.sender_chat.id
        print(f"The extracted uid was {uid}.")
        return uid

    @staticmethod
    def extract_nick(message:telegram.Message) -> str:
        """
        Extracts a name to refer to an identified entity by.
        @param message:
        @return:
        """
        if not message.from_user:
            if not message.sender_chat:
                return "0"
            return message.sender_chat.title or message.sender_chat.full_name
        nick = message.from_user.full_name
        uid = message.from_user.id
        if uid in (telegram.constants.ChatID.ANONYMOUS_ADMIN, telegram.constants.ChatID.SERVICE_CHAT, telegram.constants.ChatID.FAKE_CHANNEL):
            nick = message.sender_chat.title or message.sender_chat.full_name
        # print(f"The extracted nick was {nick}.")
        return nick
