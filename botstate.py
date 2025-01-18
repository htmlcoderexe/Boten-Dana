import botconfig

DBLink = botconfig.DB.cursor()
current_chats = []
q = None
bot = None
bc = None
botuid = 0
pyroclient = None
prize_mode = False

def write():
    botconfig.DB.commit()
