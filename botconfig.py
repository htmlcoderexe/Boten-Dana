import logging
from pathlib import Path
import asyncio
from telegram import Message
import sqlite3


mockmsg = lambda : None
mockmsg.text = "бот это кто"


#print(actions.TriggeredAction.registry)
# default time to clean own/replied messages
killdelay = 40.0
# load the token from file
with open(".token") as tokenfile:
    bottoken = tokenfile.read()
with open(".owner") as ownerfile:
    operator = int(ownerfile.read())
# set up the bot data connection
DB = sqlite3.connect("main.db")
# set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.ERROR,
    handlers=[
        logging.FileHandler("error.log"),
        logging.StreamHandler()
    ]
)
