"""
This module contains code dealing with actions the bot is able to perform based on things happening in the chat.
"""
import random
import json
import time

import telegram.constants
from telegram import Message as TGMessage

import UserInfo
import botstate
import botutils
import messagetagger
from env_vars import EnvVar


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
        self.orig_data = ""
        """Used to smuggle in the original string, as a heck."""

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
        for pattern in self.trigger:
            if pattern == data:
                return data
        return ""


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
    registry = {}
    """registry containing strings mapping to corresponding trigger actions"""

    @staticmethod
    def register(name:str, cls):
        TriggeredAction.registry[name] = cls

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
        self.trigger:Trigger
        """Dynamic parameter passed from trigger"""
        self.varstore = None
        """refers to common store"""
        self.matchdata =""
        """trigger match data"""

    def construct(self):
        """Factory method to realise correct subtype"""
        data = (self.sequence,self.subseq,self.action,self.data,self.target_reply)
        if self.action in TriggeredAction.registry:
            print(f"Spawned <{self.action}>")
            print(f"Params: START>{self.data}<END")
            return TriggeredAction.registry[self.action](*data)
        print(f"Failed to spawn <{self.action}>")

    def get_param(self, index: int):
        """
        Fetches a single param at a specific index.
        @param index: the index at which to retrieve.
        @return: a string containing the value if found, empty string otherwise.
        """
        if index >= len(self.data):
            print(f"Param <{index}> out of bounds of <{len(self.data)}>")
            value = ""
        else:
            value = self.data[index]
            print(f"value <{value}> obtained from <{index}>")
        if str(value).startswith("*"):
            var_name = value.removeprefix("*")
            print(f"var_store pointer read at <{var_name}>")
            if var_name not in self.varstore:
                print("bad pointer!")
                return ""
            print("good pointer.")
            print(f"value <{self.varstore[var_name]}> was fetched from <{var_name}>")
            return self.varstore[var_name]
        return value

    def get_pstr(self, index: int) -> str:
        """

        @param index:
        @return:
        """
        return str(self.get_param(index))

    def get_int(self, index: int) -> int:
        """
        Fetches a single param at a specific index, and attempts to get an int out of it.
        @param index: param index.
        @return: int if possible, 0 otherwise.
        """
        if index >= len(self.data):
            print(f"Param <{index}> out of bounds of <{len(self.data)}>")
            value = ""
        else:
            value = self.data[index]
            print(f"value <{value}> obtained from <{index}>")
        if str(value).startswith("*"):
            var_name = value.removeprefix("*")
            print(f"var_store pointer read at <{var_name}>")
            if var_name not in self.varstore:
                print("bad pointer!")
                return ""
            print("good pointer.")
            value = self.varstore[var_name]
        try:
            value = int(value)
        except (ValueError, TypeError):
            value = 0
        return value

    def get_params_rest(self, start_from:int) -> list[str]:
        """
        Fetches all remaining params starting from an index
        @param start_from: the index to start from
        @return: a list containing any params retrieved
        """
        if start_from not in self.data:
            return []
        result = []
        for param in self.data[start_from:]:
            value = ""
            if param.startswith("*"):
                param = param.removeprefix("*")
                if param in self.varstore:
                    value = self.varstore[param]
            else:
                value = param
            result.append(value)
        return result


    def get_string(self, poolname: str):
        return TriggeredSequence.running_sequences[self.sequence].get_string(poolname)

    async def run_action(self, message: TGMessage) -> str:
        """Does something with the message"""
        if self.target_reply:
            if not message.reply_to_message:
                return "no_target"
            message = message.reply_to_message


class TriggeredSequence:
    """Concerns sequences of actions that may be triggered."""

    running_sequences = {}
    """Contains currently loaded running sequences."""
    timed_subseqs = []
    """Contains subsequences registered to run on a timer"""

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
        # register timers if any
        if 'timers' in data:
            for timer in data['timers']:
                TriggeredSequence.register_timer(name, timer[0], timer[1])
        return cls(name,disp_name,desc,version,seq_triggers,subseqs,strings)

    async def run(self, message: TGMessage):
        """
        Runs this specific Sequence given message
        @param message:
        @return:
        """
        cat_txt = ["text_exact","text_prefix","text_suffix","text_contains"]
        cat_filter = []

        t_match = ""
        if message.text:
            cat_filter = cat_txt
            orig_text = message.text
        elif message.caption:
            orig_text = message.caption
        else:
            orig_text = ""
        prepped_text = botutils.S(orig_text).lower()
        tags = []
        if message.reply_to_message:
            tags = messagetagger.MessageTagger.get_tags(message.chat_id, message.reply_to_message.id)
        subseq = ""
        for trig in self.triggers:
            if trig.t_type in cat_filter and (trig.tag == "" or trig.tag in tags):
                t_match = trig.match(prepped_text)
                if t_match:
                    trig.orig_data = orig_text
                    subseq = trig.subseq
                    print(f"matched {orig_text}")
                    await self.run_subseq(subseq, trig, message, t_match)

    async def run_subseq(self, subseq:str, trigger:Trigger, message: TGMessage, matchdata: str = ""):
        """
        Runs a specific subsequence.
        @param subseq:
        @param trigger:
        @param message:
        @param matchdata
        @return:
        """
        if subseq not in self.subseqs:
            print('Argh, no subseq "' + subseq + '" found in sequence "'+self.name+'"')
            return
        var_store = {}
        var_store['__bot_uid'] = botstate.BotState.botuid
        actions = self.subseqs[subseq][:]
        print(repr(actions))
        while actions:
            for action in actions[:]:
                action.varstore = var_store
                action.trigger = trigger
                action.matchdata = matchdata
                print(f"{action.sequence}/{action.subseq}:{action.action} -> {action.data}")
                result = await action.run_action(message)
                # immediately shift to the new seq
                if result and result in self.subseqs:
                    actions = self.subseqs[result][:]
                    break
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
    def register_timer(sequence:str, subseq:str, period:float, run_once:bool = False):
        """Registers a subsequence to run timed.
        @param sequence:
        @param subseq:
        @param period:
        @param run_once:
        """
        # set next trigger time in one <period> from now
        time_next = time.time() + period
        # check if registered already
        for entry in TriggeredSequence.timed_subseqs[:]:
            seq, sub, per, next_time, run_once = entry
            if seq == sequence and subseq == sub:
                # store next trigger time and remove the entry
                time_next = next_time
                TriggeredSequence.timed_subseqs.remove(entry)
        # add new entry
        TriggeredSequence.timed_subseqs.append((sequence,subseq,period,time_next, run_once))

    @staticmethod
    async def run_timers():
        """
        Runs registered timed sequences.
        @return:
        """
        now = time.time()
        # go through list
        for entry in TriggeredSequence.timed_subseqs[:]:
            seq, sub, per, next_time, run_once = entry
            # if anything should be run
            if next_time < now:
                # check if valid reference
                if seq in TriggeredSequence.running_sequences:
                    sequence = TriggeredSequence.running_sequences[seq]
                    await sequence.run_subseq(sub, None, None)
                    # if it is not a one-off, append a copy at the end with updated timer
                    if not run_once:
                        TriggeredSequence.timed_subseqs.append((seq,sub,per,next_time + per, False))
                else:
                    print("timed <" + seq + "/" + sub + ">: missing sequence")
                TriggeredSequence.timed_subseqs.remove(entry)

    @staticmethod
    async def run_triggers(message: TGMessage):
        """

        @param message:
        @return:
        """
        for name, seq in TriggeredSequence.running_sequences.items():
            await seq.run(message)


class MockMessage:
    """Can be imported for use by actions not explicitly needing the actual Telegram Message"""
    def __init__(self, msgid:int):
        self.id = msgid


# ###############################################
#     Output Actions
# ###############################################

class EmitText(TriggeredAction):
    """Responds from an internal pool
    param 0: pool to use, can be *pointer
    param 1: message TTL, -1 to keep
    """
    async def run_action(self, message: TGMessage) -> str:
        pool_name = self.get_param(0)
        msg_ttl = int(self.get_param(1))
        if self.target_reply:
            if not message.reply_to_message:
                return "respond_no_target"
            message = message.reply_to_message
        text = self.get_string(pool_name)
        text = text.format_map(self.varstore)
        print("-------Writing message:--------\n" + text + "\n--------End of message:--------")
        msg = await botstate.BotState.bot.send_message(chat_id=message.chat.id, text=text,
                                                       parse_mode='MarkdownV2',
                                                       reply_to_message_id=message.id)
        if msg:

            self.varstore["__last_msg"] = msg.id
            botutils.schedule_kill(message.chat.id,msg.id,float(msg_ttl))
        return ""


class EmitPoll(TriggeredAction):
    """Posts a poll.
    param 0: text of the poll.
    param 1: variable containing answer options (list of string!)
    param 2: correct answer index
    param 3: timer
    param 4: type "quiz"/"regular"
    param 5: hide answers?
    param 6: variable to store the resulting poll ID into
    """
    async def run_action(self, message: TGMessage) -> str:
        text = self.get_param(0)
        answers = self.varstore[self.get_param(1)]
        correct = int(self.get_param(2))
        timer = int(self.get_param(3))
        poll_type = telegram.Poll.QUIZ if self.get_param(4) == "quiz" else telegram.Poll.REGULAR
        anon_mode = bool(self.get_param(5))
        poll_id_var = self.get_param(6)
        poll = await botstate.BotState.bot.send_poll(message.chat.id,
                                                     text,
                                                     answers,
                                                     type=poll_type,
                                                     is_anonymous=anon_mode,
                                                     correct_option_id=correct,
                                                     open_period=timer)
        if poll:
            self.varstore[poll_id_var] = poll.poll.id
            self.varstore["__last_msg"] = poll.id
        return ""


TriggeredAction.register("emit_text", EmitText)
TriggeredAction.register("emit_poll", EmitPoll)
# ###############################################
#     Flow Control Actions
# ###############################################


class GoSub(TriggeredAction):
    """Sets a Subsequence to follow next.
    param 0: Subsequence name or *pointer to one.
    """
    async def run_action(self, message: TGMessage) -> str:
        return self.get_param(0)


class BranchIfEquals(TriggeredAction):
    """
    Compares two values, then triggers one of the specified Subsequences depending on whether the values are equaol or not.
    param 0: first value
    param 1: second value
    param 2: subsequence to return if values are equaol
    param 3: subsequence to return if values are not equal
    """
    async def run_action(self, message: TGMessage) -> str:
        a = self.get_param(0)
        b = self.get_param(1)
        equal = self.get_param(2)
        not_equal = self.get_param(3)
        return equal if a == b else not_equal


TriggeredAction.register("gosub", GoSub)
TriggeredAction.register("if_eq", BranchIfEquals)
# ###############################################
#     Variable manipulation Actions
# ###############################################


class Concat(TriggeredAction):
    """Concatenates two values and stores the result
    param 0: first value
    param 1: second value
    param 2: variable to write
    """
    async def run_action(self, message: TGMessage) -> str:
        a = self.get_pstr(0)
        b = self.get_pstr(1)
        x = self.get_pstr(2)
        self.varstore[x] = a + b
        return ""


class Count(TriggeredAction):
    """Counts items in a given variable, then stores the results into a variable.
    param 0: Variable containing items to count.
    param 1: Variable to store the result into."""
    async def run_action(self, message: TGMessage) -> str:
        countvar = self.get_param(0)
        outvar = self.get_param(1)
        if countvar not in self.varstore:
            self.varstore[outvar] = -1
            return ""
        targetvar = self.varstore[countvar]
        self.varstore[outvar] = len(targetvar)
        return ""


class ReadAttribute(TriggeredAction):
    """Reads an attribute from an object stored in a variable and puts the result into another variable.
    param 0: Variable containing the object.
    param 1: Attribute to be read.
    param 2: Variable to store the read attribute."""
    async def run_action(self, message: TGMessage) -> str:
        obj_var = self.get_param(0)
        attr = self.get_param(1)
        out_var = self.get_param(2)
        result = ""
        if obj_var in self.varstore:
            obj = self.varstore[obj_var]
            result = getattr(obj, str(attr))
        self.varstore[out_var] = result
        return ""


class LoadTriggerData(TriggeredAction):
    """Loads trigger data into a var.
    param 0: Var to store to.
    """
    async def run_action(self, message: TGMessage) -> str:
        out_var = self.get_pstr(0)
        trig_data = self.matchdata
        self.varstore[out_var] = trig_data
        return ""


class FormatList(TriggeredAction):
    """Takes a list and a format string, outputs formatted list into a variable.
    param 0: variable to take the list from
    param 1: format string pool
    param 2: variable to write to"""
    async def run_action(self, message: TGMessage) -> str:
        listvar = self.get_param(0)
        poolname = self.get_param(1)
        outvar = self.get_param(2)
        if listvar not in self.varstore:
            self.varstore[outvar] = ""
            return "reference_error"
        data = self.varstore[listvar]
        fmt_string = self.get_string(poolname)
        output = ""
        for item in data:
            output += fmt_string.format(item)
        self.varstore[outvar] = output
        return ""


class RollPercent(TriggeredAction):
    """Rolls a chance expressed as a fraction of 1
    param 0: chance as a float between 0 and 1
    param 1: variable to write True or False to
    """
    async def run_action(self, message: TGMessage) -> str:
        chance_val = self.get_param(0)
        out_var = self.get_pstr(1)
        env_value = float(chance_val)
        roll = random.random()
        self.varstore[out_var] = roll < env_value
        return ""


class GetEnv(TriggeredAction):
    """

    """
    async def run_action(self, message: TGMessage) -> str:
        env_name = self.get_pstr(0)
        out_var = self.get_pstr(1)
        value = EnvVar.get(env_name, message.chat_id)
        self.varstore[out_var] = value
        print(f"Obtained <{value}> from <{env_name}> and stored in <{out_var}>")
        return ""


TriggeredAction.register("load_env",GetEnv)
TriggeredAction.register("concat", Concat)
TriggeredAction.register("count", Count)
TriggeredAction.register("obj_read", ReadAttribute)
TriggeredAction.register("fmt_list", FormatList)
TriggeredAction.register("roll_chance", RollPercent)
TriggeredAction.register("get_match", LoadTriggerData)
# ###############################################
#     Message information Actions
# ###############################################


class GetUID(TriggeredAction):
    """Gets the userID out of the message
    param 0: variable to store the extracted userID
    """
    async def run_action(self, message: TGMessage) -> str:
        outvar = self.get_param(0)
        if self.target_reply:
            if not message.reply_to_message:
                self.varstore[outvar] = 0
                return "no_target"
            message = message.reply_to_message
        self.varstore[outvar] = UserInfo.User.extract_uid(message)


class GetUserInfo(TriggeredAction):
    """Gets the complete UserInfo object and stores it.
    param 0: userID
    param 1: variable to store the user object.
    """
    async def run_action(self, message: TGMessage) -> str:
        uid = self.get_int(0)
        out_var = self.get_param(1)
        usr = UserInfo.User(uid, message.chat_id)
        self.varstore[out_var] = usr
        return ""


class CheckMessageType(TriggeredAction):
    """Checks if a message comes from a regular user, a bot,
    a channel or is a service message
    param 0: var_store variable to store the result in
    """
    async def run_action(self, message: TGMessage) -> str:

        var_name = self.data[0]
        if self.target_reply:
            if not message.reply_to_message:
                self.varstore[var_name] = "message_is_missing"
                return "no_target"
            message = message.reply_to_message
        if message.from_user.is_bot:
            if message.from_user.id == telegram.constants.ChatID.ANONYMOUS_ADMIN:
                self.varstore[var_name] = "message_is_channel"
            elif message.from_user.id == telegram.constants.ChatID.SERVICE_CHAT:
                self.varstore[var_name] = "message_is_service"
            else:
                self.varstore[var_name] = "message_is_bot"
        else:
            self.varstore[var_name] = "message_is_human"
        return ""


class GetMessageID(TriggeredAction):
    """Gets the message's ID.
    param 0: Variable to store the message ID.
    """
    async def run_action(self, message: TGMessage) -> str:
        if self.target_reply:
            if not message.reply_to_message:
                return "whois_no_target"
            message = message.reply_to_message
        out_var = self.get_param(0)
        self.varstore[out_var] = message.id
        return ""


class Whois(TriggeredAction):
    """Does a whois and responds one way or another
    param 0: variable prefix for the whois data
    """

    async def run_action(self, message: TGMessage) -> str:
        if self.target_reply:
            if not message.reply_to_message:
                return "whois_no_target"
            message = message.reply_to_message
        if message.from_user.id == botstate.botstate.botuid:
            return "self"
        uid = UserInfo.User.extract_uid(message)
        user = UserInfo.User(user_id=uid, chat_id=message.chat.id)
        vp = self.data[0]
        self.varstore[vp+"usernick"] = user.current_nick
        self.varstore[vp+"userid"] = user.id
        self.varstore[vp+"userrep"] = user.chatinfos[message.chat_id].reputation
        # TODO: add the rest of them
        return ""


TriggeredAction.register("check_message_type", CheckMessageType)
TriggeredAction.register("get_uid",GetUID)
TriggeredAction.register("get_user",GetUserInfo)
TriggeredAction.register("get_msgid", GetMessageID)
TriggeredAction.register("whois",Whois)
# ###############################################
#     Message manipulation Actions
# ###############################################


class RemoveMessage(TriggeredAction):
    """Erases a message
    param 0: time delay before removal
    """
    async def run_action(self, message: TGMessage) -> str:
        delay = self.data[0]
        if self.target_reply:
            if not message.reply_to_message:
                return "kill_no_target"
            message = message.reply_to_message
        botutils.schedule_kill(message.chat.id, message.id, float(delay))
        return ""


class TagMessage(TriggeredAction):
    """
    Tags a message
    param 0: tag to use
    param 1: message ID, if 0 is used, will use message object, if -1, will tag __last_msg
    """
    async def run_action(self, message: TGMessage) -> str:
        if self.target_reply:
            if not message.reply_to_message:
                return "tag_no_target"
            message = message.reply_to_message
        tag = self.get_pstr(0)
        msgid = self.get_int(1)
        if msgid == -1:
            msgid = self.varstore["__last_msg"]
        if msgid == 0:
            msgid = message.id
        messagetagger.MessageTagger.tag_message(message.chat_id, msgid, tag)
        return ""


TriggeredAction.register("tag_msg",TagMessage)


class KeepMessage(TriggeredAction):
    """Instructs the bot to not remove a message
    """
    async def run_action(self, message: TGMessage) -> str:
        if self.target_reply:
            if not message.reply_to_message:
                return "cancel_no_target"
            message = message.reply_to_message
        botutils.cancel_kill(message.chat.id, message.id)
        return ""


class EditMessage(TriggeredAction):
    """Edits a message using text from String Pools
    param 0: StringPool name
    param 1: MessageID, if not set (0), uses message from trigger.
    """
    async def run_action(self, message: TGMessage) -> str:
        strpool = self.get_param(0)
        msgid = self.get_param(1)
        if self.target_reply:
            if not message.reply_to_message:
                return "kill_no_target"
            message = message.reply_to_message
        if not msgid:
            msgid = message.id
        text = self.get_string(strpool)
        await botstate.BotState.bot.edit_message_text(chat_id=message.chat_id, message_id=msgid, text=text,
                                                      parse_mode="MarkdownV2")
        return ""


TriggeredAction.register("edit_msg",EditMessage)
TriggeredAction.register("kill_msg", RemoveMessage)
TriggeredAction.register("keep_msg", KeepMessage)
