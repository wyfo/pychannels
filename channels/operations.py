from enum import Enum, auto
from typing import Tuple, Union

from typing_extensions import Literal

from channels.channel import ReceiveChannel, SendChannel


class ChannelOperation(Enum):
    SEND = auto()
    RECV = auto()


ChannelWithOp = Union[Tuple[SendChannel, Literal[ChannelOperation.SEND]],
                      Tuple[ReceiveChannel, Literal[ChannelOperation.RECV]]]
OptChannelWithOp = Union[ChannelWithOp, Tuple[None, None]]


def SEND(chan: SendChannel) -> ChannelWithOp:  # noqa
    return chan, ChannelOperation.SEND  # type: ignore


def RECV(chan: ReceiveChannel) -> ChannelWithOp:  # noqa
    return chan, ChannelOperation.RECV  # type: ignore


CHANNEL_READY = {
    ChannelOperation.SEND: lambda chan: chan._ready_to_send,
    ChannelOperation.RECV: lambda chan: chan._ready_to_receive,
}

CHANNEL_WAIT = {
    ChannelOperation.SEND: lambda chan: chan._wait_send,
    ChannelOperation.RECV: lambda chan: chan._wait_receive,
}

CHANNEL_NOOP = {
    ChannelOperation.SEND: lambda chan: chan._no_send,
    ChannelOperation.RECV: lambda chan: chan._no_receive,
}
