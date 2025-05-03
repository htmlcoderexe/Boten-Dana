import os
import random
import string
import sys
import time
from datetime import datetime
# from turtle import update
from typing import Optional, Tuple, Any

import telegram.helpers
from pyrogram import Client
from telegram import Poll, Update, ChatMember, ChatMemberUpdated, Message
from telegram.ext import CallbackContext
from telegram.ext import filters, PollAnswerHandler, PollHandler, MessageHandler, ApplicationBuilder, CommandHandler, \
    ContextTypes, MessageReactionHandler, ChatMemberHandler

import UserInfo
import actions
import userlists
import quizstuff
import messagestore
import messagetagger
import QDB
import antimat
import botconfig
import scores
from botstate import BotState
import changelogs
import datastuff
import strings
from botutils import MD, S, md_safe_int, print_to_string
# import botstartup
import console_commands


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


# #regular messages

# #handle a message that's a reply to the bot

def handle_backtalk(userid: int, chatid: int, botmsg: string, usermsg: string, msgid: int ):
    is_pizda_reply=datastuff.check_if_pizda_reply(chatid=chatid,msgid=msgid) and BotState.talk
    if is_pizda_reply > 0:
        if usermsg in strings.pizdaresponses.keys():
            return random.choice(strings.pizdaresponses[usermsg]), -1, -1
        mat_score = 0
        words = usermsg.split()
        for word in words:
            if word in strings.badwords1:
                mat_score += 1

        if (mat_score > 1) and (is_pizda_reply == userid):
            datastuff.unsubscribe_user(userid)
            return random.choice(strings.nomorepizda), -1, -1
        return random.choice(strings.pizdaresponses["default"]), -1, -1


async def deal_with_quiz_stuff(upd: Update, context: ContextTypes.DEFAULT_TYPE, commands: list[string],
                               fulltail: string):
    userid = upd.message.from_user.id
    chatid = upd.effective_chat.id

    command = commands[1]
    trail2 = ' '.join(commands[2:])
    print("quiz stuff.")

    sessions = datastuff.find_edit_sessions(userid)
    added = False
    editing = False
    sesstype, params = "",""
    if sessions:
        for session in sessions:
            sesstype, params = session.split(" ", 1)
            if sesstype == "quiz_edit":
                editing = True
    match command:
        case "призовой":
            if trail2 == "выкл":
                BotState.prize_mode = False
                await context.bot.send_message(chat_id=chatid, text="Правильный ответ теперь будет отображаться.", parse_mode='Markdown',
                                               reply_to_message_id=upd.message.id)
            if trail2 == "вкл":
                BotState.prize_mode = True
                await context.bot.send_message(chat_id=chatid, text="Правильный ответ теперь будет спрятан.", parse_mode='Markdown',
                                               reply_to_message_id=upd.message.id)
        case "показать": # POSSIBLE with current
            if editing:
                questions = datastuff.quiz_get_all_questions(quizid=params)
                info = datastuff.quiz_get_info(quizid=params)
                msgbox = "*" + info[2] + "*, _" + str(info[3]) + "_ секунд.\n"
                for question in questions:
                    qline = (question[0][:30] + '...') if len(question[0]) > 33 else question[0]
                    msgbox += qline + "\n"
                await context.bot.send_message(chat_id=chatid, text=msgbox, parse_mode='Markdown',
                                               reply_to_message_id=upd.message.id)
            else:
                msgbox = "а не знаю чё показывать, команда \"*викторина редактировать* _ID викторины_\" в помощь"
                await context.bot.send_message(chat_id=chatid, text=msgbox, parse_mode='Markdown',
                                               reply_to_message_id=upd.message.id)
        case "редактировать": # --------- SEQUENCE ADDED ACTION ADDED
            if editing:
                await context.bot.send_message(chat_id=chatid,
                                               text="Уже редактируется quiz \"{0}\", сначала завершите работу: `викторина завершить`".format(
                                                params),
                                               parse_mode='Markdown', reply_to_message_id=upd.message.id)
            else:
                quiz_exists = datastuff.quiz_get_info(trail2)

                if quiz_exists:
                    owner_id = quiz_exists[0]
                    if userid == owner_id:
                        datastuff.begin_edit_session(userid=userid, name="quiz_edit " + trail2)
                        await context.bot.send_message(chat_id=chatid,
                                                       text="Редактирования mode quiz \"" + trail2 + "\" был begins!!",
                                                       parse_mode='Markdown', reply_to_message_id=upd.message.id)
                    else:
                        await context.bot.send_message(chat_id=chatid, text="куда лезешь, сучара?!",
                                                       parse_mode='Markdown',
                                                       reply_to_message_id=upd.message.id)
                else:
                    await context.bot.send_message(chat_id=chatid, text="НЕТУ ТАКОЙ!!11один", parse_mode='Markdown',
                                                   reply_to_message_id=upd.message.id)

        case "создать": # ---------------- ACTION ADDED
            datastuff.create_quiz(userid=userid, quizid=trail2)
            datastuff.begin_edit_session(userid=userid, name="quiz_edit " + trail2)
            await context.bot.send_message(chat_id=chatid, text="quiz \"" + trail2 + "\" был created!!",
                                           parse_mode='Markdown', reply_to_message_id=upd.message.id)
        case "назвать": # --------- ACTION ADDED
            if commands[2]:
                if editing:
                    datastuff.quiz_rename(quizid=params, newname=fulltail)
                    await context.bot.send_message(chat_id=chatid,
                                                   text="викторина теперь называется\"{name}\"".format(
                                                    name=fulltail), parse_mode='Markdown',
                                                   reply_to_message_id=upd.message.id)
                else:
                    await context.bot.send_message(chat_id=chatid,
                                                   text="непонятно, что требуется переименовать. Нужно начать редактировать викторину (команда \"*викторина редактировать* _ID викторины_\", список ID можно посмотреть через \"*викторина список*\"",
                                                   parse_mode='Markdown', reply_to_message_id=upd.message.id)
        case "время":
            if commands[2]:
                if editing:
                    datastuff.quiz_set_time(quizid=params, newtime=int(commands[2]))
                    await context.bot.send_message(chat_id=chatid,
                                                   text="вопросы теперь держатся \"{name} секунд\"".format(
                                                    name=str(int(commands[2]))), parse_mode='Markdown',
                                                   reply_to_message_id=upd.message.id)
                else:
                    await context.bot.send_message(chat_id=chatid,
                                                   text="используйте команду \"*викторина редактировать* _ID викторины_\", список ID можно посмотреть через \"*викторина список*\"",
                                                   parse_mode='Markdown', reply_to_message_id=upd.message.id)
        case "прикрепить":
            if editing:
                if upd.message.reply_to_message:
                    question_id = datastuff.quiz_count_questions(params) - 1
                    if commands[2]:
                        if int(commands[2])-1<=question_id:
                            question_id = int(commands[2])-1
                        else:
                            question_id = -1
                            await context.bot.send_message(chat_id=chatid,
                                                           text="вопроса с номером _ \"{name}_ ещё нет.\"".format(
                                                               name=str(int(commands[2]))), parse_mode='Markdown',
                                                           reply_to_message_id=upd.message.id)
                    msgname = str(userid) + "_" + str(params) + "_" + str(question_id) + str(time.time())
                    if question_id > -1:
                        await datastuff.save_message(msg=upd.message.reply_to_message,userid=userid,chatid=userid,name=msgname)
                        datastuff.quiz_attach_media(quizname=params,question_id=question_id,media_id=msgname)
                        await context.bot.send_message(chat_id=chatid,
                                                       text="я прикрипила", parse_mode='Markdown',
                                                       reply_to_message_id=upd.message.id)
            else:
                await context.bot.send_message(chat_id=chatid,
                                               text="ты хуй, куда я это прикреплять буду :(", parse_mode='Markdown',
                                               reply_to_message_id=upd.message.id)
        case "добавить": # ------ACTION ADDED
            print("add quiz?")
            if upd.message.reply_to_message and upd.message.reply_to_message.poll:
                poll = upd.message.reply_to_message.poll
                print(poll)

                options = [o['text'] for o in poll.options]
                question = poll.question
                if commands[2]:
                    correctopt = int(commands[2]) - 1
                    if editing:
                        datastuff.quiz_add_question(quizname=params, answers=options, correct=correctopt,
                                                    question=question)
                        await context.bot.send_message(chat_id=chatid, text="вопрос добавлен!!1",
                                                       parse_mode='Markdown',
                                                       reply_to_message_id=upd.message.id)
                    else:
                        await context.bot.send_message(chat_id=chatid,
                                                       text="не понятно, куда это пихать. Нужно начать редактировать викторину (команда \"*викторина редактировать* _ID викторины_\", список ID можно посмотреть через \"*викторина список*\"",
                                                       parse_mode='Markdown', reply_to_message_id=upd.message.id)
        case "запустить":
            print("starting quiz")
            await datastuff.quiz_start(chatid=chatid, context=context, quizid=trail2)
        case "завершить": # ---------- ACTION ADDED
            sessions = datastuff.find_edit_sessions(userid)
            for session in sessions:
                sesstype, params = session.split(" ", 1)
                if sesstype == "quiz_edit":
                    await context.bot.send_message(chat_id=chatid, text="Работа над \"" + params + "\" завершена!!",
                                                   parse_mode='Markdown', reply_to_message_id=upd.message.id)
                    datastuff.end_edit_session(userid=userid, name=session)
            print("ending edit")
        case "помощь":
            print("help requested")
            manualmsg = """*Инструкция пользования ботом*
`викторина создать` _ID_
Создаёт викторину с ID <ID>. По ID викторина сохраняется в боте, и по нему её можно запустить или отредактировать. <ID> может содержать несколько слов. Создание викторины автоматически запускает режим редактирования.

`викторина редактировать` _ID_
Включает режим редактирования викторины с ID <ID>.

`викторина завершить`
Завершает режим редактирования.

`викторина список`
Выдаёт список всех викторин, созданных пользователем. _ID для редактирования_ *не включает* кавычки.

`викторина показать`
Выдаёт список всех вопросов в викторине. _ID для редактирования_ *не включает* кавычки.

`викторина добавить` _№_
Добавляет вопрос в викторину, <№> указывает номер правильного ответа. Должно быть ответом на телеграм-опрос, созданный со следующими настройками: режим викторины вкл., анонимные ответы откл., несколько ответов откл.. Правильный ответ, выставленный в самом опросе, ботом игнорируется.
Доступно только в режиме редактирования.

`викторина прикрепить`

`викторина прикрепить` _№_
Прикрепляет медиа/сообщение к вопросу <№>. Если не указать номер, прикрепляет к последнему вопросу в текущей викторине. Должно быть ответом на другое сообщение, содержащее медиа.
Использует ту же технологию, как и сохранение сообщениё в чате, как следствие имеет те же ограничения:
- Некорректно выводится описание, особенно у альбомов
- Поддерживаются не все типы сообщений, только следующие:
- Войс
- Картинка (одна)
- Картинки (альбом)
- Музыка
- Видео/гифка
- Ебловойс (кружок)
- Стикер
При применении к вопросу, у которого уже имеется прикрепление, заменяет его новым.
Доступно только в режиме редактирования.

`викторина назвать` _название_
Меняет название текущей викторины.
Доступно только в режиме редактирования.

`викторина время` _кол-во секунд_
Меняет время, отданное на каждый вопрос в викторине - по умолчанию 45 секунд.
Доступно только в режиме редактирования.

`викторина запустить` _ID_
Запускает викторину с ID <ID>. Должно быть использовано там, где требуется запустить викторину (это включает личные сообщения с ботом).
"""
            await context.bot.send_message(chat_id=chatid, text=manualmsg, parse_mode='Markdown',
                                           reply_to_message_id=upd.message.id)
        case "список":
            print("listing quizzes by user")
            quizzes = datastuff.quiz_get_all(userid=userid)
            lines = ""
            tpline = "*{quizname}* - _{count}_ вопросов -  \"{qid}\"\n"
            for quiz in quizzes:
                name, count, qid = quiz
                lines += tpline.format(quizname=name, count=count, qid=qid)
            await context.bot.send_message(chat_id=chatid, text=lines, parse_mode='Markdown',
                                           reply_to_message_id=upd.message.id)
    print("quiz stuff end.")


# def handle_reply_to_non_text(upd: Update, context: ContextTypes.DEFAULT_TYPE):
#    userid = user.id
#    chatid = upd.effective_chat.id
#    botreply = False
#    replied = upd.message.reply_to_message
#   current = upd.message

async def do_console_command(command: string, args,chatid: int, messageid: int,prev:int,userid:int):
    output ="Unrecognised command: "+command+"."
    pargs = console_commands.parse_args(args)
    match command:
        case "info":
            output = await console_commands.bot_info(pargs)
        case "exit":
            datastuff.console_end_session(chatid=chatid,userid=userid,messageid=prev)
            datastuff.schedule_kill(chatid=chatid,msgid=messageid,expiration=0)
            return
        case "get":
            output = await console_commands.get_env(pargs,chatid)
        case "getx":
            output = await console_commands.get_envx(pargs)
        case "set":
            output = await console_commands.set_env(pargs,chatid)
        case "setx":
            output = await console_commands.set_envx(pargs)
        case "pool-add":
            output = await console_commands.pool_add(pargs,chatid)
        case "pool-capture-begin":
            output = await console_commands.pool_capture_start(pargs,userid,chatid)
        case "pool-capture-end":
            output = await console_commands.pool_capture_end(pargs,userid,chatid)
    output ="<pre>\nUser#&gt; "+command+" "+args+"\nDanaBot#&gt; "+output+"\n</pre>"
    await datastuff.console_spawn(chatid=chatid,userid=userid,source=messageid,text=output,previous=prev)
    pass


async def do_console_command_direct(command: string, args,chatid: int, userid:int):
    output ="Unrecognised command: "+command+"."
    pargs = console_commands.parse_args(args)
    match command:
        case "info":
            output = await console_commands.bot_info(pargs)
        case "get":
            output = await console_commands.get_env(pargs,chatid)
        case "getx":
            output = await console_commands.get_envx(pargs)
        case "set":
            output = await console_commands.set_env(pargs,chatid)
        case "setx":
            output = await console_commands.set_envx(pargs)
    output ="<pre>\nUser#&gt; "+command+" "+args+"\nDanaBot#&gt; "+output+"\n</pre>"
    pass


async def console_capture_message(userid: int, chatid: int, msg: Message):
    capture = datastuff.console_find_capture(userid=userid, chatid=chatid)
    if not capture:
        return False
    mode, context, commandline = capture
    commandline_split = commandline.split()
    command = commandline_split[0]
    args = " ".join(commandline_split[1:])
    match mode:
        case "full":
            msgname = str(chatid)+" " + str(userid) + " " + context + " " + str(msg.id)
            await datastuff.save_message(name=msgname,msg=msg,userid=userid,chatid=chatid)
            args = args + " \"" + msgname + "\""
            prev, mode = datastuff.console_find_latest_session(chatid=chatid,userid=userid)
            await do_console_command(command=command,args=args,chatid=chatid,userid=userid,messageid=0,prev=prev)
        case "full-glob":
            msgname = str(chatid)+" " + str(userid) + " " + context + " " + str(msg.id)
            await datastuff.save_message(name=msgname,msg=msg,userid=userid,chatid=0)
            args = args + " \"" + msgname + "\""
            prev, mode = datastuff.console_find_latest_session(chatid=chatid,userid=userid)
            await do_console_command(command=command,args=args,chatid=chatid,userid=userid,messageid=0,prev=prev)


# #handle a message that's a reply to something
async def handle_with_reply(upd: Update, context: ContextTypes.DEFAULT_TYPE):
    mereply = False
    botreply = False
    replied = upd.message.reply_to_message
    current = upd.message
    user = replied.from_user
    usertag = MD(user.full_name)
    userid = user.id
    thisuid = upd.message.from_user.id
    rmsgid=replied.id
    if user.is_bot:
        botreply = True

    if user.id == BotState.botuid:
        mereply = True
    chatid = upd.effective_chat.id
    output = ""
    stext = ""
    fulltail = ""
    raw = ""
    sourcemessage = ""
    if current.text:
        stext = S(current.text.lower())
        rawlistext = current.text.split()
        fulltail = " ".join(rawlistext[2:])
        halftail = " ".join(rawlistext[1:])
        raw = current.text.strip()
    if replied.text:
        sourcemessage = S(replied.text.lower())
    listext = stext.split()
    if mereply and datastuff.console_check_session(chatid=chatid,userid=thisuid,messageid=replied.id):
        await do_console_command(command=listext[0],args=halftail,chatid=chatid,messageid=current.id,prev=replied.id,userid=thisuid)
        return
    if stext in strings.removewords:
        if botreply:
            datastuff.score_add(chatid=chatid, userid=thisuid, scorename="cleaner", delta=1)
            return datastuff.handle_bot_cleaner(userid=thisuid, chatid=chatid, msgid=replied.message_id)
        datastuff.score_add(chatid=chatid, userid=thisuid, scorename="cleaner-human", delta=1)
        return MD(random.choice(strings.cantremovewords)), -1, -1
    repgainstring = [
        " [{usertag}](tg://user?id={userid}) получает плюс и теперь имеет {userrep} совершенно бесполезных очков",
        " [{usertag}](tg://user?id={userid}) получает плюс и теперь имеет {userrep} совершенно бесполезных очков",
        " [{usertag}](tg://user?id={userid}) получает плюс и теперь имеет {userrep} совершенно бесполезных очков",
        " [{usertag}](tg://user?id={userid}) получает плюс и теперь имеет {userrep} совершенно бесполезных очков",
        " [{usertag}](tg://user?id={userid}) получает плюс и теперь имеет {userrep} совершенно бесполезных очков",
        " [{usertag}](tg://user?id={userid}) получает плюс и теперь имеет {userrep} совершенно бесполезных очков",
        " [{usertag}](tg://user?id={userid}) получает плюс и теперь имеет {userrep} совершенно бесполезных очков",
        "У [{usertag}](tg://user?id={userid}) теперь {userrep} пепяки, и это круто \\(нет\\)",
        "Эй, [{usertag}](tg://user?id={userid}), у тебя уже {userrep} плюсов, можешь начинать гордиться",
        "[{usertag}](tg://user?id={userid}) получает хуй в ро\\.\\.\\. плюс и теперь имеет {userrep} совершенно бесполезных очков",
    ]
    # replosestring = "[{usertag}](tg://user?id={userid}) получает миинус и теперь имеет {userrep} совершенно бесполезных очков"
    if raw == "+":
        rep = datastuff.changerep(userid=userid, chatid=chatid, delta=1)
        userrep = md_safe_int(rep)
        output = (random.choice(repgainstring).format(usertag=usertag, userid=userid, userrep=userrep), 10, -1)
    if raw == "-":
        # rep = changerep(userid=user.id,chatid=upd.effective_chat.id, delta=-1)
        # userrep=md_safe_int(rep)
        # output=replosestring.format(usertag=usertag,userid=userid,userrep=userrep)
        output = (random.choice(strings.nominus), 15, -1)
    if mereply:
        return handle_backtalk(userid=thisuid, chatid=chatid, botmsg=sourcemessage, usermsg=stext,msgid=rmsgid)
    if stext in strings.whoises:
        output = (datastuff.whois(userid=userid, chatid=chatid), 60, 5)
    if stext in strings.quotegrab:
        output = (MD(strings.quotesaves[datastuff.save_quote(userid=thisuid, chatid=chatid, author=userid,
                                                             messageid=replied.message_id, quote=replied.text)]), 10, 5)
    if stext in strings.show_quotes:
        output = (datastuff.show_all_quotes(userid=userid,chatid=chatid),120,5)

    if stext == "войсоблядь шоле сука":
        scores = datastuff.score_fetch(userid=userid, chatid=chatid, scorename="voice")
        statext = """
Пользователь {username}

Секунд напизжено:
Сегодня: {scores4}
На этой неделе:{scores3}
За месяц: {scores2}
За год: {scores1}
Всего: {scores0}
"""
        output = (
            MD(statext.format(username=usertag, scores0=scores[0], scores1=scores[1], scores2=scores[2],
                              scores3=scores[3],
                              scores4=scores[4])), 30, 10)
    if stext == "матанализ":
        print(str(antimat.get_mats("тест " + sourcemessage + " тест")))
        print(sourcemessage)
    if len(listext) >= 2:
        if listext[0] == "бот":
            match listext[1]:
                case "держи":
                    name = ' '.join(listext[2:])
                    return await datastuff.save_message(name=name, msg=replied, chatid=chatid, userid=thisuid)
                case "распространяй":
                    name = ' '.join(listext[2:])
                    return await datastuff.save_message(name=name, msg=replied, chatid=0, userid=thisuid)

                case _:
                    pass
        if listext[0] == "викторина":
            await deal_with_quiz_stuff(upd=upd, context=context, commands=listext, fulltail=fulltail)
    return output


# #handle a message that stands alone
async def handle_plain_message(upd: Update, context: ContextTypes.DEFAULT_TYPE):
    current = upd.message
    # extract text
    stext = ""
    fulltail = ""
    if current.text:
        if current.text[0] == "/":
            now = datetime.now()
            # midnight = now.replace(hour=23, minute=59, second=59, microsecond=0)
            datastuff.schedule_kill(chatid=upd.effective_chat.id, msgid=current.message_id,
                                    expiration=now.timestamp() + 120)
        stext = S(current.text.lower())
        rawlistext = current.text.split()
        fulltail = " ".join(rawlistext[2:])
    listext = stext.split()

    # calling all items
    if stext == "бот всех":
        # stext = 1
        return MD(datastuff.listuser(upd.effective_chat.id)), 60, 5
    # active users call
    if stext == "пиздуны":
        return datastuff.listactive(chatid=upd.effective_chat.id, count=10), 60, 5
    # user self check
    if stext in strings.whoisme:
        return datastuff.whois(userid=upd.message.from_user.id, chatid=upd.effective_chat.id), 30, 5
    # user opt back in
    if stext == "бот дай пизды":
        datastuff.resubscribe_user(userid=upd.message.from_user.id)
        return MD(random.choice(strings.morepizda)), -1, -1
    # super ping, broken
    if stext == "суперпинг":
        return datastuff.superping(chatid=upd.effective_chat.id)
    # pester this specific admin
    if stext == "так" and upd.message.from_user.id == 1153937777:
        return MD(random.choice(strings.takresponses)), -1, -1
    # voice top board
    if stext == "доска войсоблядей":
        heading = """Доска ~позора~ почёта войсоблядей чата:
```
"""
        outtext = datastuff.score_get_scoreboard(chatid=upd.effective_chat.id, scorename="voice", heading=heading)
        print(outtext)
        return outtext, 30, 5
    # voice top board
    if stext == "матершинники чата":
        heading = """Доска ~позора~ почёта матершинников чата:
```
"""
        outtext = datastuff.score_get_scoreboard(chatid=upd.effective_chat.id, scorename="mat", heading=heading)
        print(outtext)
        return outtext, 30, 5
    if stext == "покормить дану":
        outtext = """Вы успешно покормили Дану!

Вы получили:
💩: +10 какашек (🥩 +5 | 🍿 +5)
🍔: +1 к сытости Даны
😺: Бетти тоже перепало!"""
        datastuff.score_add(userid=upd.message.from_user.id, chatid=upd.effective_chat.id, scorename="danafeed",
                            delta=1)
        return MD(outtext), 30, 10
    if stext == "покормить бота":
        outtext = """Вы успешно покормили бота!

Вы получили:
🐞: +10 багов (😴 +5 | 🐒 +5)
🍑: +1 к пизде"""
        datastuff.score_add(userid=upd.message.from_user.id, chatid=upd.effective_chat.id, scorename="botfeed", delta=1)
        return MD(outtext), 30, 10
    if stext == "вызвать консоль" and upd.message.from_user.id == 906833258:  # current owner id
        await datastuff.console_begin(chatid=upd.effective_chat.id, userid=upd.message.from_user.id,source=upd.message.id)
    # top actives with param
    if len(listext) > 1:
        if listext[0] == "пиздуны":
            num = listext[1]
            return datastuff.listactive(chatid=upd.effective_chat.id, count=int(num)), 60, 5
    # bot commands
    if len(listext) >= 2:
        if listext[0] == "викторина":
            await deal_with_quiz_stuff(upd=upd, context=context, commands=listext, fulltail=fulltail)
            return
        if listext[0] == "бот":
            match listext[1]:

                case "дай":
                    name = ' '.join(listext[2:])
                    await datastuff.retrieve_message(chatid=upd.effective_chat.id, name=name)
                    return
                case _:
                    pass


#  if stext=="да" and random.random()<0.10:
#     await context.bot.send_message(chat_id=upd.effective_chat.id,text="пизда",reply_to_message_id=current.id)


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
    msgid = await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please fuck me!")
    datastuff.schedule_kill(chatid=update.effective_chat.id, msgid=msgid.message_id,
                            expiration=time.time() + botconfig.killdelay)


# #called on any regular messages
async def chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # update bot's userID
    # global botuid
    BotState.botuid = context.bot.id
    BotState.bot = context.bot
    # print(context)
    # print(BotState.botuid)
    # print(update)
    # check for weird updates and bail
    if update.message is None:
        # it could be something else!!
        if update.edited_message is not None:
            print("it was edited.")
        return
    # extract useful information from the update
    chatid = update.effective_chat.id
    userid = update.message.from_user.id
    # check if message has a parent message
    replyis = update.message.reply_to_message


    # logg messages
    ###############################datastuff.log_user(userid=userid, chatid=chatid)
    UserInfo.User.refresh(user_id=userid,chat_id=chatid)
    ########################datastuff.upcountmessage(userid=userid, chatid=chatid)
    ################datastuff.score_add(userid=userid, chatid=chatid, scorename="msgcount", delta=1)
    usr = UserInfo.User(userid,chatid)
    print(repr(usr))
    usr.msg_uptick()
    usr.refresh_nick(update.message.from_user.full_name)
    # upcount voice seconds if there's a voice message
    if update.message.voice is not None:
        usr.score_add("voice", update.message.voice.duration)
        usr.score_add("voice_count")
    if update.message.video_note is not None:
        usr.score_add("eblovoice", update.message.video_note.duration)
        usr.score_add("eblovoice_count")
    rawtext = ""
    stext = ""
    if update.message.text:
        rawtext = update.message.text.strip()
        stext = S(update.message.text.lower())
        # also upcount character counts
        usr.score_add("text",len(rawtext))
        usr.score_add("mat",len(antimat.get_mats("тест " + rawtext + " тест")))


    await actions.TriggeredSequence.run_triggers(update.message)

    # get user's name and check if it changed since last
###    newnick = update.message.from_user.full_name
        ### if oldnick is None:
        ###       datastuff.log_user_event(userid=userid, chatid=chatid, event_type="renamed", data=newnick)
        ###print("initial user seen")
        # fake join, currently the only working join
        ###datastuff.log_user_event(userid=userid, chatid=chatid, event_type="joined", data="message")
    # if user unknown yet, add with today's join date
    ###if datastuff.get_join_date(userid=userid, chatid=chatid) is None:
        ### datastuff.handle_new_user(userid=userid, chatid=chatid)
        ###print(f"new user {userid}@{chatid}!")
    # log user rename
    ###if oldnick is not None and oldnick != newnick:
        ### datastuff.log_user_event(userid=userid, chatid=chatid, event_type="renamed", data=newnick)
        ###print(f"User <{oldnick}> is now known as <{newnick}>.")
    # prepare text for processing, if there is any
    # output = ()

    # run triggers for response functions

    # joiners
    if update.message.new_chat_members:
        output = ("Это кто еще, блядь", -1, -1)
    elif update.message.left_chat_member:
        output = ("Куда, блядь", -1, -1)
    #else:

    # if the message is a reply to something, handle with reply
    #    if replyis is not None:
    #        output = await handle_with_reply(upd=update, context=context)
    #    # else handle standalone message
    #    else:
    #        output = await handle_plain_message(upd=update, context=context)
    # if any of the handling functions returned some sort of a response,
    # send the message, schedule deletes if needed
    #if output and BotState.talk:
    #    msgid = await context.bot.send_message(chat_id=update.effective_chat.id, text=output[0],
    #                                           parse_mode='MarkdownV2', reply_to_message_id=update.message.id)
    #    botmsg_killdelay = output[1]
    #    if botmsg_killdelay != -1:  # -1 to keep the bot's message
    #        if botmsg_killdelay == 0:  # 0 to use default kill delay
    #            botmsg_killdelay = botconfig.killdelay
    #        datastuff.schedule_kill(chatid=update.effective_chat.id, msgid=msgid.message_id,
    #                                expiration=time.time() + float(botmsg_killdelay))
    #    usermsg_killdelay = output[2]
    #    if usermsg_killdelay != -1:  # -1 to keep the user's message
    #        if usermsg_killdelay == 0:  # 0 to use default kill delay
    #            usermsg_killdelay = botconfig.killdelay
    #        datastuff.schedule_kill(chatid=update.effective_chat.id, msgid=update.message.id,
    #                                expiration=time.time() + float(usermsg_killdelay))


# handle joins/leaves etc
# async def member_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
#    result = extract_status_change(Update.chat_member)
#    if result is None:
#        return
#    output = ""
#    was_member, is_member = result
#    joining = not was_member and is_member
#    leaving = was_member and not is_member
#    if joining:
#        output = handle_join(update)
#    if leaving:
#        output = handle_leave(update)
#    if output:
#        await context.bot.send_message(chat_id=update.effective_chat.id, text=output, parse_mode='MarkdownV2')


async def reboot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    BotState.q.run_once(when=6, callback=restart_bot)


# #dump db to screen
async def dumpdb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    res = BotState.DBLink.execute("SELECT * FROM repuser")
    rows = res.fetchall()
    print(rows)
    data = print_to_string(rows)
    res = BotState.DBLink.execute("SELECT * FROM userseen")
    rows = res.fetchall()
    print(rows)
    data += print_to_string(rows)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=data)


async def restart_bot(context: CallbackContext):
    print("going down...")
    datastuff.blast("ухожу в ребут...")
    # os.fsync()
    print(sys.argv)
    os.execv(sys.executable, ['python'] + sys.argv)


async def random_chatter(chatid:int):
    chat_freq_var = datastuff.console_get_env(env_name="random_chatter_freq", chatid=chatid)
    try:
        chat_freq = float(chat_freq_var)
    except:
        chat_freq = 0.001

    chat_pool = datastuff.console_get_env(env_name="random_chatter_pool_id", chatid=chatid)
    if random.random() < chat_freq and chat_pool:
        await datastuff.retrieve_message_from_pool(chatid=chatid,
                                                   target_chatid=chatid, pool_id=chat_pool)


# #run this to keep checking for messages to kill
async def everyminute(context: CallbackContext):
    kills = datastuff.check_kills()
    if kills is not None:
        for (chat, msg) in kills:
            datastuff.kill_message(chatid=chat, msgid=msg)
    #await actions.TriggeredSequence.run_timers()
    #for chat in BotState.current_chats:
    #    if str(chat)[0] != "-":
    #        continue
    #    await random_chatter(chatid=chat)


async def actually_every_minute(context: CallbackContext):
    pass



async def receive_quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    print("-------QUIZ ANSWER!!")
    print(update)
    print("-------QUIZ ANSWER END---------------!!")


async def receive_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    print("-------QUIZ ANSWER DATA!!")
    print(update)
    print("-------QUIZ ANSWER DATA END---------------!!")
    answer = update.poll_answer.option_ids[0]
    uid = update.poll_answer.user.id
    pollid = update.poll_answer.poll_id
    print("user " + str(uid) + " answered #" + str(answer) + " on poll " + str(pollid))
    # TODO: triggers based on poll responses
    # datastuff.quiz_verify_answer(poll=int(pollid), user=uid, answer=answer)


async def receive_reaction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # print(update)
    msg = await BotState.pyroclient.get_messages(update.effective_chat.id,update.message_reaction.message_id)
    # print(msg)
    # TODO: triggers based on reactions
    # await console_capture_message(userid=update.effective_user.id,chatid=update.effective_chat.id,msg=msg)
    pass


async def join_leave(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    pass


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
            quote =" "
        escaped_quote = telegram.helpers.escape_markdown(quote,2)
        BotState.DBLink.execute("UPDATE qdb SET quote = ? WHERE qid = ?",(escaped_quote,qid))
    BotState.write()



# #launch the thing
if __name__ == '__main__':
    # init links to Telegram
    application = ApplicationBuilder().token(botconfig.bottoken).build()
    BotState.bot = application.bot
    BotState.DB = botconfig.DB
    BotState.DBLink = botconfig.DB.cursor()
    # one_off_updateMDV2()
    BotState.pyroclient = Client("BotenDana")
    # create handlers
    start_handler = CommandHandler('start', start)
    data_handler = CommandHandler('dump', dumpdb)
    reboot_handler = CommandHandler('reboot', reboot)

    commands = []
    handlers = []
    for seqname, seq in actions.TriggeredSequence.running_sequences.items():
        for cmd,info in seq.commands.items():
            #commands.append((cmd,info[0],info[1]))
            handlers.append(CommandHandler(cmd,seq.get_command_handler(cmd)))
    for handler in handlers:
        application.add_handler(handler)
    allmsg_handler = MessageHandler(filters.ALL, chat_message)  # & (~filters.COMMAND), chat_message)
    phandler = PollHandler(receive_quiz_answer)
    # joinleave_handler = ChatMemberHandler(member_change, ChatMemberHandler.CHAT_MEMBER)

    # register handlers
    # application.add_handler(joinleave_handler)
    application.add_handler(start_handler)
    application.add_handler(data_handler)
    application.add_handler(reboot_handler)
    application.add_handler(allmsg_handler)
    application.add_handler(phandler)
    application.add_handler(PollAnswerHandler(receive_poll_answer))
    application.add_handler(MessageReactionHandler(receive_reaction))
    application.add_handler(ChatMemberHandler(join_leave))
    # state inits
    #datastuff.load_chats()
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
