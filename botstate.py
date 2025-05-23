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
