from typing import Union

from channels.channel import Msg


class NoMessage:
    pass


NO_MSG = NoMessage()
OptMsg = Union[Msg, NoMessage]

