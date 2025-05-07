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


# #------ Message killing ------

# delete a specific message from a chat
def kill_message(chatid: int, msgid: int) -> requests.Response:
    BotState.DBLink.execute("DELETE from msgkills WHERE chatid=? AND msgid = ?", (chatid, msgid))
    BotState.write()
    return requests.get(
        f"https://api.telegram.org/bot{botconfig.bottoken}/deleteMessage?chat_id={chatid}&message_id={msgid}")


# assign a specific message to be deleted at a future time
def schedule_kill(chatid: int, msgid: int, expiration: float):
    BotState.DBLink.execute("""
    INSERT INTO msgkills
    VALUES (?,?,?)
    """,
                            (chatid, msgid, expiration)
                            )
    BotState.write()
    print("scheduled to kill message")


# find any messages due to be deleted
def check_kills() -> list[Tuple[int, int]] | None:
    res = BotState.DBLink.execute("""
    SELECT chatid,msgid FROM msgkills
    WHERE expiration < ?
    """, (time.time(),))
    rows = res.fetchall()
    if not rows:
        return None
    return rows


# #----- END message killing ------


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


def write_message_event(chatid: int, msgid: int, event_type: string, data0: string = "", data1: string = "", data2: string = "", data3: string = "", data4: string = "", data5: string = "", data6: string = ""):
    BotState.DBLink.execute("INSERT INTO message_events VALUES (?,?,?,?,?,?,?,?,?,?)",(chatid,msgid,event_type,data0,data1,data2,data3,data4,data5,data6))
    BotState.write()


def tag_pizda_target(chatid: int, msgid: int, userid: int):
    write_message_event(chatid=chatid,msgid=msgid,event_type="pizda_target",data0=userid)


def find_pizda_target(chatid:int,msgid:int) -> int:
    res = BotState.DBLink.execute("""
    SELECT data0 FROM message_events
    WHERE chatid = ? 
    AND messageid = ?
    """,(chatid,msgid))
    row = res.fetchone()
    if row:
        return row[0]
    return 0


def tag_pizda_reply(chatid:int, msgid: int,userid:int, replytoid: int,depth: int = 0):
    write_message_event(chatid=chatid,msgid=msgid,event_type="pizda_reply",data0=userid,data1=replytoid,data2=depth)


def check_if_pizda_reply(chatid:int,msgid:int) -> int:
    res = BotState.DBLink.execute("""
    SELECT data0, data1, data2 FROM message_events
    WHERE chatid = ?
    AND messageid = ?
    AND event_type = ?
    """,(chatid,msgid,"pizda_reply"))
    row = res.fetchone()
    if row:
        return int(row[0])
    return 0


# update user's last seen and add to existing users.
# covered in User
def XX__log_user(userid: int, chatid: int):
    last = time.time()
    res = BotState.DBLink.execute("SELECT last FROM userseen where userid=? AND chatid=?", (userid, chatid))
    row = res.fetchone()
    if row is None:
        # print(f"user {userid} set to {last} ")
        BotState.DBLink.execute("INSERT INTO userseen VALUES (?,?,?,0,'')", (chatid, userid, last))
    else:
        # print(f"user {userid} updated to {last} ")
        BotState.DBLink.execute("UPDATE userseen SET last=? WHERE  chatid=? AND userid=?", (last, chatid, userid))
    BotState.write()

# replaced in User/ChatInfo
# most recent user activity
def XX__get_last_seen(userid: int, chatid: int):
    res = BotState.DBLink.execute("""
    SELECT last 
    FROM userseen 
    WHERE userid=? 
    AND chatid=?
    """, (userid, chatid))
    row = res.fetchone()
    if row is None:
        return 0
    else:
        return row[0]

    # get a list of all users seen by the bot in a specific chat


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

# replaced in User/Info
# most recent "name change", likely what is still used
def XX__get_newest_nick(userid: int, chatid: int) -> Optional[str]:
    res = BotState.DBLink.execute("""
    SELECT event_data 
    FROM user_events
    WHERE userid=?
    AND chatid=?
    AND event_type="renamed"
    ORDER BY time DESC
    LIMIT 1
    """, (userid, chatid))
    row = res.fetchone()
    if row is None:
        return None
    return row[0]

# replaced in User/Info
# find all names of one user
def XX__get_all_nicks(userid: int, chatid: int) -> list[str] | None:
    res = BotState.DBLink.execute("""
    SELECT event_data 
    FROM user_events
    WHERE userid=?
    AND chatid=?
    AND event_type="renamed"
    ORDER BY time DESC
    """, (userid, chatid))
    rows = res.fetchall()
    if not rows:
        return None
    result = [i[0] for i in rows]
    return result


# count amount of joins by this user, currently broken :(
def XX_get_times_joined(userid: int, chatid: int) -> list[str] | None:
    res = BotState.DBLink.execute("""
    SELECT event_data 
    FROM user_events
    WHERE userid=?
    AND chatid=?
    AND event_type="joined"
    ORDER BY time DESC
    """, (userid, chatid))
    rows = res.fetchall()
    if not rows:
        return None
    result = [i[0] for i in rows]
    return result


# get join date, most cases is first message
def XX__get_join_date(userid: int, chatid: int) -> Optional[Tuple[float, bool]]:
    res = BotState.DBLink.execute("""
    SELECT time,fake
    FROM join_dates
    WHERE userid=? 
    AND chatid=?
    """, (userid, chatid))
    return res.fetchone()


# #--- {QUOTE STUFF-------------------

# get a list of quotes saved for this user
# replaced with qdb - get_quptes
def XX_get_quotes(userid: int, chatid: int) -> list[str] | None:
    if chatid == 0:
        res = BotState.DBLink.execute("""
            SELECT quote,chatid
            FROM qdb
            WHERE author=?
            """, (userid,))
        rows = res.fetchall()
        if not rows:
            print("no quotes for " + str(userid))
            return None
        return [x[0] for x in rows if x[1] < 0]
    else:
        res = BotState.DBLink.execute("""
    SELECT quote
    FROM qdb
    WHERE author=?
    AND chatid=?
    """, (userid, chatid))
        rows = res.fetchall()
        if not rows:
            print("no quotes for " + str(userid))
            return None
        return [x[0] for x in rows]


# save another user's message as a quote
def XX__save_quote(userid: int, chatid: int, author: int, messageid: int, quote: string) -> int:
    datatuple = (chatid, userid, author, messageid, quote)
    print(datatuple)
    # check if user cites self, currently disaled
    if author == userid and False:
        return 2
    # check if quote has already been saved
    res = BotState.DBLink.execute("""
    SELECT quote
    FROM qdb
    WHERE messageid=?
    """, (messageid,))
    rows = res.fetchall()
    print(rows)
    if rows:
        return 1
    # write the quote
    BotState.DBLink.execute("""
    INSERT INTO qdb
    VALUES(?,?,?,?,?)
    """, datatuple)
    BotState.write()
    return 0


# --- END QUOTE STUFF}----------------


# --- {SUBSCRIPTIONS to PIZDA function-----

# add user to unsubscribed list
def unsubscribe_user(userid: int):
    BotState.DBLink.execute("""
    INSERT INTO unsubscribers 
    VALUES (?)""", (userid,))
    BotState.write()
    return 0


# remove user from unsubscribed list
def resubscribe_user(userid: int):
    BotState.DBLink.execute("""
    DELETE FROM unsubscribers 
    WHERE userid = ?""", (userid,))
    BotState.write()
    return 0


# check if user is on the unsubscribed list
def user_subscribed(userid: int) -> bool:
    res = BotState.DBLink.execute("""
    SELECT userid 
    FROM unsubscribers 
    WHERE userid = ?""", (userid,))
    rows = res.fetchall()
    print(rows)
    if rows:
        print("user" + str(userid) + " unsubscribed")
        return False
    print("user" + str(userid) + " subscribed")
    return True


# --- END SUBSCRIPTIONS to PIZDA function }


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


# --- { SCORE STUFF

# unused

def XXD__score_get_scope_strings(now: datetime = None):
    today = now if now is not None else datetime.now()
    year = today.strftime("%Y")
    yearmonth = today.strftime("%Y-%m")
    yearmonthday = today.strftime("%Y-%m-%d")
    yearweek = today.strftime("%Y-w%W")
    return year, yearmonth, yearweek, yearmonthday

# covered with ScoreHelper

def XX_score_fetch(chatid: int, userid: int, scorename: string, now: datetime = None):
    today = now if now is not None else datetime.now()
    year = today.strftime("%Y")
    yearmonth = today.strftime("%Y-%m")
    yearmonthday = today.strftime("%Y-%m-%d")
    yearweek = today.strftime("%Y-w%W")
    score_all = score_fetch_scope(chatid=chatid, userid=userid, scorename=scorename, scope="all")
    score_year = score_fetch_scope(chatid=chatid, userid=userid, scorename=scorename, scope=year)
    score_month = score_fetch_scope(chatid=chatid, userid=userid, scorename=scorename, scope=yearmonth)
    score_week = score_fetch_scope(chatid=chatid, userid=userid, scorename=scorename, scope=yearweek)
    score_day = score_fetch_scope(chatid=chatid, userid=userid, scorename=scorename, scope=yearmonthday)
    return score_all, score_year, score_month, score_week, score_day

# out of scope, get_top upgrades to using nicknames
# formatting is in scope of consumer

def XX_score_get_scoreboard(chatid: int, scorename: string, heading: string):
    outtext = heading
    scores = score_fetch_top_scope(chatid=chatid, scorename=scorename, count=5)
    for score in scores:
        userid, amount = score
        nicks = get_all_nicks(userid=userid, chatid=chatid)
        print(nicks)
        # firstnick="три длинных хуйя или слова"
        firstnick = nicks.pop(0)
        print(firstnick)
        outtext += "" + MD(firstnick) + "    " + MD(str(amount)) + "\n"
    outtext += "```"
    return outtext

# covered with ScoreHelper

def XX_score_add(chatid: int, userid: int, scorename: string, delta: int, today: float = 0):
    if today == 0:
        today = datetime.now()
    else:
        today = datetime.fromtimestamp(today)
    year = today.strftime("%Y")
    yearmonth = today.strftime("%Y-%m")
    yearmonthday = today.strftime("%Y-%m-%d")
    yearweek = today.strftime("%Y-w%W")
    score_add_scope(chatid=chatid, userid=userid, scorename=scorename, scope="all", delta=delta)
    score_add_scope(chatid=chatid, userid=userid, scorename=scorename, scope=year, delta=delta)
    score_add_scope(chatid=chatid, userid=userid, scorename=scorename, scope=yearmonth, delta=delta)
    score_add_scope(chatid=chatid, userid=userid, scorename=scorename, scope=yearmonthday, delta=delta)
    score_add_scope(chatid=chatid, userid=userid, scorename=scorename, scope=yearweek, delta=delta)

# covered with ScoreHelper

def XX_score_fetch_scope(chatid: int, userid: int, scorename: string, scope: string):
    res = BotState.DBLink.execute("""
    SELECT amount 
    FROM scores 
    WHERE userid = ? 
    AND chatid = ? 
    AND scorename = ? 
    AND scope = ? """, (userid, chatid, scorename, scope))
    row = res.fetchone()
    if row is None:
        return 0
    else:
        return row[0]

# covered with ScoreHelper

def XX_score_fetch_top_scope(chatid: int, scorename: string, count: int = 1, scope: string = "all"):
    res = BotState.DBLink.execute("""
    SELECT userid,amount
    FROM scores
    WHERE chatid = ?
    AND scorename = ?
    AND scope = ?
    ORDER BY amount DESC
    LIMIT ? """, (chatid, scorename, scope, count))
    return res.fetchall()

# covered with ScoreHelper

def XX_score_add_scope(chatid: int, userid: int, scorename: string, scope: string, delta: int):
    data1 = (userid, chatid, scorename, scope)
    data2 = (chatid, userid, scorename, scope, delta)
    # print(data1)
    # print(data2)
    res = BotState.DBLink.execute(
        "SELECT amount FROM scores where userid = ? AND chatid = ? AND scorename = ? AND scope = ? ", data1)
    row = res.fetchone()
    if row is None:
        BotState.DBLink.execute("INSERT INTO scores VALUES (?,?,?,?,?)", data2)
        BotState.write()
    else:
        amount = row[0]
        data3 = (amount + delta, chatid, userid, scorename, scope)
        # print(data3)
        BotState.DBLink.execute("""UPDATE scores
        SET amount = ?
        WHERE chatid = ?
        AND userid = ?
        AND scorename = ?
        AND scope = ?
        """, data3)
        BotState.write()


# --- END SCORE STUFF }
# TODO UTILITY/display
def XUTIL__fmt_timespan(timespan: float) -> str:
    timeunits = ("сек.", "мин.", "ч.", "д.", "мес.")
    index = 0
    output = 0
    if timespan < 60:
        output = timespan
    else:
        timespan /= 60
        index = 1
        if timespan < 60:
            output = timespan
        else:
            timespan /= 60
            index = 2
            if timespan < 24:
                output = timespan
            else:
                timespan /= 24
                index = 3
                if timespan < 30:
                    output = timespan
                else:
                    timespan /= 30.5
                    index = 4
                    return "~ " + str(output.__round__()) + " " + timeunits[index]
    return str(output.__round__()) + " " + timeunits[index]

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
def XCMD__show_all_quotes(userid: int, chatid: int) -> str:
    quotelist = get_quotes(userid=userid, chatid=0)
    quotes = "Ничего нету"
    if quotelist is not None:
        quotes = "\"" + "\"\n\"".join(map(str,quotelist)) + "\""
    return MD(quotes)

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

# replaced with mod_rep in User/Info
# changes a given user's reputation score
def XX_changerep(userid: int, chatid: int, delta: int) -> int:
    res = BotState.DBLink.execute("SELECT rep FROM repuser where userid=? AND chatid=?", (userid, chatid))
    row = res.fetchone()
    # if user has not rep yet, create an entry and change it from 0
    if row is None:
        BotState.DBLink.execute("""INSERT INTO repuser VALUES
        (?, ?, ?, 9)
        """, (chatid, userid, delta))
        BotState.write()
        return delta
    # change user's rep
    else:
        rep = row[0] + delta
        BotState.DBLink.execute("""
        UPDATE repuser
        SET rep = ?
        WHERE userid = ?
        AND chatid= ?
        """, (rep, userid, chatid))
        BotState.write()
        return rep


# changes a given user's reputation score
# deprecated! score "msgcount" covers this
# for legacy counts not matching score may be updated manually
# with a dummy entry - #TODO: migration to scores
def XXD__upcountmessage(userid: int, chatid: int) -> int:
    res = BotState.DBLink.execute("SELECT msg FROM repuser where userid=? AND chatid=?", (userid, chatid))
    row = res.fetchone()
    # if user has not rep yet, create an entry and change it from 0
    if row is None:
        BotState.DBLink.execute("""INSERT INTO repuser VALUES
        (?, ?, 0, 1)
        """, (chatid, userid))
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
        """, (rep, userid, chatid))
        BotState.write()
        return rep


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


def XCMD__handle_bot_cleaner(userid: int, chatid: int, msgid: int):
    can_clean = perm_check(chatid=chatid, userid=userid, perm="cleaner")
    print(str(can_clean))
    kill_message(chatid=chatid, msgid=msgid)
    return MD(random.choice(strings.removeokwords)), 5, 5


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


def XX__console_get_env_scope(env_name:string,scopeid:int) -> str | None:
    results = BotState.DBLink.execute(("""
        SELECT var_value FROM env_vars
        WHERE var_scope = ?
        AND var_name = ?
        """), (scopeid,env_name))
    result = results.fetchone()
    #  print(env_name, scopeid)
    #  print(results)
    #  print(result)
    if result:
        return result[0]
    return None


def console_get_env(env_name:string,chatid: int, option:env_var_option = env_var_option.EFFECTIVE) -> str:
    if option == env_var_option.LOCAL:
        return console_get_env_scope(env_name=env_name,scopeid=chatid)
    if option == env_var_option.GLOBAL:
        return console_get_env_scope(env_name=env_name,scopeid=0)
    if option == env_var_option.EFFECTIVE:
        final = console_get_env_scope(env_name=env_name,scopeid=chatid)
        if not final:
            final = console_get_env_scope(env_name=env_name,scopeid=0)
        return final


def console_set_env(env_name:string,env_value:string,scopeid:int):
    current = console_get_env_scope(env_name=env_name,scopeid=scopeid)
    if current:
        BotState.DBLink.execute(("""
        UPDATE env_vars
        SET var_value = ?
        WHERE var_scope = ?
        AND var_name = ?
        """),(env_value,scopeid,env_name))
        BotState.write()
    else:
        BotState.DBLink.execute(("""
                INSERT INTO env_vars
                VALUES(?,?,?)
                """), (env_name, env_value, scopeid))
        BotState.write()


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

# covere in messagepool - #TODO console hookup
def XX__add_message_to_pool(chatid: int, name:str,pool_id: string, weight: float = 1.0):
    check = BotState.DBLink.execute(("""
    SELECT message_name,weight FROM message_pools
    WHERE pool_id = ?
    AND chatid = ?
    AND message_name = ?
    """),(pool_id,chatid,name))
    exists = check.fetchone()
    if exists:
        return "⛔Error! Message '" + name + "' already in the pool '" + pool_id + "'."
    BotState.DBLink.execute(("""
    INSERT INTO message_pools
    VALUES (?,?,?,?)
    """),(pool_id,chatid,name,weight))
    BotState.write()
    return "✅Success! Message '" + name + "' has been added to the pool '" + pool_id + "'."

# covered in messagepool
async def XX__retrieve_message_from_pool(chatid:int,target_chatid:int,pool_id:str,reply_to_id:int = 0,try_global: bool = True):
    res = BotState.DBLink.execute(("""
    SELECT message_name,weight FROM message_pools
    WHERE pool_id = ?
    AND chatid = ?
    """),(pool_id,chatid))
    rows = res.fetchall()
    print("---fetching from pool---")
    print(rows)

    if not rows:
        if try_global:
            return await retrieve_message_from_pool(chatid=0,target_chatid=target_chatid,pool_id=pool_id,reply_to_id=reply_to_id, try_global=False)
        return
    messages = [row[0] for row in rows]
    weights = [row[1] for row in rows]
    winner = random.choices(population=messages,weights=weights,k=1)
    msgsent = await retrieve_message(name=winner[0],chatid=chatid,target_chatid=target_chatid,reply_to_id=reply_to_id)
    return msgsent

# replaced by write_part


def XX__write_message_component(chatid: int, name: string, component_type: string, data: string, userid: int):
    BotState.DBLink.execute("""
    INSERT INTO saved_messages
    VALUES (?,?,?,?,?,?)
    """, (chatid, name, component_type, data, userid, time.time()))
    BotState.write()


# replaced by read_parts


def XX__get_message_components(chatid: int, name: string):
    res = BotState.DBLink.execute("""
    SELECT type,data FROM saved_messages
    WHERE name = ?
    AND chatid = ?
    """, (name, chatid))
    return res.fetchall()


# replaced by store_messag


async def XX_save_message(name: string, msg: Message, userid: int, chatid: int):
    rows = get_message_components(name=name, chatid=chatid)
    if rows:
        return "Уже есть сообщение с именем \"" + MD(name) + "\"\\!", 5, 10
    if msg.text:
        write_message_component(chatid=chatid, name=name, component_type="text", data=msg.text, userid=userid)
        return "Сообщение \"" + MD(name) + "\" сохранено\\!", 5, 10
    if msg.caption:
        write_message_component(chatid=chatid, name=name,
                                component_type="caption", data=msg.caption, userid=userid)
    if msg.voice:
        write_message_component(chatid=chatid, name=name,
                                component_type="voice", data=msg.voice.file_id, userid=userid)
    if msg.video_note:
        write_message_component(chatid=chatid, name=name,
                                component_type="eblovoice", data=msg.video_note.file_id, userid=userid)
    if msg.audio:
        write_message_component(chatid=chatid, name=name,
                                component_type="music", data=msg.audio.file_id, userid=userid)
    if msg.sticker:
        write_message_component(chatid=chatid, name=name,
                                component_type="sticker", data=msg.sticker.file_id, userid=userid)
    if msg.video:
        write_message_component(chatid=chatid, name=name,
                                component_type="video", data=msg.video.file_id, userid=userid)
    if msg.document:
        write_message_component(chatid=chatid, name=name,
                                component_type="file", data=msg.document.file_id, userid=userid)
    if msg.photo:
        if msg.media_group_id:
            album = (await BotState.pyroclient.get_media_group(chat_id=chatid, message_id=msg.id))
            print_to_string(album)
            for photomsg in album:

                write_message_component(chatid=chatid, name=name,
                                        component_type="image", data=photomsg.photo.file_id,
                                        userid=userid)
        else:
            write_message_component(chatid=chatid, name=name,
                                    component_type="image", data=msg.photo[-1].file_id, userid=userid)

    return "Сообщение \"" + MD(name) + "\" сохранено\\!", 5, 10

# replaced by replay_message in MessageStore

async def XX_retrieve_message(name: string, chatid: int,  do_global: bool = False, target_chatid: int = 0,reply_to_id:int = 0):
    """
    Retrieves and replays an earlier saved message.
    @param name: Unique name string identifying the saved message.
    @param chatid: Chat that saved the message (0 for global)
    @param do_global: If True, the function won't attempt a fallback check in the global scope.
    @param target_chatid: if set, will post the message to that chat instead
    @param reply_to_id: if set and non-zero, will reply to that message.
    @return: List of message IDs played.
    """
    if target_chatid == 0:
        destination_chatid = chatid
    else:
        destination_chatid = target_chatid
    rows = get_message_components(name=name, chatid=0 if do_global else chatid)
    if rows:
        photos = []
        caption = ""
        fileid = ""
        filetype = ""
        text = ""
        for row in rows:
            filetype = row[0]
            match filetype:
                case "text":
                    text = row[1]
                case "caption":
                    caption = row[1]
                case "image":
                    photos.append(row[1])
                case _:
                    fileid = row[1]
        if text:
            msgsent = (await BotState.bot.send_message(chat_id=destination_chatid, text=text,reply_to_message_id=reply_to_id))
            return [msgsent.id]
        if photos:
            medialist = []
            for photoid in photos:
                medialist.append(InputMediaPhoto(media=photoid))
            messages = await BotState.bot.send_media_group(chat_id=destination_chatid, media=medialist,reply_to_message_id=reply_to_id)
            return [message.id for message in messages]
        print(filetype + " = " + fileid)
        match filetype:
            case "voice":
                msgsent = (await BotState.bot.send_voice(chat_id=destination_chatid, voice=fileid,reply_to_message_id=reply_to_id))
            case "eblovoice":
                msgsent = (await BotState.bot.send_video_note(chat_id=destination_chatid, video_note=fileid,reply_to_message_id=reply_to_id))
            case "video":
                msgsent = (await BotState.bot.send_video(chat_id=destination_chatid, video=fileid, caption=caption,reply_to_message_id=reply_to_id))
            case "music":
                msgsent = (await BotState.bot.send_audio(chat_id=destination_chatid, audio=fileid, caption=caption,reply_to_message_id=reply_to_id))
            case "sticker":
                msgsent = (await BotState.bot.send_sticker(chat_id=destination_chatid, sticker=fileid,reply_to_message_id=reply_to_id))
            case "file":
                msgsent = (await BotState.bot.send_document(chat_id=destination_chatid, document=fileid,reply_to_message_id=reply_to_id))
            case _:
                return []
                pass
        return [msgsent.id]
        pass
    # if nothing found for this chat, look thru globals
    # if already looking thru globals, give up
    else:
        if do_global:
            await BotState.bot.send_message(chat_id=destination_chatid, text="404")
        else:
            await retrieve_message(name=name, chatid=chatid, do_global=True, target_chatid=target_chatid)


# QUIZ STUFF: SESSIONS
def check_edit_session(userid: int, name: string):
    res = BotState.DBLink.execute("""
    SELECT session_name,userid FROM edit_sessions
    WHERE session_name = ?
    AND userid = ?
    """, (name, userid))
    return len(res.fetchall()) > 0


def find_edit_sessions(userid: int):
    res = BotState.DBLink.execute("""
    SELECT session_name FROM edit_sessions
    WHERE userid = ?
    """, (userid,))
    rows = res.fetchall()
    if not rows:
        return None
    result = [i[0] for i in rows]
    return result


def end_edit_session(userid: int, name: string):
    BotState.DBLink.execute("""
    DELETE FROM edit_sessions
    WHERE session_name = ?
    AND userid = ?
    """, (name, userid))
    BotState.write()


def begin_edit_session(userid: int, name: string):
    BotState.DBLink.execute("""
    INSERT INTO edit_sessions
    VALUES (?,?)
    """, (name, userid))
    BotState.write()


# QUIZ STUFF:QUIZZES

def XX__create_quiz(userid: int, quizid: string):
    BotState.DBLink.execute("""
    INSERT INTO quizzes
    VALUES (?,?,?,?,?)
    """, (userid, time.time(), "(Без названия)", 45, quizid))
    BotState.write()


# len(quiz.questions)
def XX__quiz_count_questions(quizid: string):
    res = BotState.DBLink.execute("""
    SELECT ordinal
    FROM quiz_questions
    WHERE quiz_name = ?
    """, (quizid,))
    rows = res.fetchall()
    if not rows:
        return 0
    return len(rows)


# quiz.init
def XX__quiz_get_info(quizid: string):
    """

    @param quizid: the specific quiz to retrieve info from
    @return: A tuple of (owner's userID, creation timestamp, visible title, question timer, question count)
    """
    count = quiz_count_questions(quizid=quizid)
    res = BotState.DBLink.execute("""
    SELECT ownerid,created,title,question_time
    FROM quizzes
    WHERE name = ?
    """, (quizid,))
    row = res.fetchone()
    if not row:
        return None
    return row[0], row[1], row[2], row[3], count


# quiz.question.init
def XX__quiz_get_question(quizid: string, ordinal: int):
    """

    @param quizid: the quiz containing the question
    @param ordinal: question number, 0-based
    @return: a tuple of (question, options separated with |, correct option number (0-based), ID of attached media if any)
    """
    res = BotState.DBLink.execute("""
    SELECT question,options,correct_option,extraid
    FROM quiz_questions
    WHERE quiz_name = ?
    AND ordinal = ?""", (quizid, ordinal))
    row = res.fetchone()
    if not row:
        return "c", "a|b", 0, "0:0"
    return row[0], row[1], row[2], row[3]


# quiz.questions contains
def XX__quiz_get_all_questions(quizid: string):
    info = quiz_get_info(quizid=quizid)
    count = info[4]
    questions = []
    for i in range(count):
        question = quiz_get_question(quizid=quizid, ordinal=i)
        questions.append(question)
    return questions


# quiz.add_question
def XX__quiz_add_question(quizname: string, question: string, answers: list[string], correct: int):
    ordinal = quiz_count_questions(quizid=quizname)
    BotState.DBLink.execute("""
    INSERT INTO quiz_questions
    VALUES (?,?,?,?,?,?)
    """, (quizname, question, ordinal, "|".join(answers), correct, ""))
    BotState.write()


# question.attach_media
def XX__quiz_attach_media(quizname: string, question_id:int,media_id: string):
    BotState.DBLink.execute("""
    UPDATE quiz_questions
    SET extraid = ?
    WHERE quiz_name = ?
    AND ordinal = ?""",(media_id,quizname,question_id))
    BotState.write()


# quiz.rename
def XX__quiz_rename(quizid: string, newname: string):
    BotState.DBLink.execute("""
        UPDATE quizzes
        SET title = ?
        WHERE name = ?""", (newname, quizid))
    BotState.write()


# quiz.set_time
def XX__quiz_set_time(quizid: string, newtime: int):
    BotState.DBLink.execute("""
        UPDATE quizzes
        SET question_time = ?
        WHERE name = ?""", (newtime, quizid))
    BotState.write()


# session.award_correct_answer
def XX__quiz_add_score(sessionid: string, quizid: string, userid: int, seconds: float):
    res = BotState.DBLink.execute("""
    SELECT quiz_session_id,quiz_name,userid,seconds,answers
    FROM quiz_scores
    WHERE quiz_session_id = ?
    AND quiz_name = ?
    AND userid = ?""", (sessionid, quizid, userid))
    row = res.fetchone()
    if row:
        secs = row[3] + seconds
        score = row[4] + 1
        BotState.DBLink.execute("""
        UPDATE quiz_scores
        SET seconds = ?,answers = ?
        WHERE quiz_session_id = ?
        AND quiz_name = ?
        AND userid = ?""", (secs, score, sessionid, quizid, userid))
        BotState.write()
        print((secs, score, sessionid, quizid, userid))
    else:
        BotState.DBLink.execute("""
        INSERT INTO quiz_scores
        VALUES (?,?,?,?,?)""", (sessionid, quizid, userid, seconds, 1,))
        BotState.write()
        print((sessionid, quizid, userid, seconds, 1,))


# session.submit_answer
def XX__quiz_verify_answer(poll: int, user: int, answer: int):
    now = time.time()
    res = BotState.DBLink.execute("""
    SELECT quiz_session_id,pollid,quiz_name,ordinal,time,msgid
    FROM quiz_replytracker
    WHERE pollid = ?""", (str(poll),))
    row = res.fetchone()
    if not row:
        print("pollid " + str(poll) + " isn't in the list")
        return
    session = row[0]
    question, options, correct, extra = quiz_get_question(quizid=row[2], ordinal=row[3])
    if correct == answer:
        diff = now - row[4]
        print("correct answer given in " + str(diff) + " sec")
        quiz_add_score(sessionid=session, quizid=row[2], userid=user, seconds=diff)
    else:
        print("Incorrect answer given.")
    if session[0] != "-":
        next_ordinal = row[3]+1
        owner, created, quizname, timer, count = quiz_get_info(quizid=row[2])
        if next_ordinal >= count:
            next_ordinal = -3
        chatid, startmsg = quiz_get_session(session)
        schedule_kill(chatid=chatid,msgid=row[5],expiration=0)
        BotState.DBLink.execute(("""
        UPDATE quiz_next
        SET time = 0
        WHERE quiz_session_id = ?
        AND ordinal = ?
        """),(session,next_ordinal))
        BotState.write()


# session.write_plan
def XX__quiz_write_plan(session_id: string, chatid: int, quizid: string):
    now = time.time()
    plan = []

    # 2 message edits first:
    now += 3
    plan.append((session_id, chatid, now, quizid, -2))
    now += 3
    plan.append((session_id, chatid, now, quizid, -1))
    now += 3
    owner, created, quizname, timer, count = quiz_get_info(quizid=quizid)

    if count == 1:
        plan.append((session_id, chatid, now, quizid, 0))
        now += float(timer)
    else:
        print("qcount = " + str(count))
        for ordinal in range(count):
            print("adding q" + str(ordinal))
            plan.append((session_id, chatid, now, quizid, ordinal))
            now += float(timer)
    plan.append((session_id, chatid, now, quizid, -3))

    for entry in plan:
        BotState.DBLink.execute("""
        INSERT INTO quiz_next
        VALUES (?,?,?,?,?)""", entry)
    BotState.write()


# session.start
def XX__quiz_session_start(session_id: string, chatid: int, startid: int):
    BotState.DBLink.execute("""
    INSERT INTO quiz_sessions
    VALUES (?,?,?,0)""", (session_id, chatid, startid))
    BotState.write()


# session.end
def XX__quiz_session_end(session_id: string):
    BotState.DBLink.execute("""
    UPDATE quiz_sessions
    SET ended = ?
    WHERE quiz_session_id = ?""", (1, session_id))
    res = BotState.DBLink.execute(("""
    SELECT chatid,start_message_id
    FROM quiz_sessions
    WHERE quiz_session_id = ?"""),(session_id,))
    row = res.fetchone()
    if row:
        schedule_kill(chatid=row[0],msgid=row[1],expiration=time.time())
    BotState.write()


# session.check_ongoing
def XX__quiz_session_check(chatid: int):
    res = BotState.DBLink.execute("""
    SELECT ended
    FROM quiz_sessions
    WHERE chatid = ?
    AND ended = ?""", (chatid, 0))
    rows = res.fetchall()
    if rows:
        return True
    return False


# will be ported to sequences
async def XXSEQ__quiz_start(chatid: int, context: ContextTypes.DEFAULT_TYPE, quizid: string):
    ongoing = quiz_session_check(chatid=chatid)
    failmsg = """Unable to start.
Already a quiz going!! finish it first."""
    if ongoing:
        await context.bot.send_message(chat_id=chatid, text=failmsg, parse_mode='Markdown')
        return
    now = time.time()
    owner, created, quizname, timer, count = quiz_get_info(quizid=quizid)
    quizname = MD(quizname,1)
    startmessage = """Викторина начинается!!11
*{quizname}*
_{count}_ вопросов.
На каждый вопрос дано _{timer}_ секунд.
                🔴⚫⚫"""
    startmessage = startmessage.format(quizname=quizname, count=count, timer=timer)
    msgid = await context.bot.send_message(chat_id=chatid, text=startmessage, parse_mode='Markdown')
    startid = msgid.message_id
    session_id = str(chatid) + quizid + str(now)
    quiz_session_start(session_id=session_id, chatid=chatid, startid=startid)
    quiz_write_plan(session_id=session_id, chatid=chatid, quizid=quizid)

# will be ported to sequences
async def XXSEQ__quiz_post_poll(chatid: int, session_id: string, quizid: string, ordinal: int):
    questiondata = quiz_get_question(quizid=quizid, ordinal=ordinal)
    quizdata = quiz_get_info(quizid=quizid)
    good_answer = questiondata[2]
    answers = questiondata[1].split("|")
    fake_answer = random.randint(0, len(answers)-1)
    if fake_answer >= int(good_answer):
        fake_answer += 1

    quizcount = quizdata[4]
    timer = quizdata[3]
    question = questiondata[0]
    correct = fake_answer if BotState.prize_mode else good_answer
    media_id = questiondata[3]
    print(questiondata)
    if media_id:
        medias = (await retrieve_message(chatid=quizdata[0],name=media_id,target_chatid=chatid))
        if medias:
            for media in medias:
                schedule_kill(chatid=chatid,msgid=media,expiration=time.time() + timer)
    pollupdate = (await BotState.bot.send_poll(
        chatid,
        "[" + str(ordinal+1) + "/" + str(quizcount) + "] " + question,
        answers,
        type=Poll.QUIZ,
        is_anonymous=False,
        correct_option_id=correct,
        open_period=timer))
    pollid = pollupdate.poll.id
    pollmsg = pollupdate.id
    schedule_kill(chatid=chatid, msgid=pollmsg, expiration=time.time() + timer)
    BotState.DBLink.execute("""
    INSERT INTO quiz_replytracker
    VALUES (?,?,?,?,?,?)""", (session_id, pollid, quizid, ordinal, time.time(),pollmsg))
    BotState.write()


# unused?
def XX__quiz_cleanup_session(session_id: string):
    quiz_session_end(session_id=session_id)

# quiz.find_by_owner
def XX__quiz_get_all(userid: int):
    res = BotState.DBLink.execute("""
    SELECT title,name
    FROM quizzes
    WHERE ownerid = ?
    """, (userid,))
    rows = res.fetchall()
    if not rows:
        return []
    quizzes = []
    for row in rows:
        name, qid = row
        count = quiz_get_info(quizid=qid)[4]
        quizzes.append((name, count, qid))
    return quizzes


# session.load
def XX__quiz_get_session(session_id: string):
    res = BotState.DBLink.execute("""
    SELECT chatid,start_message_id
    FROM quiz_sessions
    WHERE quiz_session_id = ?""", (session_id,))
    row = res.fetchone()
    if row:
        return row[0], row[1]
    return 0, 0


# session.get_results
def XX__quiz_get_results(session_id: string):
    res = BotState.DBLink.execute("""
    SELECT userid,seconds,answers,quiz_name
    FROM quiz_scores
    WHERE quiz_session_id = ?
    ORDER BY answers DESC,seconds""", (session_id,))
    rows = res.fetchall()
    return rows


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

# session.give_awards
def XX__quiz_award_medals(session, chatid):
    results = quiz_get_results(session)
    winnertable = []
    medalcounter = 0
    for result in results:
        uid, timing, score, qid = result
        timestring = session.removeprefix(str(chatid))
        timestring = timestring.removeprefix(str(qid))
        today = float(timestring)
        if medalcounter < 3:
            pass
        else:
            score_add(chatid=chatid, userid=uid, scorename="quiz_medals_other", delta=1,today=today)
        usernick = get_newest_nick(userid=uid, chatid=chatid)
        score_add(chatid=chatid, userid=uid, scorename="quiz_medals_" + str(medalcounter), delta=1,today=today)
        score_add(chatid=chatid, userid=uid, scorename="quiz_participations", delta=1,today=today)
        if not usernick:
            usernick = "MissingNo.&%!▮"
        if len(usernick) > 15:
            usernick = "{:.12}...".format(usernick)
        usernick = MD(usernick, 1)
        winnertable.append((medalcounter,usernick, str(score),str(round(timing,1))))
        medalcounter += 1
    return winnertable


# fmt_string should take care of most of this
def XXSEQ__quiz_format_winners(resultsdata, quizname,quizid):
    medals = ["🥇", "🥈", "🥉"]
    msgtpl = """🏁Конец!🏁
    *{qname}*
    Победители и прочие участники:
    """.format(qname=quizname)
    for winner in resultsdata:
        medal,usernick,score,playtime = winner
        if medal < 3:
            medal = medals[medal]
        else:
            medal = ""
        resultrow = medal + "*" + usernick + "*: _" + score + "_ правильных за _" + playtime + "_ секунд.\n"
        msgtpl += resultrow
    msgtpl += "\nПройти в личке? пеши \"викторина запустить " + quizid + "\" боту (без кавычек!!!11)"
    return msgtpl


# done with sequence events
async def XXSEQ__quiz_tick():
    now = time.time()
    res = BotState.DBLink.execute("""
    SELECT quiz_session_id,chatid,time,quiz_name,ordinal
    FROM quiz_next
    WHERE time < ?""", (now,))
    rows = res.fetchall()

    if not rows:
        return
    for row in rows:
        session, chatid, scheduled, quizid, command = row
        chatid, startmsg = quiz_get_session(session_id=session)
        owner, created, quizname, timer, count = quiz_get_info(quizid=quizid)
        quizname = MD(quizname, 1)
        match command:
            case -3:
                winners = quiz_award_medals(session,chatid)
                msgtpl = quiz_format_winners(winners,quizname,quizid)

                await BotState.bot.send_message(chat_id=chatid, text=msgtpl, parse_mode='Markdown')
            case -2:
                startmessage = """Викторина начинается!!11
*{quizname}*
_{count}_ вопросов.
На каждый вопрос дано _{timer}_ секунд.
                🔴🟡⚫"""
                startmessage = startmessage.format(quizname=quizname, count=count, timer=timer)
                await BotState.bot.edit_message_text(chat_id=chatid, message_id=startmsg, text=startmessage,
                                                     parse_mode="Markdown")
            case -1:
                startmessage = """Викторина начинается!!11
*{quizname}*
_{count}_ вопросов.
На каждый вопрос дано _{timer}_ секунд.
                🟢🟢🟢"""
                startmessage = startmessage.format(quizname=quizname, count=count, timer=timer)
                await BotState.bot.edit_message_text(chat_id=chatid, message_id=startmsg, text=startmessage,
                                                     parse_mode="Markdown")
            case _:
                # do actual questions
                print("question #" + str(command))
                await quiz_post_poll(chatid=chatid, session_id=session, quizid=quizid, ordinal=command)
    BotState.DBLink.execute("""
    DELETE
    FROM quiz_next
    WHERE time < ?""", (now,))
