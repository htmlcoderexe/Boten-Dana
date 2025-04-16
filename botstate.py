from pyrogram import Client
from sqlite3.dbapi2 import Cursor
botstate = None


class BotState:
    DBLink: Cursor = None
    DB = None
    current_chats = []
    q = None
    bot = None
    bc = None
    botuid = 0
    pyroclient: Client = None
    prize_mode = False
    talk = True

    def __init__(self, dblink, bot, pyroclient):
        self.DB = dblink
        self.DBLink = dblink.cursor()
        self.bot = bot
        self.pyroclient = pyroclient

    @staticmethod
    def write():
        BotState.DB.commit()
