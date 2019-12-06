from asyncio import FIRST_COMPLETED, Future, create_task, wait
from random import shuffle
from typing import (Any, Optional, Set, Tuple, TypeVar, overload)

from typing_extensions import Literal

from channels.channel import ReceiveChannel
from channels.errors import ChannelClosed
from channels.operations import (CHANNEL_NOOP, CHANNEL_READY, CHANNEL_WAIT,
                                 ChannelWithOp,
                                 OptChannelWithOp, RECV)

T = TypeVar("T")


async def _wrap_wait(chan_op: ChannelWithOp) -> ChannelWithOp:
    chan, op = chan_op
    await CHANNEL_WAIT[op](chan)
    CHANNEL_NOOP[op](chan)
    return chan_op


def select_nowait(*channels: ChannelWithOp,
                  keep_order=False) -> OptChannelWithOp:
    chans = list(channels)
    if not keep_order:
        # Shuffle the list to avoid data race
        shuffle(chans)
    # Looks for a ready channel
    for chan_op in chans:
        chan, op = chan_op
        if CHANNEL_READY[op](chan):
            return chan_op
    return None, None


@overload
async def select(*channels: ChannelWithOp) -> ChannelWithOp:
    ...


@overload
async def select(*channels: ChannelWithOp, no_wait: Literal[False]
                 ) -> ChannelWithOp:
    ...


@overload
async def select(*channels: ChannelWithOp, no_wait: Literal[True]
                 ) -> OptChannelWithOp:
    ...


@overload
async def select(*channels: ChannelWithOp, no_wait: bool
                 ) -> OptChannelWithOp:
    ...


async def select(*channels: ChannelWithOp, no_wait: bool = False
                 ) -> OptChannelWithOp:
    # Shuffle the list to avoid data race
    chans = list(channels)
    shuffle(chans)
    selected = select_nowait(*chans, keep_order=True)
    if selected[0] is not None or no_wait:
        return selected
    pending: Set[Future[ChannelWithOp]] = {
        create_task(_wrap_wait(chan_op))
        for chan_op in chans
    }
    # Waits for the ready channels and return the first gettable value
    # Doesn't stop to the first ready, cause ChannelClosed can be raised
    while pending:
        done, pending = await wait(pending, return_when=FIRST_COMPLETED)
        for task in done:
            try:
                chan_op = task.result()
                # In case of another task having been run between wait
                # completion and here, closing the channel for example
                chan, op = chan_op
                if CHANNEL_READY[op](chan):
                    for pending_task in pending:
                        pending_task.cancel()
                    return chan_op
                else:
                    pending.add(create_task(_wrap_wait(chan_op)))
            except ChannelClosed:
                pass
    # Every "ready" channels were in fact closed
    raise ChannelClosed()


NoDefault = object()


@overload
async def select_get(*channels: ReceiveChannel[T]
                     ) -> Tuple[ReceiveChannel[T], T]:
    ...


@overload
async def select_get(*channels: ReceiveChannel[T], default: T
                     ) -> Tuple[Optional[ReceiveChannel[T]], T]:
    ...


@overload
async def select_get(*channels: ReceiveChannel
                     ) -> Tuple[ReceiveChannel, Any]:
    ...


@overload
async def select_get(*channels: ReceiveChannel, default: Any
                     ) -> Tuple[Optional[ReceiveChannel], Any]:
    ...


async def select_get(*channels: ReceiveChannel, default=NoDefault
                     ) -> Tuple[Optional[ReceiveChannel], Any]:
    chan, _ = await select(*map(RECV, channels),
                           no_wait=default is not NoDefault)
    if chan is None:
        assert default is not NoDefault
        return None, default
    assert isinstance(chan, ReceiveChannel)
    return chan, chan._receive()
