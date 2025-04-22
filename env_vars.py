from enum import Enum

from botstate import BotState


class EnvVarScope(Enum):
    GLOBAL = 0
    LOCAL = 1
    EFFECTIVE = 2


class EnvVar:
    """

    """
    @staticmethod
    def get_scope(env_name: str, scopeid: int) -> str | None:
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
