"""
This module contains code dealing with actions the bot is able to perform based on things happening in the chat.
"""
import random
import json
from telegram import Message as TGMessage

import QDB
import UserInfo
import botstate
import botutils
import messagestore
import messagetagger
import scores


# id    | name      |
# 1     | pizda     |   Pizda 1.0
# 2     | whois     |   Анализ 1.0
# 3     | cleaner   |   Чистка 1.0
# 4     | msgstore  |   База сообщений 1.0


# id    | sequence  |   env_var         | desc
# 1     | pizda     |   pizda_frequency | частота срабатывания пизды


# trigger: sequence and subsequence to match effects
# type affects how to match
# data used for matching
# tag to filter if tagging

# sequence  | subseq    | chatid    | msgid | tag

# id    | sequence  | subseq    | type      | data      | tag
# 1     | pizda     | main      | t_full    | да        | 0
# 2     | pizda     | твоя      | t_full    | твоя      | pizdareply
# 3     | pizda     | хуй       | t_full    | хуй       | pizdareply
# 4     | whois     | main      | t_full    | это кто   | 0     # for example: message reply with whois code phrase
# 5     | whois     | main      | t_full    | кто это   | 0     # checks all text triggers, matches trigger #4
# 6     | cleaner   | main      | t_full    | убери     | 0     # looks for whois/main action
# 7     | msgstore  | main      | t_pre     | держи     | 0     # runs whois/main #3
# 8     | whois     | self      | retval    |           | 0     # gets text from pool result if user found and returns nothing
# 9     | whois     | nobody    | retval    |           | 0     # if user is Dana, return "self"
# 10    | whois     | 404       | retval    |           | 0     # trigger check procs again for retval type
# 11    | msgstore  | save_ok   | retval    |           | 0
class Trigger:
    """A trigger that can be matched against"""
    def __init__(self, seq: str, subseq: str, t_type:str, data: list[str], tag:str = ""):
        self.sequence = seq
        """Sequence activated by trigger"""
        self.subseq = subseq
        """Subsequence activated by trigger"""
        self.trigger = data
        """Trigger data"""
        self.t_type = t_type
        """Trigger type"""
        self.tag = tag
        """Tag to constrain the trigger"""

    def construct(self):
        match self.t_type:
            case "text_exact":
                return TriggerTextExact(self.sequence,self.subseq,self.t_type,self.trigger,self.tag)
            case "retval":
                return TriggerRetVal(self.sequence,self.subseq,self.t_type,self.trigger,self.tag)
            case "text_contains":
                return TriggerTextContains(self.sequence,self.subseq,self.t_type,self.trigger,self.tag)
            case "text_prefix":
                return TriggerTextPre(self.sequence,self.subseq,self.t_type,self.trigger,self.tag)
            case "text_suffix":
                return TriggerTextPost(self.sequence,self.subseq,self.t_type,self.trigger,self.tag)

    def match(self, data:str) -> str:
        """Checks if the message matches the trigger"""
        pass


class TriggerTextExact(Trigger):
    """Matches exact text"""

    def match(self, data:str) -> str:
        return data if self.trigger[0] == data else ""


class TriggerTextPre(Trigger):
    """Matches a prefix and returns trimmed remains"""

    def match(self, data:str) -> str:
        if data.startswith(self.trigger[0]):
            return data.removeprefix(self.trigger[0]).strip()
        return ""


class TriggerTextPost(Trigger):
    """Matches a postfix and returns trimmed remains"""

    def match(self, data:str) -> str:
        if data.endswith(self.trigger[0]):
            return data.removesuffix(self.trigger[0]).strip()
        return ""


class TriggerTextContains(Trigger):
    """Matches if the text is found anywhere"""

    def match(self, data:str) -> str:
        return data if self.trigger[0] in data else ""


class TriggerRetVal(Trigger):
    """Matches when previous action returns a value"""

    def match(self, data:str) -> str:
        return data if self.subseq == data else ""

# id    | sequence  |   subseq  | type  | data          | data2
# 1     | pizda     |   main    | rpool | pizda_pool    |
# 11    | pizda     |   respond | rpool | pizda_pool    | -1
# 2     | pizda     |   твоя    | rpool | pizda_t_pool  | -1
# 3     | whois     |   main    | whois | whois_result  | 60
# 4     | whois     |   404     | rpool | whois_404     |
# 5     | whois     |   self    | rpool | whois_self    |
# 6     | whois     |   nobody  | rpool | whois_nobody  |
# 7     | cleaner   |   main    | rm    |               |
# 8     | cleaner   |   ok      | rpool | cleaner_ok    | 1.0
# 9     | cleaner   |   human   | rpool | cleaner_hu    | 1.0
# 10    | cleaner   |   nothing | rpool | cleaner_no    | 1.0
# 11    | msgstore  |   main    | save  | saveok        | 1.0
# 11    | msgstore  |   save_no | rpool | savefail      | 1.0
# 12    | msgstore  |   main    | load  |               | 1.0
class TriggeredAction:
    """An action that may be triggered"""
    def __init__(self,seq:str, subseq:str,a_type:str, data:list[str], target_reply:bool):
        self.data = data
        """Action param"""
        self.action = a_type
        """Action to take"""
        self.sequence = seq
        """Sequence action belongs to"""
        self.subseq = subseq
        """Sequence branch action belongs to"""
        self.target_reply = target_reply
        """Apply the TriggeredAction to the message replied to if true."""
        self.param =""
        """Dynamic parameter passed from trigger"""
        self.varstore = None

    def construct(self):
        """Factory method to realise correct subtype"""
        match self.action:
            case "reply_pool":
                return ActionRespond(self.sequence,self.subseq,self.action,self.data,self.target_reply)
            case "reply_text":
                return ActionRespondText(self.sequence,self.subseq,self.action,self.data,self.target_reply)
            case "whois":
                return ActionWhois(self.sequence,self.subseq,self.action,self.data,self.target_reply)
            case "kill_src":
                return ActionKillDirect(self.sequence,self.subseq,self.action,self.data,self.target_reply)
            case "kill_reply":
                return ActionKillReply(self.sequence,self.subseq,self.action,self.data,self.target_reply)
            case "scoreboard":
                return ActionScoreBoard(self.sequence,self.subseq,self.action,self.data,self.target_reply)
            case "score_up":
                return ActionScoreUpReplied(self.sequence,self.subseq,self.action,self.data,self.target_reply)
            case "save_msg":
                return ActionSaveMessage(self.sequence,self.subseq,self.action,self.data,self.target_reply)
            case "roll_env":
                return ActionRandomProc(self.sequence,self.subseq,self.action,self.data,self.target_reply)
            case "check_userlist":
                return ActionCheckUserList(self.sequence,self.subseq,self.action,self.data,self.target_reply)

    async def run_action(self, message: TGMessage) -> str:
        """Does something with the message"""
        pass


class ActionRespond(TriggeredAction):
    """Responds from a simple pool
    param 0: pool name
    param 1: message TTL, -1 to keep
    param 2: tag this message
    """

    async def run_action(self, message: TGMessage) -> str:
        if self.target_reply:
            if not message.reply_to_message:
                return "respond_no_target"
            message = message.reply_to_message
        # get a message out of the pool
        pool = messagestore.MessagePool(pool_id=self.data[0])
        store = messagestore.MessageStore(chatid=message.chat_id, user=message.from_user.id, glob=True)
        # put the message out
        results = await store.replay_message(name=pool.fetch(), reply_to=message.id)
        if results:
            for msgid in results:
                # apply tags if specified
                if self.data[2]:
                    messagetagger.MessageTagger.tag_message(message.chat_id, msgid, self.data[2])
                # schedule kill if specified
                if self.data[1] != -1:
                    botutils.schedule_kill(message.chat.id, msgid, float(self.data[1]))
        return ""


class ActionRespondText(TriggeredAction):
    """Responds from an internal pool
    param 0: pool to use
    param 1: message TTL, -1 to keep
    """
    async def run_action(self, message: TGMessage) -> str:
        if self.target_reply:
            if not message.reply_to_message:
                return "respond_no_target"
            message = message.reply_to_message
        text = TriggeredSequence.running_sequences[self.sequence].get_string(self.data[0])
        msg = await botstate.BotState.bot.send_message(chat_id=message.chat.id, text=text,
                                                       parse_mode='MarkdownV2',
                                                       reply_to_message_id=message.id)
        if msg:
            botutils.schedule_kill(message.chat.id,msg.id,float(self.data[1]))
        return ""


class ActionKillDirect(TriggeredAction):
    """Kills the triggering message
    param 0: seconds to keep
    """

    async def run_action(self, message: TGMessage) -> str:
        botutils.schedule_kill(message.chat.id, message.id, float(self.data[0]))
        return ""


class ActionKillReply(TriggeredAction):
    """Kills the message replied to.
    param 0: seconds to keep
    """

    async def run_action(self, message: TGMessage) -> str:
        if not message.reply_to_message:
            return "nomessage"
        botutils.schedule_kill(message.chat.id, message.reply_to_message.id, float(self.data[0]))
        return ""


class ActionWhois(TriggeredAction):
    """Does a whois and responds one way or another
    param 0: string pool for the template
    param 1: seconds to keep the message
    """

    async def run_action(self, message: TGMessage) -> str:
        if self.target_reply:
            if not message.reply_to_message:
                return "whois_no_target"
            message = message.reply_to_message
        if message.from_user.id == botstate.botstate.botuid:
            return "self"
        user = UserInfo.User(user_id=message.from_user.id, chat_id=message.chat.id)

        whoistpl = TriggeredSequence.running_sequences[self.sequence].get_string(self.data[0])
        whoistpl = whoistpl.format(usernick=user.current_nick,
                                   userid=user.id,
                                   userrep=user.chatinfos[message.chat_id].reputation)
        msg = await botstate.BotState.bot.send_message(chat_id=message.chat.id, text=whoistpl, parse_mode='MarkdownV2',
                                                       reply_to_message_id=message.id)
        if msg:
            botutils.schedule_kill(message.chat.id,msg.id,float(self.data[1]))
        return ""


class ActionScoreBoard(TriggeredAction):
    """Shows a top scoreboard
    param 0: score to show
    param 1: number of winners
    param 2: text pool to use
    param 3: message TTL, -1 to keep
    """

    async def run_action(self, message: TGMessage) -> str:
        if self.target_reply:
            if not message.reply_to_message:
                return "scoreboard_no_target"
            message = message.reply_to_message
        ss = scores.ScoreHelper(message.from_user.id,message.chat.id)
        board = ss.get_top(self.data[0], int(self.data[1]))
        board_text =""
        for name,score,uid in board:
            name = botutils.MD(name)
            board_text += botutils.TU(name,int(uid)) + "    " + str(score) + "\n"
        tpl = TriggeredSequence.running_sequences[self.sequence].get_string(self.data[2])
        tpl = tpl.format(board=board_text)
        msg = await botstate.BotState.bot.send_message(chat_id=message.chat.id, text=tpl, parse_mode='MarkdownV2',
                                                       reply_to_message_id=message.id)
        if msg:
            botutils.schedule_kill(message.chat.id, msg.id, float(self.data[1]))
        return ""


class ActionSaveMessage(TriggeredAction):
    """Saves a message to the MessageStore"""

    async def run_action(self, message: TGMessage) -> str:
        if not message.reply_to_message:
            return "nomessage"
        msgname = ""
        match self.data[0]:
            case "var_store":
                msgname = self.varstore[self.data[1]]
            case "param":
                msgname = self.param
            case "prefixed":
                msgname = self.data[1] + self.param
        store = messagestore.MessageStore(message.chat.id, message.from_user.id)
        saved = await store.store_message(message.reply_to_message, msgname)
        if saved:
            self.varstore[self.data[2]] = msgname
            return ""
        return "savefail"


class ActionRemoveMessage(TriggeredAction):
    """Erases a message"""
    async def run_action(self, message: TGMessage) -> str:
        if not message.reply_to_message:
            return "nomessage"
        if message.reply_to_message.from_user.is_bot:
            return "remove_ok"
            pass  # TODO: link to message killing system
        return "remove_human"


class ActionCheckUserList(TriggeredAction):
    """Checks if triggering user is on a UserList
    param 0: UserList name
    param 1: returned if user on the list
    param 2: returned if user NOT on the list
    """
    async def run_action(self, message: TGMessage) -> str:
        if self.target_reply:
            if not message.reply_to_message:
                return "respond_no_target"
            message = message.reply_to_message
        uid = message.from_user.id
        res = botstate.BotState.DBLink.execute("""
        SELECT user_id FROM userlists
        WHERE name = ?
        AND user_id = ?
        """,(self.data[0], uid))
        row = res.fetchone()
        return self.data[1] if row else self.data[2]


class ActionRandomProc(TriggeredAction):
    """Rolls a chance based on an env_var
    param 0: env_var containing chance
    param 1: returned if roll succeeds
    param 2: returned if roll fails
    """
    async def run_action(self, message: TGMessage) -> str:
        env_value = float(self.data[0])  # TODO: properly get env_var
        roll = random.random()
        return self.data[1] if roll < env_value else self.data[2]


class ActionScoreUpReplied(TriggeredAction):
    """Ups a score
    param 0: score name
    param 1: amount
    """
    async def run_action(self, message: TGMessage) -> str:
        if self.target_reply:
            if not message.reply_to_message:
                return "scoreup_no_target"
            message = message.reply_to_message
        ss = scores.ScoreHelper(message.from_user.id, message.chat.id)
        amount = int(self.data[1])
        ss.add(self.data[0], amount)
        return ""


class ActionAnnounceScore(TriggeredAction):
    """Announces a single score
    param 0: score name
    param 1: message TTL
    param 2: string pool
    """
    async def run_action(self, message: TGMessage) -> str:
        if self.target_reply:
            if not message.reply_to_message:
                return "score_announce_no_target"
            message = message.reply_to_message
        ss = scores.ScoreHelper(message.from_user.id, message.chat.id)
        amount = ss.get(self.data[0])
        tpl = TriggeredSequence.running_sequences[self.sequence].get_string(self.data[2])
        tpl = tpl.format(score=amount)
        msg = await botstate.BotState.bot.send_message(chat_id=message.chat.id, text=tpl, parse_mode='MarkdownV2',
                                                       reply_to_message_id=message.id)
        if msg:
            botutils.schedule_kill(message.chat.id, msg.id, float(self.data[1]))
        return ""


class ActionQDBSave(TriggeredAction):
    """
    Saves to QDB
    param 0: additional score to give to the saved quote
    param 1: prefix for redirected returns
    """
    async def run_action(self, message: TGMessage) -> str:
        if not message.reply_to_message:
            return self.data[1] + "_nomessage"
        if not message.reply_to_message.text and not message.reply_to_message.caption:
            return self.data[1] + "_notext"
        text = message.reply_to_message.text_markdown_v2 if message.reply_to_message.text else message.reply_to_message.caption_markdown_v2
        uid = UserInfo.User.extract_uid(message.reply_to_message)
        msgid = message.reply_to_message.id
        chatid = message.chat.id
        replyid = 0
        replytext = ""
        replyuser = 0
        qdb = QDB.Database(message.chat.id, message.from_user.id)
        # use pyro to get the context of the message being captured if possible
        pc = botstate.BotState.pyroclient
        fullmsg = await pc.get_messages(chatid,msgid)
        if fullmsg and fullmsg.reply_to_message:
            replyid = fullmsg.reply_to_message.id
            replyuser = UserInfo.User.extract_uid(fullmsg.reply_to_message)
            replytext = fullmsg.reply_to_message.text if fullmsg.reply_to_message.text else replytext
            replytext = fullmsg.reply_to_message.caption if fullmsg.reply_to_message.caption else replytext

        q = qdb.save_quote(text=text, msg_id=msgid, user_id=uid, reply_text=replytext, reply_user=replyuser, reply_id=replyid)
        if int(self.data[0]) > 0:
            q.upvote()
            return self.data[1] + "_ok"


class ActionQDBGetUserQuotes(TriggeredAction):
    """
    Gets quotes for user
    param 0: amount of quotes to get, -1 to get all
    param 1: "local" or "global" to get quotes from everywhere or just this chat.
    param 2: score threshold
    param 3: sorting mode: "score", "newest", "oldest"
    """



class TriggeredSequence:
    """Concerns sequences of actions that may be triggered."""

    running_sequences = {}
    """Contains currently loaded running sequences."""

    def __init__(self, name:str, display_name:str, desc:str, version:tuple[int], triggers:list[Trigger], subseqs:dict[str,list[TriggeredAction]],
                 strings=None):
        if strings is None:
            strings = {}
        self.name = name
        self.display_name = display_name
        self.description = desc
        self.version = version
        self.triggers = triggers
        self.subseqs = subseqs
        self.strings = strings

    @classmethod
    def load_from_json(cls, json_data:str):
        """"""
        data = json.loads(json_data)
        print(data)
        name = data['name']
        disp_name = data['display_name']
        desc = data['description']
        version = data['version']
        # load triggers
        triggerlist = data['triggers']
        seq_triggers = []
        for trig in triggerlist:
            print(trig)
            tseq = name
            ttype = trig['type']
            tsubseq = trig['subseq']
            tparams = trig['params']
            ttag = "" if 'tag' not in trig else trig['tag']
            seq_triggers.append(Trigger(tseq,tsubseq,ttype,tparams,ttag).construct())
        print(triggerlist)
        print(seq_triggers)
        # load subseqs
        subseqs = {}
        subseqlist = data['subseqs'].items()
        for subseq,actions in subseqlist:
            actionlist = []
            for action in actions:
                atype = action['action']
                aparams = action['params']
                atarget = False
                if 'target' in action:
                    atarget = True
                actionlist.append(TriggeredAction(name,subseq,atype,aparams,atarget).construct())
            subseqs[subseq] = actionlist
        # load stringpools if any
        strings = None if 'stringpools' not in data else data['stringpools']
        return cls(name,disp_name,desc,version,seq_triggers,subseqs,strings)

    async def run(self, message: TGMessage):
        """

        @param message:
        @return:
        """
        cat_txt = ["text_exact","text_prefix","text_suffix","text_contains"]
        cat_filter = []

        var_store = {}
        t_match = ""
        if message.text:
            cat_filter = cat_txt
        subseq = ""
        for trig in self.triggers:
            if trig.t_type in cat_filter:
                t_match = trig.match(message.text)
                if t_match:
                    subseq = trig.subseq
                    print(f"matched{message.text}")
        if not subseq:
            return
        if subseq not in self.subseqs:
            print('Argh, no subseq "' + subseq + '" found in sequence "'+self.name+'"')
            return
        actions = self.subseqs[subseq][:]
        while actions:
            for action in actions[:]:
                action.varstore = var_store
                action.param = t_match
                print(f"{action.sequence}/{action.subseq}:{action.action}")
                result = "404" # await action.run_action(message)
                if result and result in self.subseqs:
                    actions += self.subseqs[result]
                actions.remove(action)

    def get_string(self, pool_name:str):
        """
        Get a string from the sequence's internal string pools
        @param pool_name: string pool name
        @return: a string picked from the pool if pool exists, else an error string
        """
        if pool_name not in self.strings:
            return "text.missing.error"
        return random.choice(self.strings[pool_name])

    @staticmethod
    def run_triggers(message: TGMessage, category: str = "", data: str = ""):
        """

        @param data:
        @param category:
        @param message: Message to check
        @return:
        """
        tags = ["none"]
        if message.reply_to_message:
            tags = TriggeredSequence.get_tags(message.reply_to_message.id, message.chat.id)
        if not category:
            if message.text:
                category = "text"
                data = botutils.S(message.text.lower())
            if message.caption:
                category = "text"
                data = botutils.S(message.caption.lower())
        triggers = TriggeredSequence.get_triggers(category, tags)
        actions = []
        if triggers:
            for trigger in triggers:
                if trigger.match(data):
                    actions += TriggeredSequence.load_actions(trigger.sequence,trigger.subseq, trigger.match(data))
        while actions:
            for action in actions:
                result = action.run_action(message)
                if result:
                    triggers = TriggeredSequence.get_triggers("retval", tags)
                    if triggers:
                        for trigger in triggers:
                            if trigger.match(result):
                                actions += TriggeredSequence.load_actions(trigger.sequence, trigger.subseq, trigger.match(result))

    @staticmethod
    def get_triggers(caterogy: str, tags: list[str]) -> list[Trigger]:
        type_text = "('t_full', 't_pre', 't_post', 't_wild'"
        type_ret = "('retval')"
        subst_type = "('')"
        match caterogy:
            case "text":
                subst_type = type_text
            case "retval":
                subst_type = type_ret
        q = f"""
        SELECT sequence, subseq, type, data
        FROM action_triggers
        WHERE type IN {subst_type}
        """
        if tags:
            q += "AND TAGS IN (" + ",".join(tags) + ")"
        res = botstate.BotState.DBLink.execute(q)
        rows = res.fetchall()
        triggers = []
        if not rows:
            return []
        for row in rows:
            trg = Trigger(*row).construct()
            triggers.append(trg)
        return triggers

    @staticmethod
    def get_tags(msgid: int, chatid:int) -> list[str]:
        res = botstate.BotState.DBLink.execute("""
                    SELECT tag
                    FROM sequence_tags
                    WHERE msgid = ?
                    AND chatid =?""", (msgid,chatid))
        rows = res.fetchall()
        if rows:
            return [row[0] for row in rows]
        return ["none"]

    @staticmethod
    def load_actions(sequence: str, subseq: str, param: str):
        """Loads the action set"""
        res = botstate.BotState.DBLink.execute("""
        SELECT sequence,subseq,type,data
        FROM triggered_actions
        WHERE sequence = ?
        AND subseq = ?""",(sequence,subseq))
        rows = res.fetchall()
        actions = []
        if not rows:
            return []
        for row in rows:
            act = TriggeredAction(*row).construct()
            act.param = param
            actions.append(act)
        return actions



