import logging

import sqlite3

# default time to clean own/replied messages
killdelay = 40.0
# don't show anyone this, #TODO: make this load from
# a git-ignore'd file
with open(".token") as tokenfile:
    bottoken = tokenfile.read()
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

