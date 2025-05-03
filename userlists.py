import botstate
from actions import TriggeredAction
from telegram import Message as TGMessage


class UserList:

    @staticmethod
    def check_list(user_id:int,list_name:str):
        res = botstate.BotState.DBLink.execute("""
        SELECT user_id FROM user_lists
        WHERE user_id = ?
        AND list_name = ?
        """,(user_id,list_name))
        row = res.fetchone()
        return True if row else False

    @staticmethod
    def add_user(user_id:int, list_name:str) -> bool:
        if not UserList.check_list(user_id,list_name):
            botstate.BotState.DBLink.execute("""
            INSERT INTO user_lists
            VALUES (?, ?)
            """,(list_name,user_id))
            botstate.BotState.write()
            return True
        return False

    @staticmethod
    def remove_user(user_id:int, list_name:str) -> bool:
        if UserList.check_list(user_id,list_name):
            botstate.BotState.DBLink.execute("""
            DELETE FROM user_lists
            WHERE user_id = ?
            AND list_name = ?
            """,(user_id,list_name))
            botstate.BotState.write()
            return True
        return False


class ActionCheckUserList(TriggeredAction, action_name="userlist_check"):
    """ Checks if a user is on a given list
    param 0: uid
    param 1: userlist name
    param 2: variable to store the result to
    """
    async def run_action(self, message: TGMessage) -> str:
        uid = int(self.read_param(0))
        ulist = self.read_param(1)
        outvar = self.read_param(2)
        self.varstore[outvar] = UserList.check_list(uid, ulist)
        return ""


class ActionUserListAdd(TriggeredAction, action_name="userlist_add"):
    """ Adds a user to a given list
    param 0: uid
    param 1: userlist name
    param 2: variable to store the result to
    """
    async def run_action(self, message: TGMessage) -> str:
        uid = int(self.read_param(0))
        ulist = self.read_param(1)
        outvar = self.read_param(2)
        self.varstore[outvar] = UserList.add_user(uid, ulist)
        return ""


class ActionUserListRemove(TriggeredAction, action_name="userlist_remove"):
    """ Removes a user from a given list
    param 0: uid
    param 1: userlist name
    param 2: variable to store the result to
    """
    async def run_action(self, message: TGMessage) -> str:
        uid = int(self.read_param(0))
        ulist = self.read_param(1)
        outvar = self.read_param(2)
        self.varstore[outvar] = UserList.remove_user(uid, ulist)
        return ""
