"""
This module contains code dealing with actions the bot is able to perform based on things happening in the chat.
"""
import copy
import random
import json
import time

import telegram.constants
from telegram import Message as TGMessage
from telegram.ext import ContextTypes

import UserInfo
import botstate
import botutils
import env_vars
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
    def __init__(self, seq: str, subseq: str, t_type:str, data: list[str], tag:str = "", raw_mode:bool = False):
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
        self.raw_mode:bool = raw_mode
        """Whether the trigger consumes sanitised string or raw string."""
        self.orig_data = ""
        """Used to smuggle in the original string, as a heck."""
        self.tagdata:tuple[str]
        """Any additional tag-related data"""

    def construct(self):
        itemdata = (self.sequence,self.subseq,self.t_type,self.trigger,self.tag, self.raw_mode)
        match self.t_type:
            case "text_exact":
                return TriggerTextExact(*itemdata)
            case "retval":
                return TriggerRetVal(*itemdata)
            case "text_contains":
                return TriggerTextContains(*itemdata)
            case "text_prefix":
                return TriggerTextPre(*itemdata)
            case "text_suffix":
                return TriggerTextPost(*itemdata)

    def match(self, data:str) -> str:
        """Checks if the message matches the trigger"""
        pass

    @classmethod
    def Empty(cls):
        return cls("","","",[""],"",False)


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
    action_name:str = "nop"
    """Action names used in the registry."""

    @staticmethod
    def register(name:str, cls):
        TriggeredAction.registry[name] = cls

    # noinspection PyMethodOverriding
    def __init_subclass__(cls, action_name:str, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.action_name = action_name
        print(f"Registered <{cls.__name__}> as <{action_name}>.")
        TriggeredAction.register(action_name, cls)

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
            #print(f"Spawned <{self.action}>")
            #print(f"Params: START>{self.data}<END")
            return TriggeredAction.registry[self.action](*data)
        print(f"Failed to spawn <{self.action}>")

    def resolve_pointer(self, value:str):
        """

        @param value:
        @return:
        """
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

    def write_param(self, index: int, value):
        """
        Writes to var_store given variable
        @param index: param containing the variable name
        @param value: value to write
        @return:
        """
        print("Attempting to write to var_store")
        var_name = self.read_string(index)
        if not var_name == "":
            self.varstore[var_name] = value
            print(f"Wrote to <{var_name}> in var_store.")
        else:
            print(f"Failed to write: string issue, probably.")

    def read_param(self, index: int):
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
        return self.resolve_pointer(value)

    def read_string(self, index: int) -> str:
        """

        @param index:
        @return:
        """
        return str(self.read_param(index))

    def read_int(self, index: int) -> int:
        """
        Fetches a single param at a specific index, and attempts to get an int out of it.
        @param index: param index.
        @return: int if possible, 0 otherwise.
        """
        value = self.read_param(index)
        try:
            value = int(value)
        except (ValueError, TypeError):
            print(f"Unable to get int from <{value}>, casting 0")
            value = -1
        return value

    def read_to_end(self, start_from:int) -> list[str]:
        """
        Fetches all remaining params starting from an index
        @param start_from: the index to start from
        @return: a list containing any params retrieved
        """
        if start_from >= len(self.data):
            print(f"No more params after {start_from}. Returning empty list.")
            return []
        result = []
        for i in range(start_from, len(self.data)):
            value = self.read_param(i)
            result.append(value)
        print(f"Obtained following params: <{result}>")
        return result

    def get_random_string(self, poolname: str):
        return TriggeredSequence.running_sequences[self.sequence].get_random_string(poolname)

    async def run_action(self, message: TGMessage) -> str:
        """Does something with the message"""
        if self.target_reply:
            if not message.reply_to_message:
                return "no_target"
            message = message.reply_to_message


class SequenceMd2Info:
    def __init__(self, name:str,display_name:str,description:str,version:str):
        self.name = name
        self.display_name = display_name
        self.description = description
        self.version = version


class TriggeredSequence:
    """Concerns sequences of actions that may be triggered."""

    running_sequences = {}
    """Contains currently loaded running sequences."""
    timed_subseqs = []
    """Contains subsequences registered to run on a timer"""

    def __init__(self, name:str, display_name:str, desc:str, version:tuple[int], triggers:list[Trigger], subseqs:dict[str,list[TriggeredAction]],
                 strings=None, config_vars:dict[str,tuple[str,str]] = None, commands:dict[str,tuple[str,str]] = None):
        if strings is None:
            strings = {}
        self.name = name
        """Name of this sequence."""
        self.display_name = display_name
        """Display name of this sequence."""
        self.description = desc
        """Description of this sequence."""
        self.version = version
        """Version, standard version convention."""
        self.triggers = triggers
        """Triggers defined for this sequence."""
        self.subseqs = subseqs
        """Subsequences defined in this sequence."""
        self.strings = strings
        """String pools defined in this sequence."""
        self.env_vars = config_vars
        """Environment variables used for configuring this sequence."""
        self.commands = commands
        """Commands registered for this sequence."""

    def md2info(self) -> SequenceMd2Info:
        info = SequenceMd2Info(botutils.MD(self.name), botutils.MD(self.display_name),botutils.MD(self.description),botutils.MD(f"{self.version[0]}.{self.version[1]}.{self.version[2]}"))
        # print(info.__dict__)
        return info

    @classmethod
    def load_from_json(cls, json_data:str):
        """"""
        errorcounter = 0
        data = json.loads(json_data)
        # print(data)
        name = data['name']
        disp_name = data['display_name']
        desc = data['description']
        print(f"Loading <{name}> \"<{disp_name}>\".")
        version = data['version']
        # load triggers
        triggerlist = data['triggers']
        seq_triggers = []
        for trig in triggerlist:
            # print(trig)
            tseq = name
            ttype = trig['type']
            tsubseq = trig['subseq']
            tparams = trig['params']
            ttag = "" if 'tag' not in trig else trig['tag']
            rawmode = False if 'raw' not in trig else True
            seq_triggers.append(Trigger(tseq,tsubseq,ttype,tparams,ttag, rawmode).construct())
        # print(triggerlist)
        # print(seq_triggers)
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
                action_obj = TriggeredAction(name,subseq,atype,aparams,atarget).construct()
                if action_obj is not None:
                    actionlist.append(action_obj)
                else:
                    print(f"Unknown Action <{atype}>, skipping.")
                    errorcounter += 1
                    actionlist = []
            if actionlist:
                print(f"Loaded subseq <{subseq}>.")
                subseqs[subseq] = actionlist
            else:
                print(f"Dropping subseq <{subseq}>.")
                continue
        # load stringpools if any
        strings = None if 'stringpools' not in data else data['stringpools']
        # register timers if any
        if 'timers' in data:
            for timer in data['timers']:
                TriggeredSequence.register_timer(name, timer[0], timer[1])
            print(f"Loaded {len(data['timers'])} timers.")
        # load and init declared config vars
        config_vars = {}
        if 'config_vars' in data:
            # print(data['config_vars'])
            for cfgvar in data['config_vars']:
                var = cfgvar['name']
                cfg_desc = cfgvar['display_name']
                default = cfgvar['default']
                config_vars[var] = (cfg_desc, default)
                # set a default value if the var hasn't been set before
                #if env_vars.EnvVar.get_scope(var, 0) is None:
                #    env_vars.EnvVar.set_scope(var, 0, default)
            print(f"Loaded {len(data['config_vars'])} configuration variables.")
        # load and init declared config vars
        commands = {}
        if 'commands' in data:
            for cmd, info in data['commands'].items():
                cmd_desc = info['description']
                subseq= info['subseq']
                commands[cmd] = (cmd_desc, subseq)
            print(f"Loaded {len(data['commands'])} commands.")
        print(f"Loaded <{name}> with {errorcounter} errors.")
        return cls(name,disp_name,desc,version,seq_triggers,subseqs,strings,config_vars,commands)

    async def run(self, message: TGMessage):
        """
        Runs this specific Sequence given message
        @param message:
        @return:
        """
        # set a list of trigger filters, TODO: fix hardcoding text type
        cat_txt = ["text_exact","text_prefix","text_suffix","text_contains"]
        cat_filter = []

        t_match = ""
        # get text out
        if message.text:
            cat_filter = cat_txt
            orig_text = message.text
        elif message.caption:
            cat_filter = cat_txt
            orig_text = message.caption
        else:
            orig_text = ""
        # normalise to make matching easier
        prepped_text = botutils.S(orig_text).lower()
        tags = []
        # if replying to something, check if that has any additional data we saved earlier
        if message.reply_to_message:
            tags = messagetagger.MessageTagger.get_tags(message.chat_id, message.reply_to_message.id)
        subseq = ""
        # go thru triggers
        for trig in self.triggers:
            t_match = ""
            # for now this is redundant, used to filter by a specific trigger category
            if trig.t_type in cat_filter:
                # matching is cheap enough to to regardless
                t_match = trig.match(orig_text if trig.raw_mode else prepped_text)
                # set the entire matched text
                trig.orig_data = orig_text
                if t_match:
                    # the trigger applies as long as 1) it has no tag or 2) it matches the current tag
                    if trig.tag == "" or trig.tag in tags:
                        # set the correct subseq to run
                        subseq = trig.subseq
                        print(f"matched <{orig_text}>")
                        # set extra info if actually found
                        if trig.tag in tags:
                            trig.tagdata = tags[trig.tag]
                        # go
                        await self.run_subseq(subseq, trig, message, t_match)

    def get_command_handler(self, command:str):
        async def handler(update:telegram.Update, context: ContextTypes.DEFAULT_TYPE):
            subseq = self.commands[command][1]
            await self.run_subseq(subseq, Trigger.Empty(),update.message,"")
        return handler

    async def run_subseq(self, subseq:str, trigger:Trigger, message: TGMessage, matchdata: str = ""):
        """
        Runs a specific subsequence.
        @param subseq:
        @param trigger:
        @param message:
        @param matchdata
        @return:
        """
        # not found!
        if subseq not in self.subseqs:
            print('Argh, no subseq "' + subseq + '" found in sequence "'+self.name+'"')
            return
        print(f"--- ENTRY POINT <{subseq}> ---")
        triggering_user = 0
        if message is not None:
            triggering_user = UserInfo.User.extract_uid(message)
        # init local variable store
        var_store = {'__bot_uid': botstate.BotState.botuid, '__uid': triggering_user}
        # get a copy of the actions list
        actions = self.subseqs[subseq][:]
        print(repr(actions))
        # keep going as long as there are any actions left
        while actions:
            # go through a copy of the current list until exhausted
            for action in actions[:]:
                # provide reference to variable store
                action.varstore = var_store
                # original trigger and its data
                action.trigger = trigger
                # whatever the trigger returned as the match
                action.matchdata = matchdata
                # execute
                print(f"{action.sequence}/{action.subseq}:{action.action} -> {action.data}")
                result = str(await action.run_action(message))
                # if non-empty result, try to run this as the new subseq
                # immediately shift to the new subseq
                if result:
                    if result in self.subseqs:
                        # copy the new subseq and exit the iteration
                        # this drops any remaining actions
                        actions = self.subseqs[result][:]
                        print(f"--- GOTO <{result}> ---")
                        break
                    elif result.startswith("*") and result.removeprefix("*") in self.subseqs:
                        # put new subseq at the front, followed by the rest of current subseq
                        # that way you get a CALL that returns
                        result = result.removeprefix("*")
                        actions.remove(action)
                        actions = self.subseqs[result][:] + actions
                        print(f"--- CALL <{result}> ---")
                        break
                # otherwise just remove this action from the original copy and keep going
                actions.remove(action)

    def get_random_string(self, pool_name:str):
        """
        Get a string from the sequence's internal string pools
        @param pool_name: string pool name
        @return: a string picked from the pool if pool exists, else an error string
        """
        if pool_name not in self.strings:
            print(f"Couldn't find string pool <{pool_name}>.")
            return "String pool not found"
        print(f"Found string pool <{pool_name}>, picking random string.")
        return random.choice(self.strings[pool_name])

    def get_string(self, pool_name:str, index:int):
        """
        Gets a string from the sequence's internal string pools at a specific index.
        @param pool_name: string pool name
        @param index: index
        @return: a string selected by the parameters, or an error if not found
        """
        if pool_name not in self.strings:
            print(f"Couldn't find string pool <{pool_name}>.")
            return "String pool not found."
        if 0 <= index < len(self.strings[pool_name]):
            print(f"Fetching string <{index}> from <{pool_name}>.")
            return self.strings[pool_name][index]
        print(f"Index <{index}> is not in <{pool_name}>.")
        return "String index out of bounds."

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

class EmitText(TriggeredAction, action_name="emit_text"):
    """Responds from an internal pool
    param 0: pool to use, can be *pointer
    param 1: message TTL, -1 to keep
    """
    async def run_action(self, message: TGMessage) -> str:
        pool_name = self.read_param(0)
        msg_ttl = self.read_int(1)
        if self.target_reply:
            if not message.reply_to_message:
                return "respond_no_target"
            message = message.reply_to_message
        text = self.get_random_string(pool_name)
        text = text.format_map(self.varstore)
        print("-------Writing message:--------\n" + text + "\n--------End of message:--------")
        msg = await botstate.BotState.bot.send_message(chat_id=message.chat.id, text=text,
                                                       parse_mode='MarkdownV2',
                                                       reply_to_message_id=message.id)
        if msg:

            self.varstore["__last_msg"] = msg.id
            botutils.schedule_kill(message.chat.id,msg.id,float(msg_ttl))
        return ""


class EmitPoll(TriggeredAction, action_name="emit_poll"):
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
        text = self.read_param(0)
        answers = self.varstore[self.read_param(1)]
        correct = int(self.read_param(2))
        timer = int(self.read_param(3))
        poll_type = telegram.Poll.QUIZ if self.read_param(4) == "quiz" else telegram.Poll.REGULAR
        anon_mode = bool(self.read_param(5))
        poll_id_var = self.read_param(6)
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

# ###############################################
#     Flow Control Actions
# ###############################################


class GoSub(TriggeredAction, action_name="gosub"):
    """Sets a Subsequence to follow next.
    param 0: Subsequence name or *pointer to one.
    """
    async def run_action(self, message: TGMessage) -> str:
        return self.read_string(0)


class Call(TriggeredAction, action_name="call"):
    """Sets a Subsequence to call, returning once finished.
    param 0: Subsequence name or *pointer to one.
    """
    async def run_action(self, message: TGMessage) -> str:
        return "*" + self.read_string(0)


class BranchIfEquals(TriggeredAction, action_name="if_eq"):
    """
    Compares two values, then triggers one of the specified Subsequences depending on whether the values are equaol or not.
    param 0: first value
    param 1: second value
    param 2: subsequence to return if values are equaol
    param 3: subsequence to return if values are not equal
    """
    async def run_action(self, message: TGMessage) -> str:
        a = self.read_param(0)
        b = self.read_param(1)
        equal = self.read_param(2)
        not_equal = self.read_param(3)
        if a == b:
            print(f"Values are equal, taking branch <{equal}>.")
            return equal
        print(f"Values are not equal, taking branch <{not_equal}>.")
        return not_equal


class BranchIfGreaterOrEqual(TriggeredAction, action_name="if_gte"):
    """
    Compares two values, then triggers one of the specified Subsequences depending on
    whether the first value is greater or equal than the second one or not.
    param 0: first value
    param 1: second value
    param 2: subsequence to return if first value is greater or equal to the second one
    param 3: subsequence to return if first value is less than the second one
    """
    async def run_action(self, message: TGMessage) -> str:
        a = self.read_param(0)
        b = self.read_param(1)
        gte = self.read_param(2)
        not_gte = self.read_param(3)
        if a >= b:
            print(f"Value B is smaller, taking branch <{gte}>.")
            return gte
        print(f"Values A is smaller, taking branch <{not_gte}>.")
        return not_gte


# ###############################################
#     Variable manipulation Actions
# ###############################################


class Concat(TriggeredAction, action_name="concat"):
    """Concatenates two values and stores the result
    param 0: first value
    param 1: second value
    param 2: variable to write
    """
    async def run_action(self, message: TGMessage) -> str:
        a = self.read_string(0)
        b = self.read_string(1)
        x = self.read_string(2)
        self.varstore[x] = a + b
        return ""


class Add(TriggeredAction, action_name="add"):
    """Adds two values and stores the result
    param 0: first value
    param 1: second value
    param 2: variable to write
    """
    async def run_action(self, message: TGMessage) -> str:
        a = self.read_int(0)
        b = self.read_int(1)
        x = self.read_string(2)
        self.varstore[x] = a + b
        return ""


class Count(TriggeredAction, action_name="count"):
    """Counts items in a given variable, then stores the results into a variable.
    param 0: Variable containing items to count.
    param 1: Variable to store the result into."""
    async def run_action(self, message: TGMessage) -> str:
        countvar = self.read_param(0)
        outvar = self.read_param(1)
        if countvar not in self.varstore:
            self.varstore[outvar] = -1
            return ""
        targetvar = self.varstore[countvar]
        self.varstore[outvar] = len(targetvar)
        return ""


class Escape(TriggeredAction, action_name="escape"):
    """
    Escapes a string for MarkDownV2, then stores the results.
    param 0: String to be escaped.
    param 1: out results.
    """
    async def run_action(self, message: TGMessage) -> str:
        text = self.read_string(0)
        text = botutils.MD(text,2)
        self.write_param(1,text)
        return ""


class TimestampNow(TriggeredAction, action_name="get_time"):
    """
    Gets current timestamp and stores it.
    param 0: output variable
    """
    async def run_action(self, message: TGMessage) -> str:
        self.write_param(0,time.time())
        return ""


class ReadAttribute(TriggeredAction, action_name="obj_read"):
    """Reads an attribute from an object stored in a variable and puts the result into another variable.
    param 0: Variable containing the object.
    param 1: Attribute to be read.
    param 2: Variable to store the read attribute."""
    async def run_action(self, message: TGMessage) -> str:
        obj_var = self.read_param(0)
        attr = self.read_param(1)
        out_var = self.read_param(2)
        result = ""
        if obj_var in self.varstore:
            obj = self.varstore[obj_var]
            result = getattr(obj, str(attr))
        self.varstore[out_var] = result
        return ""


class LoadTriggerData(TriggeredAction, action_name="get_match"):
    """Loads trigger data into a var.
    param 0: Var to store to.
    """
    async def run_action(self, message: TGMessage) -> str:
        out_var = self.read_string(0)
        trig_data = self.matchdata
        self.varstore[out_var] = trig_data
        return ""


class FormatList(TriggeredAction, action_name="fmt_list"):
    """Takes a list and a format string, outputs formatted list into a variable.
    param 0: variable to take the list from
    param 1: format string pool
    param 2: variable to write to"""
    async def run_action(self, message: TGMessage) -> str:
        listvar = self.read_param(0)
        poolname = self.read_param(1)
        outvar = self.read_param(2)
        if listvar not in self.varstore:
            self.varstore[outvar] = ""
            return "reference_error"
        data = self.varstore[listvar]
        fmt_string = self.get_random_string(poolname)
        output = ""
        for item in data:
            output += fmt_string.format(item)
        self.varstore[outvar] = output
        return ""


class RollPercent(TriggeredAction, action_name="roll_chance"):
    """Rolls a chance expressed as a fraction of 1
    param 0: chance as a float between 0 and 1
    param 1: variable to write True or False to
    """
    async def run_action(self, message: TGMessage) -> str:
        chance_val = self.read_param(0)
        out_var = self.read_string(1)
        env_value = float(chance_val)
        roll = random.random()
        self.varstore[out_var] = roll < env_value
        return ""


class GetEnv(TriggeredAction, action_name="load_env"):
    """

    """
    async def run_action(self, message: TGMessage) -> str:
        env_name = self.read_string(0)
        out_var = self.read_string(1)
        value = EnvVar.get(env_name, message.chat_id)
        self.varstore[out_var] = value
        print(f"Obtained <{value}> from <{env_name}> and stored in <{out_var}>")
        return ""


# ###############################################
#     Message information Actions
# ###############################################


class GetUID(TriggeredAction, action_name="get_uid"):
    """Gets the userID out of the message
    param 0: variable to store the extracted userID
    """
    async def run_action(self, message: TGMessage) -> str:
        outvar = self.read_param(0)
        if self.target_reply:
            if not message.reply_to_message:
                self.varstore[outvar] = 0
                return "no_target"
            message = message.reply_to_message
        self.varstore[outvar] = UserInfo.User.extract_uid(message)


class GetUserInfo(TriggeredAction, action_name="get_user"):
    """Gets the complete UserInfo object and stores it.
    param 0: userID
    param 1: variable to store the user object.
    """
    async def run_action(self, message: TGMessage) -> str:
        uid = self.read_int(0)
        out_var = self.read_param(1)
        usr = UserInfo.User(uid, message.chat_id)
        self.varstore[out_var] = usr
        return ""


class CheckMessageType(TriggeredAction, action_name="check_message_type"):
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


class GetMessageID(TriggeredAction, action_name="get_msgid"):
    """Gets the message's ID.
    param 0: Variable to store the message ID.
    """
    async def run_action(self, message: TGMessage) -> str:
        if self.target_reply:
            if not message.reply_to_message:
                return "whois_no_target"
            message = message.reply_to_message
        out_var = self.read_param(0)
        self.varstore[out_var] = message.id
        return ""


class GetLoadedSequences(TriggeredAction, action_name="get_seqs"):
    """

    param 0: variable to store the information
    """
    async def run_action(self, message: TGMessage) -> str:
        out_var = self.read_param(0)
        seq_info = []
        for seq_name, seq_data in TriggeredSequence.running_sequences.items():
            seq_info.append(seq_data.md2info())
        self.varstore[out_var] = seq_info
        return ""


class Whois(TriggeredAction, action_name="whois"):
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


# ###############################################
#     Message manipulation Actions
# ###############################################


class RemoveMessage(TriggeredAction, action_name="kill_msg"):
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


class TagMessage(TriggeredAction, action_name="tag_msg"):
    """
    Tags a message
    param 0: tag to use
    param 1: message ID, if 0 is used, will use message object, if -1, will tag __last_msg
    params X: any extra data up to 7 items
    """
    async def run_action(self, message: TGMessage) -> str:
        if self.target_reply:
            if not message.reply_to_message:
                return "tag_no_target"
            message = message.reply_to_message
        tag = self.read_string(0)
        msgid = self.read_int(1)
        extras = self.read_to_end(2)
        if msgid == -1:
            msgid = self.varstore["__last_msg"]
        if msgid == 0:
            msgid = message.id
        messagetagger.MessageTagger.tag_message(message.chat_id, msgid, tag, *extras)
        return ""


class KeepMessage(TriggeredAction, action_name="keep_msg"):
    """Instructs the bot to not remove a message
    """
    async def run_action(self, message: TGMessage) -> str:
        if self.target_reply:
            if not message.reply_to_message:
                return "cancel_no_target"
            message = message.reply_to_message
        botutils.cancel_kill(message.chat.id, message.id)
        return ""


class EditMessage(TriggeredAction, action_name="edit_msg"):
    """Edits a message using text from String Pools
    param 0: StringPool name
    param 1: MessageID, if not set (0), uses message from trigger.
    """
    async def run_action(self, message: TGMessage) -> str:
        strpool = self.read_param(0)
        msgid = self.read_param(1)
        if self.target_reply:
            if not message.reply_to_message:
                return "kill_no_target"
            message = message.reply_to_message
        if not msgid:
            msgid = message.id
        text = self.get_random_string(strpool)
        await botstate.BotState.bot.edit_message_text(chat_id=message.chat_id, message_id=msgid, text=text,
                                                      parse_mode="MarkdownV2")
        return ""
