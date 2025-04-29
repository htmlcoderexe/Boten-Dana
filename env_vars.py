from enum import Enum

from botstate import BotState


class EnvVarScope(Enum):
    GLOBAL = 0
    """Global scope"""
    LOCAL = 1
    """Local scope, specific to a ChatID"""
    EFFECTIVE = 2
    """Effective scope - local value if available, else global"""


class EnvVar:
    """

    """
    @staticmethod
    def get_scope(env_name: str, scopeid: int) -> str | None:
        """
        Gets the env-var from a specific scope
        @param env_name: Name of the variable
        @param scopeid: Scope (chatID if local, 0 if global)
        @return:
        """
        results = BotState.DBLink.execute(("""
            SELECT var_value FROM env_vars
            WHERE var_scope = ?
            AND var_name = ?
            """), (scopeid, env_name))
        result = results.fetchone()
        print(env_name, scopeid)
        print(results)
        print(result)
        if result:
            return result[0]
        return None

    @staticmethod
    def get(env_name: str, chatid: int, option: EnvVarScope = EnvVarScope.EFFECTIVE) -> str:
        """
        Gets the value of a specific environment variable.
        @param env_name: Name of the variable.
        @param chatid: ChatID of the chat in question.
        @param option: Scope selection between global, local or effective
        @return:
        """
        print("Selecting scope...")
        if option == EnvVarScope.LOCAL:
            print("Local chosen.")
            return EnvVar.get_scope(env_name=env_name, scopeid=chatid)
        if option == EnvVarScope.GLOBAL:
            print("Global chosen.")
            return EnvVar.get_scope(env_name=env_name, scopeid=0)
        if option == EnvVarScope.EFFECTIVE:
            print("Effective chosen.")
            final = EnvVar.get_scope(env_name=env_name, scopeid=chatid)
            if not final:
                final = EnvVar.get_scope(env_name=env_name, scopeid=0)
            return final

    @staticmethod
    def set_scope(env_name: str, scopeid: int, value: str):
        """
        Sets the value of an environment variable.
        @param env_name: Name ov the variable.
        @param scopeid: ChatID for local scopes or 0 for global scope
        @param value: Value to set the variable to.
        @return:
        """
        exists = EnvVar.get_scope(env_name, scopeid)
        if exists:
            BotState.DBLink.execute(("""
                    UPDATE env_vars
                    SET var_value = ?
                    WHERE var_scope = ?
                    AND var_name = ?
                    """), (value, scopeid, env_name))
            BotState.write()
        else:
            BotState.DBLink.execute(("""
                            INSERT INTO env_vars
                            VALUES(?,?,?)
                            """), (env_name, value, scopeid))
            BotState.write()
