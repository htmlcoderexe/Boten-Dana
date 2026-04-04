import random
import time

import botutils
import scheduled_events
from actions import TriggeredAction
from botstate import BotState
from messagestore import TGMessage


class Butt:
    """a"""
    def __init__(self, butt_id, file_id, owner, chat, name,butt_hash):
        self.id = butt_id
        """Unique ID of the butt"""
        self.pic = file_id
        """Picture of this butt"""
        self.owner = owner
        """User ID of the owner"""
        self.chat = chat
        """Chat where this butt is spawning"""
        self.name = name
        """Name of this butt"""
        self.hash = hash
        """File hash of the picture to avoid duplicates"""

    @classmethod
    def load(cls, butt_id):
        q = """SELECT file_id, owner, spawning_chat, name, hash
        FROM butts_game_butts
        WHERE butt_id = ?"""
        res = BotState.DBLink.execute(q,(butt_id,))
        row = res.fetchone()
        if row:
            return cls(butt_id=butt_id,file_id=row[0],owner=row[1],chat=row[2],name=row[3],butt_hash=row[4])
        else:
            return None

    @staticmethod
    def get_chat_status(chat_id):
        q = """SELECT butt_id, owner
        FROM butts_game_butts
        WHERE spawning_chat = ?
        AND owner IN (0, -1) """
        res = BotState.DBLink.execute(q,(chat_id,))
        row = res.fetchone()
        if row:
            return row
        else:
            return "", 0

    def set_name(self, name):
        q = """UPDATE butts_game_butts
                SET name = ?
                WHERE butt_id = ?"""
        BotState.DBLink.execute(q, (name, self.id))
        BotState.write()
        self.name = name


class NameButt(TriggeredAction, action_name="name_butt"):
    async def run_action(self, message: TGMessage) -> str:
        butt_id = self.read_int(0)
        butt = Butt.load(butt_id)
        if not butt:
            return ""
        name = self.read_string(1)
        name = name[:32]
        butt.set_name(name)
        return ""


class GetButtStatusForChat(TriggeredAction, action_name="get_chat_butt"):
    async def run_action(self, message: TGMessage) -> str:
        chatid = self.read_int(0)
        if chatid == -1:
            chatid = message.chat_id
        status = Butt.get_chat_status(chat_id=chatid)
        self.write_param(1,status[0])
        self.write_param(2,status[1])
        return ""


class GetButtStatusForUser(TriggeredAction, action_name="get_user_butt"):
    async def run_action(self, message: TGMessage) -> str:
        userid = self.read_int(0)
        if userid == -1:
            userid = self.varstore['__uid']
        q = """SELECT butt_id
        FROM butts_game_butts
        WHERE owner = ?"""
        res = BotState.DBLink.execute(q,(userid,))
        row = res.fetchone()
        if row:
            self.write_param(1,row[0])
        else:
            self.write_param(1,"")
        return ""


class UserTakeButtOwnership(TriggeredAction, action_name="claim_butt"):
    async def run_action(self, message: TGMessage) -> str:
        butt_id = self.read_int(0)
        userid = self.read_int(1)
        chat_id = self.varstore['__chat_id']
        if userid == -1:
            userid = self.varstore['__uid']
        q = """UPDATE butts_game_butts
        SET owner = ?
        WHERE butt_id = ?"""
        BotState.DBLink.execute(q,(userid,butt_id))
        BotState.write()
        events = scheduled_events.ScheduledEvent.cancel_events("refresh_butt",chat_id,[(0,butt_id)])
        #  ScheduledEvent.schedule_event("msg_kill", chatid, expiration, msgid)
        return ""


class GetButtInfo(TriggeredAction, action_name="butt_load"):
    async def run_action(self, message: TGMessage) -> str:
        butt_id = self.read_int(0)
        self.write_param(1,Butt.load(butt_id))
        return ""


class LoadButts(TriggeredAction, action_name="load_butts"):
    async def run_action(self, message: TGMessage) -> str:
        chatid = message.chat_id
        file_ids = []
        if message.media_group_id:
            album = await BotState.pyroclient.get_media_group(chat_id=chatid, message_id=message.id)
            for msg_part in album:
                if msg_part.photo:
                    file_ids.append((msg_part.photo.file_id,msg_part.photo.file_unique_id))
        else:
            if message.photo:
                file_ids.append((message.photo[-1].file_id,message.photo[-1].file_unique_id))
        if file_ids:
            for file_id in file_ids:
                q = """SELECT butt_id
                FROM butts_game_butts
                WHERE hash = ?"""
                res = BotState.DBLink.execute(q,(file_id[1],))
                exists = res.rowcount > 0
                if exists:
                    continue
                q = """INSERT INTO butts_game_butts
                VALUES (NULL, ?, 0, 0, '',?)"""
                BotState.DBLink.execute(q, file_id)
            BotState.write()
        return ""


class SelectButt(TriggeredAction, action_name="select_butt"):
    async def run_action(self, message: TGMessage) -> str:
        chat_id = self.read_int(0)
        if chat_id == -1:
            chat_id = self.varstore["__chat_id"]
        q = """SELECT butt_id, file_id
        FROM butts_game_butts
        WHERE owner = 0
        AND spawning_chat = 0"""
        res = BotState.DBLink.execute(q)
        rows = res.fetchall()
        if not rows:
            return ""
        row = random.choice(rows)
        file_id = row[1]
        butt_id = row[0]
        delay = 600+random.randint(0,600)
        do_delay = self.read_int(1) == 1
        moment = time.time()
        if do_delay:
            moment += delay
        scheduled_events.ScheduledEvent.schedule_event("announce_butt", chat_id, moment, file_id, butt_id)
        q = """UPDATE butts_game_butts
        SET owner = -1, spawning_chat = ?
        WHERE butt_id = ?
        """
        BotState.DBLink.execute(q,(chat_id,butt_id))
        BotState.write()
        moment = time.time()+3600
        scheduled_events.ScheduledEvent.schedule_event("refresh_butt", chat_id, moment, butt_id)


class DropButt(TriggeredAction, action_name="drop_butt"):
    async def run_action(self, message: TGMessage) -> str:
        chat_id = self.read_int(0)
        if chat_id == -1:
            chat_id = self.varstore['__chat_id']
        status = Butt.get_chat_status(chat_id)
        if status[0] == "":
            return ""
        if status[1] != -1:
            return ""
        butt = Butt.load(status[0])
        q = """UPDATE butts_game_butts
        SET owner = 0
        WHERE spawning_chat = ?
        AND butt_id = ?"""
        BotState.DBLink.execute(q,(chat_id,butt.id))
        BotState.write()
        self.write_param(1,butt.id)
        self.write_param(2,butt.pic)
        return ""
        # msg_sent = (await BotState.bot.send_photo(chat_id=chatid,photo=file_id))


class ResetButt(TriggeredAction, action_name="reset_butt"):
    async def run_action(self, message: TGMessage) -> str:
        butt_id = self.read_int(0)
        q = """UPDATE butts_game_butts
                SET owner = 0, spawning_chat = 0
                WHERE butt_id = ?
                """
        BotState.DBLink.execute(q, (butt_id,))
        BotState.write()


class RetractButt(TriggeredAction, action_name="retract_butt"):
    async def run_action(self, message: TGMessage) -> str:
        chat_id = self.read_int(0)
        if chat_id == -1:
            chat_id = self.varstore["__chat_id"]
        q = """UPDATE butts_game_butts
                SET owner = 0, spawning_chat = 0
                WHERE spawning_chat = ?
                AND owner = 0
                """
        BotState.DBLink.execute(q, (chat_id,))
        BotState.write()
        return ""
