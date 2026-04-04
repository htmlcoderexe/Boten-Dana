import time

import telegram.ext
from pyrogram import Client
from sqlite3.dbapi2 import Cursor
from telegram import Bot
botstate = None


class BotState:
    DBLink: Cursor = None
    DB = None
    current_chats = []
    q:telegram.ext.JobQueue = None
    bot:Bot = None
    bc = None
    botuid = 0
    pyroclient: Client = None
    prize_mode = False
    talk = True

    def __init__(self, dblink, bot, pyroclient):
        BotState.DB = dblink
        BotState.DBLink = dblink.cursor()
        BotState.bot = bot
        BotState.pyroclient = pyroclient

    @staticmethod
    def write():
        BotState.DB.commit()

    @staticmethod
    def update_chat_status(chat_id, name, status):
        q = """SELECT chatid FROM chat_info
        WHERE chatid = ?"""
        res = BotState.DBLink.execute(q,(chat_id,))
        row = res.fetchone()
        if not row:
            BotState.new_chat_status(chat_id,name,status)
            return
        q = """UPDATE chat_info
        SET name = ?, status = ?, time = ?
        WHERE chatid = ?"""
        res = BotState.DBLink.execute(q,(name,status,time.time(),chat_id))
        BotState.write()

    @staticmethod
    def update_chat_info(chat_id, name):
        q = """UPDATE chat_info
                SET name = ?, time = ?
                WHERE chatid = ?"""
        res = BotState.DBLink.execute(q, (name, time.time(), chat_id))
        BotState.write()

    @staticmethod
    def new_chat_status(chat_id, name, status):
        q = """INSERT INTO chat_info
        VALUES (?,?,?,?)"""
        res = BotState.DBLink.execute(q,(chat_id,name,status,time.time()))
        BotState.write()

    @staticmethod
    def get_chat_status(chat_id):
        q = """SELECT chatid, name, status, time FROM chat_info
        WHERE chatid = ?"""
        res = BotState.DBLink.execute(q,(chat_id,))
        row = res.fetchone()
        return row

