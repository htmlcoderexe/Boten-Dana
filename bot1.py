import os
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import telegram.helpers
from pyrogram import Client
from telegram import Poll, Update, ChatMember, ChatMemberUpdated
from telegram.ext import CallbackContext
from telegram.ext import filters, PollAnswerHandler, MessageHandler, ApplicationBuilder, CommandHandler, \
    ContextTypes, MessageReactionHandler, ChatMemberHandler

import UserInfo
import actions
import botutils
import env_vars
import scheduled_events
import quizstuff
import messagestore
import antimat
import botconfig
import scores
from botstate import BotState
import changelogs
import datastuff


# #process member update, stole from PTB docs:
def extract_status_change(chat_member_update: ChatMemberUpdated) -> Optional[Tuple[bool, bool]]:
    """Takes a ChatMemberUpdated instance and extracts whether the 'old_chat_member' was a member
    of the chat and whether the 'new_chat_member' is a member of the chat. Returns None, if
    the status didn't change.
    """
    status_change = chat_member_update.difference().get("status")
    old_is_member, new_is_member = chat_member_update.difference().get("is_member", (None, None))

    if status_change is None:
        return None

    old_status, new_status = status_change
    was_member = old_status in [
        ChatMember.MEMBER,
        ChatMember.OWNER,
        ChatMember.ADMINISTRATOR,
    ] or (old_status == ChatMember.RESTRICTED and old_is_member is True)
    is_member = new_status in [
        ChatMember.MEMBER,
        ChatMember.OWNER,
        ChatMember.ADMINISTRATOR,
    ] or (new_status == ChatMember.RESTRICTED and new_is_member is True)

    return was_member, is_member


async def test_poll(chatid: int):
    pollupdate = (await BotState.bot.send_poll(
        chatid,
        "Тест",
        ["Вар. 1", "Вар. 2", "Вар. 3", "Вар. 4"],
        type=Poll.QUIZ,
        is_anonymous=False,
        correct_option_id=2,
        open_period=45))
    print("----POLL POSTED:----")
    print(pollupdate)
    print("-----END POLL POSTED")


# message handlers

# start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please fuck me!")


# #called on any regular messages
async def chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # update bot's userID
    # global botuid
    BotState.botuid = context.bot.id
    BotState.bot = context.bot
    if update.message is None:
        # it could be something else!!
        if update.edited_message is not None:
            print("it was edited.")
        return
    # extract useful information from the update
    chatid = update.effective_chat.id
    userid = UserInfo.User.extract_uid(update.message)
    nickname = UserInfo.User.extract_nick(update.message)

    usr = UserInfo.User.refresh(user_id=userid,chat_id=chatid)

    print(repr(usr))
    print(chatid)
    if update.message and update.message.text:
        print("------------------")
        print(update.message.text)
        print("------------------")
    usr.msg_uptick()
    usr.refresh_nick(nickname)
    # upcount voice seconds if there's a voice message
    if update.message.voice is not None:
        usr.score_add("voice", update.message.voice.duration)
        usr.score_add("voice_count")
    if update.message.video_note is not None:
        usr.score_add("eblovoice", update.message.video_note.duration)
        usr.score_add("eblovoice_count")
    if update.message.text:
        rawtext = update.message.text.strip()
        # stext = S(update.message.text.lower())
        # also upcount character counts
        usr.score_add("text",len(rawtext))
        usr.score_add("mat",len(antimat.get_mats("тест " + rawtext + " тест")))
    await actions.TriggeredSequence.run_triggers(update.message)


async def restart_bot(context: CallbackContext):
    print("going down...")
    datastuff.blast("ухожу в ребут...")
    # os.fsync()
    print(sys.argv)
    os.execv(sys.executable, ['python'] + sys.argv)


async def random_chatter(chatid:int):
    chat_freq_var = env_vars.EnvVar.get(env_name="random_chatter_freq", chatid=chatid)
    try:
        chat_freq = float(chat_freq_var)
    except ValueError:
        chat_freq = 0.001

    chat_pool = env_vars.EnvVar.get(env_name="random_chatter_pool_id", chatid=chatid)
    if random.random() < chat_freq and chat_pool:
        store = messagestore.MessageStore(chatid,0)
        pool = messagestore.MessagePool(chat_pool,chatid)
        name = pool.fetch()
        await store.replay_message(name,0,chatid)


# #run this to keep checking for messages to kill
async def everyminute(context: CallbackContext):
    kills = scheduled_events.ScheduledEvent.fetch_events("msg_kill")
    for kill in kills:
        botutils.kill_message(chatid=kill.chat_id, msgid=kill.event_data[0])
    await actions.TriggeredSequence.run_timers()
    await actions.TriggeredSequence.process_events()
    # for chat in BotState.current_chats:
    #    if str(chat)[0] != "-":
    #        continue
    #    await random_chatter(chatid=chat)


async def actually_every_minute(context: CallbackContext):
    pass


async def receive_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    print("-------QUIZ ANSWER DATA!!")
    print(update)
    print("-------QUIZ ANSWER DATA END---------------!!")
    answer = update.poll_answer.option_ids[0]
    uid = update.poll_answer.user.id
    if uid in (telegram.constants.ChatID.ANONYMOUS_ADMIN, telegram.constants.ChatID.SERVICE_CHAT,
               telegram.constants.ChatID.FAKE_CHANNEL):
        uid = update.poll_answer.voter_chat.id
    pollid = int(update.poll_answer.poll_id)
    print("user " + str(uid) + " answered #" + str(answer) + " on poll " + str(pollid))
    # TODO: triggers based on poll responses
    # datastuff.quiz_verify_answer(poll=int(pollid), user=uid, answer=answer)
    # TODO: THIS IS HACK PUT PROPER HANDLER YOU FUCKASS
    quizstuff.QuizPlaySession.submit_answer(pollid, uid, answer)


async def receive_reaction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    print(update)
    # msg = await BotState.pyroclient.get_messages(update.effective_chat.id,update.message_reaction.message_id)
    # print(msg)
    # TODO: triggers based on reactions
    # await console_capture_message(userid=update.effective_user.id,chatid=update.effective_chat.id,msg=msg)
    pass


async def join_leave(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    print("fuck")
    print(update)
    if update.chat_member is None:
        return
    old, new = extract_status_change(update.chat_member)
    uid = update.chat_member.new_chat_member.user.id
    actor_uid = update.chat_member.from_user.id
    chatid = update.chat_member.chat.id
    new_user = UserInfo.User.refresh(uid,chatid, True)
    if old and not new:
        # user left
        new_user.log_event("left","left")
        if uid != actor_uid:
            # user got removed?
            # #TODO: special event trigger for this
            new_user.log_event("removed",actor_uid)

        scheduled_events.ScheduledEvent.schedule_event("user_leave",chatid, -1, uid)
        pass
    if new and not old:
        # user joined
        new_user.log_event("joined","joined")
        if uid != actor_uid:
            # user got added?
            # #TODO: special event trigger for this
            new_user.log_event("added",actor_uid)

        if len(new_user.current_chat.joins) > 1:
            scheduled_events.ScheduledEvent.schedule_event("user_rejoin", chatid, -1, uid)
        else:
            scheduled_events.ScheduledEvent.schedule_event("user_join", chatid, -1, uid)


async def chat_load():
    print("---------LOADING CHATS")
    await datastuff.load_chats()
    print("DONE LOADING----------")


async def reg_commands(context: CallbackContext):
    print("registering commands...")
    commands = [("start","initiate the bot"),("settings","configure stuff"),("help","no help")]
    for seqname, seq in actions.TriggeredSequence.running_sequences.items():
        for cmd,info in seq.commands.items():
            commands.append((cmd,info[0]))
    await BotState.bot.set_my_commands(commands)
    print(f"registered {len(commands)} commands.")


def one_off_updateMDV2():
    quotes_r = BotState.DBLink.execute("SELECT qid, quote FROM qdb")
    quotes = quotes_r.fetchall()
    for line in quotes:
        qid,quote = line
        if not quote:
            quote = " "
        escaped_quote = telegram.helpers.escape_markdown(quote,2)
        BotState.DBLink.execute("UPDATE qdb SET quote = ? WHERE qid = ?",(escaped_quote,qid))
    BotState.write()


def one_off_redo_quiz_scores():
    res = BotState.DBLink.execute("SELECT quiz_session_id FROM quiz_sessions",())
    rows = res.fetchall()
    sessioncount = len(rows)
    print(f"Loaded {sessioncount} sessions.")
    for i, row in enumerate(rows):
        sessid = row[0]
        print(f"[{i}/{sessioncount}] Processing <{sessid}>")
        if sessid[0:4] != "-100":
            print("Skipping session from chat.")
            continue
        session = quizstuff.QuizPlaySession.load(sessid)
        if session:
            results = session.get_results()
            stoday = datetime.fromtimestamp(session.time)
            print(f"Awarding medals on {str(stoday)}")
            for j, result in enumerate(results):
                sh = scores.ScoreHelper(result[4], session.chat_id,stoday)
                if j >= len(quizstuff.QuizPlaySession.MEDAL_EMOJI):
                    sh.add("quiz_medals_other")
                sh.add("quiz_medals_" + str(j))
                sh.add("quiz_participations")
            print(f"Awarded {len(results)} medals.")
        else:
            print("Not found.")


# #launch the thing
if __name__ == '__main__':
    # init links to Telegram
    application = ApplicationBuilder().token(botconfig.bottoken).build()
    BotState.bot = application.bot
    BotState.DB = botconfig.DB
    BotState.DBLink = botconfig.DB.cursor()
    # one_off_updateMDV2()
    # one_off_redo_quiz_scores()
    BotState.pyroclient = Client("BotenDana")
    # create handlers
    start_handler = CommandHandler('start', start)

    seqdir = Path("./sequences")
    seqfiles = list(seqdir.glob("*.json"))
    for seq in seqfiles:
        sdata = seq.read_text("UTF-8")
        sequence = actions.TriggeredSequence.load_from_json(sdata)
        actions.TriggeredSequence.running_sequences[sequence.name] = sequence
    print(f"Loaded {len(actions.TriggeredSequence.running_sequences)} sequences.")

    handlers = []
    for seqname, seq in actions.TriggeredSequence.running_sequences.items():
        for cmd,info in seq.commands.items():
            handlers.append(CommandHandler(cmd,seq.get_command_handler(cmd)))
    for handler in handlers:
        application.add_handler(handler)
    allmsg_handler = MessageHandler(filters.ALL, chat_message)  # & (~filters.COMMAND), chat_message)
    # joinleave_handler = ChatMemberHandler(member_change, ChatMemberHandler.CHAT_MEMBER)

    # register handlers
    # application.add_handler(joinleave_handler)
    application.add_handler(start_handler)
    application.add_handler(allmsg_handler)
    application.add_handler(PollAnswerHandler(receive_poll_answer))
    application.add_handler(MessageReactionHandler(receive_reaction))
    application.add_handler(ChatMemberHandler(join_leave, ChatMemberHandler.CHAT_MEMBER))
    # state inits
    datastuff.load_chats()
    # datastuff.quiz_refresh_stats()
    BotState.q = application.job_queue
    print("registering one-run")
    BotState.q.run_once(reg_commands, 0.0)
    print("registering onceasecond")
    BotState.q.run_repeating(callback=everyminute, interval=1, first=1)
    print("registering onceaminute")
    BotState.q.run_repeating(callback=everyminute, interval=60, first=1)
    # BotState.q.run_repeating(callback=reg_commands, interval=6, first=1)
    # startup messages
    # #datastuff.blast("перезагрузка успешна!!11")
    changelogs.blast_logs()

    # start the main bot
    BotState.pyroclient.start()
    application.job_queue.run_once(reg_commands, 1.0)
    application.run_polling(allowed_updates=Update.ALL_TYPES)
    # botstate.pyroclient.stop()
    # anything to do before shutting down
    # #datastuff.blast("ухожу в ребут...")
