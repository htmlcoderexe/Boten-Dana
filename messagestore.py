import time
import random
from telegram import Message,InputMediaPhoto

import botutils
import messagetagger
from botstate import BotState
from actions import TriggeredAction

TGMessage = Message


class StoredMessagePart:
    """
    Represents a single component of a stored message.
    """
    part_type = ""
    data = ""

    def __init__(self, part_type: str, data: str):
        self.part_type = part_type
        self.data = data

    def __str__(self):
        return f"MessagePart: type <{self.part_type}>, data <{self.data}>"

    def __repr__(self):
        return f"MessagePart: type <{self.part_type}>, data <{self.data}>"


class MessageStore:
    """
    Used to interact with the message storage system.
    """
    owner_chat = 0
    current_user = 0
    glob_mode = False

    def __init__(self,chatid: int, user: int, glob: bool = False):
        """
        Creates an instance to interact with the storage system.
        @param chatid: Associates a chatID to perform store operations.
        @param user: User who is interacting with the storage.
        @param glob: If set to true, the global message store will be used (chatid 0), by default the chatid associated
        with this MessageStore is used for operations.
        """
        self.owner_chat = chatid
        self.current_user = user
        self.glob_mode = glob

    def write_part(self, name: str, part_type: str, data: str = ""):
        """
        Writes a message component to the message store.
        @param name: Name of the stored message to associate with the component
        @param part_type: Type of the component
        @param data: Message component data, varies by type
        @return:
        """
        chatid = 0 if self.glob_mode else self.owner_chat
        BotState.DBLink.execute("""
            INSERT INTO saved_messages
            VALUES (?,?,?,?,?,?)
            """, (chatid, name, part_type, data, self.current_user, time.time()))
        BotState.write()

    def read_parts(self, name:str, chatid:int = -1):
        """
        Retrieves all components of a specific stored message.
        @param name: Name of the stored message.
        @param chatid: optional chatid
        @return: A List (empty if nothing is found) of StoredMessagePart
        """
        if chatid == -1:
            chatid = 0 if self.glob_mode else self.owner_chat
        print(name)
        print(chatid)
        print("getting parts---------------")
        res = BotState.DBLink.execute("""
            SELECT type,data FROM saved_messages
            WHERE name = ?
            AND chatid = ?
            """, (name, chatid))
        partdata = res.fetchall()
        parts = []
        for part in partdata:
            parts.append(StoredMessagePart(part_type=part[0], data=part[1]))
        return parts

    def move_message(self, name:str, new_id:int):
        """

        @param name:
        @param new_id:
        @return:
        """
        chatid = 0 if self.glob_mode else self.owner_chat
        print(name)
        print(chatid)
        rows = self.read_parts(name=name, chatid=new_id)
        if rows:
            # TODO: i8n
            return False
        print("moving part---------------")
        res = BotState.DBLink.execute("""
                   UPDATE saved_messages
                   SET chatid = ?
                   WHERE name = ?
                   AND chatid = ?
                   """, (new_id, name, chatid))
        return True

    def get_type_emoji(self, name: str):
        parts = self.read_parts(name)
        print(parts)
        # nothing
        if not parts:
            return " "
        # remove all text
        for part in parts[:]:
            if part.part_type in ["text","caption"]:
                parts.remove(part)
        # nothing left, there was only text
        if not parts:
            return "📄"
        # probably an album
        if len(parts) > 1:
            return "🗃"
        match parts[0].part_type:
            # append to a list to send as a mediagroup later
            case "image":
                return "🖼"
            case "voice":
                return "🎤"
            case "eblovoice":
                return "🤳"
            case "video":
                return "📼"
            case "music":
                return "🎧"
            case "sticker":
                return "🩹"
            case "file":
                return "💾"

    async def store_message(self, msg: Message, name: str):
        """
        Stores a Telegram.Message.
        @param msg: The Telegram.Message to be stored.
        @param name: The name to
        @return: Tuple used by timed bot responses - str response, int user message remove delay, int bot message remove delay
        """
        success_msg = "Сообщение \"" + botutils.MD(name) + "\" сохранено\\!", 5, 10
        chatid = 0 if self.glob_mode else self.owner_chat
        rows = self.read_parts(name=name)
        if rows:
            # TODO: i8n
            return False
        if msg.text:
            self.write_part(name=name, part_type="text", data=msg.text)
            return True
        if msg.media_group_id:
            album = await BotState.pyroclient.get_media_group(chat_id=chatid, message_id=msg.id)
            for msg_part in album:
                if msg_part.caption:
                    self.write_part(name=name,part_type="caption",data=msg.caption)
                else:
                    self.write_part(name=name,part_type="caption",data="")
                if msg_part.photo:
                    self.write_part(name=name,part_type="image",data=msg_part.photo.file_id)
            return True
        if msg.photo:
            self.write_part(name=name, part_type="image", data=msg.photo[-1].file_id)
        if msg.caption:
            self.write_part(name=name,part_type="caption",data=msg.caption)
        if msg.voice:
            self.write_part(name=name,part_type="voice",data=msg.voice.file_id)
        if msg.video_note:
            self.write_part(name=name,part_type="eblovoice",data=msg.video_note.file_id)
        if msg.audio:
            self.write_part(name=name,part_type="music",data=msg.audio.file_id)
        if msg.sticker:
            self.write_part(name=name,part_type="sticker",data=msg.sticker.file_id)
        if msg.video:
            self.write_part(name=name, part_type="video", data=msg.video.file_id)
        if msg.document:
            self.write_part(name=name, part_type="file", data=msg.document.file_id)
        return True

    def get_text(self, name: str):
        """
        Gains the textual component of the message so stored.
        @param name: Name of the message.
        @return: The text, hopefully.
        """
        parts = self.read_parts(name=name)
        if not parts:
            if self.glob_mode:
                return ""
            else:
                self.glob_mode = True
                return self.get_text(name=name)
        for part in parts:
            match part.part_type:
                case "text":
                    return part.data
                case "caption":
                    return part.data
        return ""

    async def replay_message(self, name: str, reply_to: int = 0, target_chat: int =0) -> list[int]:
        """
        Fetches a stored message and sends it to a chat
        @param name: The name identifying the stored message
        @param reply_to: The message to reply to (0 if no replying)
        @param target_chat: The chat to send the message to, if different from the message's origin chat
        @return: ID(s) of sent message(s)
        """
        dest_chat = self.owner_chat if target_chat == 0 else target_chat
        reply_to_msg = None if reply_to == 0 else reply_to
        msgsent = None
        print(f"Retrieving message with NAME<{name}>")
        parts = self.read_parts(name=name)
        if not parts:
            if self.glob_mode:
                msgsent = await BotState.bot.send_message(chat_id=dest_chat,text="404")
                return [msgsent.id]
            else:
                self.glob_mode = True
                return await self.replay_message(name=name,reply_to=reply_to,target_chat=target_chat)
        photos = []
        captions = []
        # holds a single caption to use if the caption belongs to a single media file
        caption = ""
        for part in parts:
            match part.part_type:
                # append to a list to send as a mediagroup later
                case "image":
                    photos.append(part.data)
                # captions can attach to separate media messages, append to list
                # when a media group message is saved, a caption part is created for every image
                case "caption":
                    # set the single caption - write order guarantees this gets set before any other file type
                    caption = part.data
                    captions.append(part.data)
                # plain text message, send as is
                case "text":
                    msgsent = await BotState.bot.send_message(chat_id=dest_chat,text=part.data,reply_to_message_id=reply_to_msg)
                # if any of those, fire off the message with the previously set caption (blank if not set)
                case "voice":
                    msgsent = (await BotState.bot.send_voice(chat_id=dest_chat, voice=part.data, caption=caption,reply_to_message_id=reply_to_msg))
                case "eblovoice":
                    msgsent = (await BotState.bot.send_video_note(chat_id=dest_chat, video_note=part.data, caption=caption,reply_to_message_id=reply_to_msg))
                case "video":
                    msgsent = (await BotState.bot.send_video(chat_id=dest_chat, video=part.data, caption=caption, reply_to_message_id=reply_to_msg))
                case "music":
                    msgsent = (await BotState.bot.send_audio(chat_id=dest_chat, audio=part.data, caption=caption, reply_to_message_id=reply_to_msg))
                case "sticker":
                    msgsent = (await BotState.bot.send_sticker(chat_id=dest_chat, sticker=part.data,reply_to_message_id=reply_to_msg))
                case "file":
                    msgsent = (await BotState.bot.send_document(chat_id=dest_chat, document=part.data, caption=caption, reply_to_message_id=reply_to_msg))
            # if any messages got sent, return the ID of the sent message
            if msgsent:
                return [msgsent.id]
            # if we're still here, try to send a media group
        if len(photos) > 0:
            media_group = []
            for idx, photo in enumerate(photos):
                caption = "" if idx >= len(captions) else captions[idx]
                media_group.append(InputMediaPhoto(caption=caption, media=photo))
            messages = await BotState.bot.send_media_group(chat_id=dest_chat,media=media_group,reply_to_message_id=reply_to_msg)
            return [message.id for message in messages]
        return []


class MessagePool:
    """
    Used to interact with message pools
    """

    def __init__(self, pool_id: str, chat_id: int = 0):
        self.id = pool_id
        """ID (string) of this pool"""
        self.chat = chat_id
        """ChatID to associate with the pool"""
        self.is_global = chat_id == 0
        """Whether a chat-specific or a global pool (chatID 0) is in use"""
        pool = MessagePool.get_messages(pool_id=pool_id, chat_id=chat_id)
        if not pool and not self.is_global:
            pool = MessagePool.get_messages(pool_id=pool_id, chat_id=0)
            self.is_global = True
        self.messages = ()
        """Saved Message IDs"""
        self.weights = ()
        """Weights of corresponding Saved Messages in this pool"""
        if pool:
            self.messages,self.weights = list(zip(*pool))

    def fetch(self):
        """Picks out a random messageID from the pool"""
        return random.choices(population=self.messages, weights=self.weights, k=1)[0]

    def add(self, message_id: str, weight: float = 1.0) -> bool:
        """Adds a message to this pool"""
        check = BotState.DBLink.execute(("""
            SELECT message_name,weight FROM message_pools
            WHERE pool_id = ?
            AND chatid = ?
            AND message_name = ?
            """), (self.id, self.chat, message_id))
        exists = check.fetchone()
        if exists:
            return False
        BotState.DBLink.execute(("""
            INSERT INTO message_pools
            VALUES (?,?,?,?)
            """), (self.id, self.chat, message_id, weight))
        BotState.write()
        return True

    @staticmethod
    def get_messages(pool_id: str, chat_id: int) -> list:
        """
        Retrieves messages in a pool
        @param pool_id:
        @param chat_id:
        @return:
        """
        res = BotState.DBLink.execute(("""
            SELECT message_name,weight FROM message_pools
            WHERE pool_id = ?
            AND chatid = ?
            """), (pool_id, chat_id))
        rows = res.fetchall()
        return rows


class SaveMessage(TriggeredAction, action_name="save_msg"):
    """Saves a message to the MessageStore
    param 0: message name
    param 1: out success state
    param 2: optional chatid
    """
    async def run_action(self, message: TGMessage) -> str:
        if not message.reply_to_message:
            self.write_param(1,"no_message")
            return ""
        chatid = self.read_int(2)
        if chatid == -1:
            chatid = self.varstore["__chat_id"]
        msgname = self.read_string(0)
        store = MessageStore(chatid, message.from_user.id)
        saved = await store.store_message(message.reply_to_message, msgname)
        if saved:
            self.write_param(1,"ok")
            return ""
        self.write_param(1,"fail")
        return ""


class MoveMessage(TriggeredAction, action_name="move_saved_message"):
    """
    param 0: message name
    param 1: new scopeID (chatid/0 for global)
    """



class ReplaySavedMessage(TriggeredAction, action_name="emit_saved_message"):
    """Replays a saved message.
    param 0: message name
    param 1: message TTL, -1 to keep
    param 2: tag this message
    param 3: ID of the message to reply to. If not set (0), then this message won't be a reply.
    If -1, the message passed through the trigger will be used.
    param 4: Owner chat override, ignored if -1
    """
    async def run_action(self, message: TGMessage) -> str:
        if self.target_reply:
            if not message.reply_to_message:
                return "no_target"
            message = message.reply_to_message
        msgid = self.read_param(3)
        if msgid == -1:
            msgid = message.id
        msg_name = self.read_param(0)
        if not msg_name:
            return ""
        msg_ttl = float(self.read_param(1))
        msg_tag = self.read_param(2)
        chatid = self.varstore["__chat_id"]
        override = self.read_int(4)
        source = chatid if override == -1 else override
        store = MessageStore(chatid=source, user=self.varstore["__uid"])
        # put the message out
        results = await store.replay_message(name=msg_name, reply_to=msgid,target_chat=chatid)
        if results:
            for msgid in results:
                self.varstore["__last_msg"] = msgid
                # apply tags if specified
                if msg_tag:
                    messagetagger.MessageTagger.tag_message(chatid, msgid, msg_tag)
                # schedule kill if specified
                if msg_ttl != -1:
                    botutils.schedule_kill(chatid, msgid, msg_ttl)
        return ""


class FetchFromPool(TriggeredAction, action_name="fetch_pool"):
    """Fetches a message from a simple pool
    param 0: pool name
    param 1: Variable to store the fetched ID
    """
    async def run_action(self, message: TGMessage) -> str:
        # get a message out of the pool
        pool_id = self.read_param(0)
        out_var = self.read_param(1)
        pool = MessagePool(pool_id=pool_id)
        self.varstore[out_var] = pool.fetch()
        return ""
