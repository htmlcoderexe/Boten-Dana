import logging
from pathlib import Path
import actions
import asyncio
from telegram import Message
import sqlite3


mockmsg = lambda : None
mockmsg.text = "бот это кто"


seqdir = Path("./sequences")
seqfiles = list(seqdir.glob("*.json"))
for seq in seqfiles:
    sdata = seq.read_text("UTF-8")
    sequence = actions.TriggeredSequence.load_from_json(sdata)
    actions.TriggeredSequence.running_sequences[sequence.name] = sequence
print(f"Loaded {len(actions.TriggeredSequence.running_sequences)} sequences.")
#print(actions.TriggeredAction.registry)
# default time to clean own/replied messages
killdelay = 40.0
# load the token from file
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
