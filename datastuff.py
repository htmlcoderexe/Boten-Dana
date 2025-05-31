# from email import message
# from urllib import response
import json
# import io
# import logging
# import os
import random
import string
# import sys
import time
from datetime import datetime
# from ast import arg
# from multiprocessing import context
# from pydoc import Helper
# from types import SimpleNamespace
from typing import Optional, Tuple
from collections import namedtuple
from enum import Enum

import requests
# import telegram
from telegram import InputMediaPhoto
# from telegram import Bot
from telegram import Update, Message, Poll
# from telegram.ext import CallbackContext, JobQueue
# from telegram.ext import ExtBot
from telegram.ext import ContextTypes

import botconfig
from botstate import BotState
import strings
from botutils import MD, TU, print_to_string


# import sqlite3
# from turtle import update
# from tkinter import E


# action functions


# sends a message to a chat/user
def send_message(message: string, target_id: int) -> requests.Response:
    send_text = (f"https://api.telegram.org/bot{botconfig.bottoken}/sendMessage?chat_id={target_id}&parse_mode"
                 f"=Markdown&text={message}")
    return requests.get(send_text)



# blast to all current chats
def blast(bot_message: string, remove: bool = True, doprivates: bool = False):
    for chat in BotState.current_chats:
        if str(chat)[0] != "-" and not doprivates:
            continue
        res = send_message(message=bot_message, target_id=chat)
        ajson = json.loads(res.content)
        print("------BLAST START-------")
        print("------MESSAGE START-----")
        print(bot_message)
        print("------MESSAGE END-------")
        print("------RESULT START------")
        print(ajson)
        print("------RESULT END--------")
        if "result" in ajson:
            update = Message.de_json(ajson["result"], bot=BotState.bot)
            if remove:
                schedule_kill(chatid=chat, msgid=update.id, expiration=time.time() + botconfig.killdelay)
        else:
            print("fuckity")
        print("------BLAST END---------")



# most recently seen first
def get_users(chatid: int) -> list[int] | None:
    res = BotState.DBLink.execute("""
    SELECT userid 
    FROM userseen
    WHERE chatid=?
    ORDER BY last DESC
    """, (chatid,))
    rows = res.fetchall()
    if not rows:
        return None
    result = [i[0] for i in rows]
    return result


# get a list of users, sorted by most messages
def get_active(chatid: int, count: int = 10) -> list[Tuple[int, int]]:
    res = BotState.DBLink.execute("""
    SELECT userid,msg 
    FROM repuser
    WHERE chatid=?
    ORDER BY msg DESC
    LIMIT ?
    """, (chatid, count))
    rows = res.fetchall()
    if not rows:
        return [(0, 0)]
    result = [i for i in rows]
    return result




# --- {PERMISSIONS STUFF

# give user permission
def perm_grant(chatid: int, userid: int, perm: string):
    BotState.DBLink.execute("""INSERT INTO perms VALUES (?,?,?)""", (chatid, userid, perm))
    BotState.write()
    return 0


# remove permission from user
def perm_revoke(chatid: int, userid: int, perm: string):
    BotState.DBLink.execute("""DELETE FROM perms WHERE chatid= ? AND userid = ? AND perm = ?""", (chatid, userid, perm))
    BotState.write()
    return 0


# check if user has permission
def perm_check(chatid: int, userid: int, perm: string) -> bool:
    res = BotState.DBLink.execute("""SELECT userid FROM perms WHERE chatid= ? AND userid = ? AND perm = ?""",
                                  (chatid, userid, perm))
    rows = res.fetchall()
    print(rows)
    if rows:
        return True
    return False


# --- END PERMISSIONS STUFF }



# TODO command function, unused?
def XCMD__listuser(chatid: int) -> str:
    users = get_users(chatid=chatid)
    nicks = []
    for u in users:
        nicks.append(get_newest_nick(userid=u, chatid=chatid))
    return "\n".join(nicks)

# TODO command function
def XCMD__listactive(chatid: int, count: int = 10) -> str:
    actives = get_active(chatid=chatid, count=count)
    lines = []
    for uid, msg in actives:
        lines.append("*" + MD(get_newest_nick(userid=uid, chatid=chatid)) + "* \\- " + MD(str(msg)))
    return "\n".join(lines)


# TODO: command function
def XCMD__whois(userid: int, chatid: int) -> str:
    print("---")
    print(BotState.botuid)
    print(userid)
    print("---")
    if BotState.botuid == userid:
        print("хуй")
        return MD(random.choice(strings.botwhoises))
    lasttime = get_last_seen(userid=userid, chatid=chatid)
    if lasttime == 0:
        return MD("да хуй знает, в первый раз вижу ¯\\_(ツ)_/¯")
    getjoin = get_join_date(userid=userid, chatid=chatid)
    if getjoin is None:
        print("empty joindate????")
        return MD("да хуй знает, в первый раз вижу ¯\\_(ツ)_/¯")
    date_time, fake = getjoin
    nicks = get_all_nicks(userid=userid, chatid=chatid)
    print(nicks)
    firstnick = nicks.pop(0)
    usernicks = ""
    if len(nicks) > 0:
        usernicks = "\n".join(nicks)
    returner = "Рецидивист. В чате уже {returntimes}-й раз.\n"
    from_beginning = "самого начала"
    quotes = ""
    userinfostring = """Пользователь {usernick}
aka {usernicks}
id {userid}
пепяка: {userrep}{medals}
последнее действие: {recent} назад
первое сообщение: {joindate}
{isreturner}{quotes}
    """
    medalsstring = ""
    d_time = datetime.fromtimestamp(date_time)
    joindate = d_time.strftime("%d-%m-%Y")
    print(getjoin)
    if fake != "false":
        joindate = from_beginning
    quotelist = get_quotes(userid=userid, chatid=0)
    if quotelist is not None:
        if len(quotelist) > 3:
            quotelist = random.sample(quotelist, 3)
        quotes = "\"" + "\"\n\"".join(map(str,quotelist)) + "\""

    if lasttime is None:
        lastformatted = "хз "
    else:
        lastformatted = fmt_timespan(time.time() - lasttime)
    num_joins = get_times_joined(userid=userid, chatid=chatid)
    if num_joins is None or len(num_joins) < 2:
        returnstring = ""
    else:
        returnstring = returner.format(returntimes=len(num_joins))
    rep = changerep(userid, chatid, 0)
    golds = score_fetch_scope(chatid=chatid,userid=userid,scorename="quiz_medals_0",scope="all")
    silvers = score_fetch_scope(chatid=chatid,userid=userid,scorename="quiz_medals_1",scope="all")
    bronzes = score_fetch_scope(chatid=chatid,userid=userid,scorename="quiz_medals_2",scope="all")
    if golds > 0:
        medalsstring = medalsstring + "🥇" + str(golds)
    if silvers > 0:
        medalsstring = medalsstring + "🥈" + str(silvers)
    if bronzes > 0:
        medalsstring = medalsstring + "🥉" + str(bronzes)
    if medalsstring != "":
        medalsstring = "\n" + medalsstring
    output = userinfostring.format(
        usernick=firstnick,
        usernicks=usernicks,
        recent=lastformatted,
        joindate=joindate,
        isreturner=returnstring,
        userrep=rep,
        quotes=quotes,
        userid=userid,
        medals=medalsstring
    )
    return MD(output)


# log an event
def XX__log_user_event(userid: int, chatid: int, event_type: string, data: string):
    last = time.time()
    BotState.DBLink.execute("""INSERT INTO user_events VALUES
    (?,?,?,?,?)
    """, (chatid, userid, last, event_type, data))
    print(f"Event of type <{event_type}> logged for user {userid}@{chatid}.")
    BotState.write()


# load all chats
def load_chats():
    res = BotState.DBLink.execute("SELECT DISTINCT chatid FROM userseen")
    chats = res.fetchall()
    #print(chats)
    for chat in chats:
        info = BotState.bot.get_chat(chat)
        #print(info)
        BotState.current_chats.append(chat[0])
    print(BotState.current_chats)




# joining users
# unused?
def XXU__handle_join(upd: Update) -> string:
    userid = upd.chat_member.new_chat_member.user.id
    chatid = upd.effective_chat.id
    log_user_event(userid=userid, chatid=chatid, event_type="joined", data="join")
    oldnick = get_newest_nick(userid=userid, chatid=chatid)
    newnick = upd.chat_member.new_chat_member.user.full_name
    if oldnick is None or oldnick != newnick:
        log_user_event(userid=userid, chatid=chatid, event_type="renamed", data=newnick)
    if oldnick is None:
        handle_new_user(userid=userid, chatid=chatid)


# leaving users
def XXU__handle_leave(upd: Update) -> string:
    userid = upd.chat_member.new_chat_member.user.id
    chatid = upd.effective_chat.id
    log_user_event(userid=userid, chatid=chatid, event_type="left", data="")

# covered in userchatinfo/setjoin
def XX__handle_new_user(userid: int, chatid: int, unknown_date: bool = False):
    last = time.time()
    BotState.DBLink.execute("""
    INSERT INTO join_dates 
    VALUES (?,?,?,?)
    """, (chatid, userid, last, "true" if unknown_date else "false"))
    BotState.write()


def superping(chatid: int):
    output = ""
    users = get_users(chatid=chatid)
    if users:
        for user in users:
            output += TU("🎺", userid=user)
    return output, 20, 5




# ------- CONSOLE STUFF
console_session_info = namedtuple("ConsoleSessionInfo",['chatid','userid','messageid'])


class env_var_option(Enum):
    GLOBAL = 0
    LOCAL = 1
    EFFECTIVE = 2


def console_create_session(chatid: int, userid: int, messageid: int):
    BotState.DBLink.execute(("""
    INSERT INTO console_sessions
    VALUES(?,?,?,?,?,?,?)
    """),(chatid,time.time(),time.time(),0,userid,messageid,""))
    BotState.write()


def console_update_session(chatid: int, userid: int, messageid: int,previous:int):
    BotState.DBLink.execute(("""
    UPDATE console_sessions
    SET last_active = ?,
    messageid = ?
    WHERE chatid = ?
    AND userid = ?
    AND messageid = ?
    """),(time.time(),messageid,chatid,userid,previous))
    BotState.write()


def console_set_mode(session: console_session_info,mode:str):
    BotState.DBLink.execute(("""
        UPDATE console_sessions
        SET mode = ?
        WHERE chatid = ?
        AND userid = ?
        AND messageid = ?
        """), (mode, session.chatid, session.userid, session.messageid))
    BotState.write()


def console_get_mode(session: console_session_info) -> str:
    session = BotState.DBLink.execute(("""
            SELECT mode FROM console_sessions
            WHERE chatid = ?
            AND userid = ?
            AND messageid = ?
            """), (session.chatid, session.userid, session.messageid))
    sessions = session.fetchone()
    if not sessions:
        return ""
    return sessions[0]








def console_end_session(chatid: int, userid: int, messageid: int):
    BotState.DBLink.execute(("""
    UPDATE console_sessions
    SET endtime = ?
    WHERE chatid = ?
    AND userid = ?
    AND messageid = ?
    """),(time.time(),chatid,userid,messageid))
    schedule_kill(chatid=chatid, msgid=messageid,expiration=0)
    BotState.write()


def console_check_session(chatid:int,userid:int,messageid:int):
    session = BotState.DBLink.execute(("""
        SELECT last_active FROM console_sessions
        WHERE chatid = ?
        AND userid = ?
        AND endtime = 0
        AND messageid = ?
        """), (chatid, userid, messageid))
    sessions = session.fetchall()
    if not sessions:
        return False
    return True


def console_find_latest_session(chatid:int,userid:int):
    sessions = BotState.DBLink.execute(("""
            SELECT messageid, mode FROM console_sessions
            WHERE chatid = ?
            AND userid = ?
            AND endtime = 0
            ORDER BY last_active DESC
            LIMIT 1
            """), (chatid, userid))
    session = sessions.fetchone()
    if not session:
        return None
    return session


def console_find_capture(userid: id, chatid: id):
    captures = BotState.DBLink.execute(("""
    SELECT capture_mode, context_id, capture_command
    FROM message_captures
    WHERE session_id = ?
    """),(str(chatid)+" "+str(userid),))
    return captures.fetchone()


def console_begin_capture(userid: int, chatid: int, mode: str, command: str, context: str):
    BotState.DBLink.execute(("""
    INSERT INTO message_captures
    VALUES (?,?,?,?)
    """),(str(chatid)+" "+str(userid),mode,context,command))


def console_end_capture(userid: int, chatid: int):
    BotState.DBLink.execute(("""
    DELETE FROM message_captures
    WHERE session_id = ?
    """),(str(chatid)+" "+str(userid),))


async def console_spawn(chatid: int, userid: int,source: int, text: string, previous:int = 0):
    new_console_msg = await BotState.bot.send_message(text=text, chat_id=chatid, reply_to_message_id=source,parse_mode="HTML")
    if console_check_session(chatid,userid,previous):
        schedule_kill(chatid=chatid, msgid=previous,expiration=0)
        console_update_session(chatid=chatid,userid=userid,messageid=new_console_msg.message_id,previous=previous)
    else:
        console_create_session(chatid=chatid,userid=userid,messageid=new_console_msg.message_id)
    schedule_kill(chatid=chatid,msgid=source,expiration=0)


async def console_begin(chatid: int, userid: int, source: int):
    await console_spawn(chatid=chatid,userid=userid,source=source,text="<pre>" + strings.console_greetings + "\nDanaBot#&gt;</pre>")


# was a one-off migration
def XUTIL__quiz_refresh_stats():

    BotState.DBLink.execute("""
    DELETE FROM scores
    WHERE scorename LIKE "quiz_%"
    """)

    res = BotState.DBLink.execute("""
    SELECT quiz_session_id,chatid
    FROM quiz_sessions
    WHERE chatid < 0
    AND ended = 1
    """)
    sessionlist = res.fetchall()
    for row in sessionlist:
        sessionid,chatid = row
        quiz_award_medals(sessionid,chatid)
