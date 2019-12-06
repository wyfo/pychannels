# Channel

Implementation of ['channel'](https://en.wikipedia.org/wiki/Channel_(programming)) ADT (used notably in Golang) on top of asyncio.

This README has been written in a few minutes, it would be improved later

# API

Channel are roughly specified as following:
```python
from typing import Generic, TypeVar

Msg = TypeVar("Msg")

class SendChannel(Generic[Msg]):
    async def send(self, msg: Msg): ...
    
class ReceiveChannel(Generic[Msg]):
    async def receive(self) -> Msg: ...

class Channel(SendChannel[Msg], ReceiveChannel[Msg]):
    pass
    
class ChannelClosed(Exception):
    pass    
    
class ClosableChannel(Channel[Msg]):
    def close(self): ...
    
    def __aiter__(self):
        return self
        
    def __anext__(self) -> Msg:
        try:
            return await self.receive()
        except ChannelClosed:
            raise StopIteration()
```
This specification is completed by a `select` (+ `select_nowait` + `select_get`) function, which enable to wait for the first channel ready to do an operation (receive/send):
```python
from typing import TypeVar, Tuple

from channels.operations import ChannelWithOp, SEND, RECV, OptChannelWithOp
from channels.channel import ReceiveChannel, BufferedChannel
from channels.select import NoDefault

async def select(*channels: ChannelWithOp) -> ChannelWithOp:
    ...

c1 = BufferedChannel()
c2 = BufferedChannel()
async def test_select():
    chan, _ = await select(RECV(c1), RECV(c2))
    if chan is c1:
        ...
    if chan is c2:
        ...

def select_nowait(*channels: ChannelWithOp) -> OptChannelWithOp:
    ...

def test_select_nowait():
    chan, _ = select_nowait(RECV(c1), RECV(c2))
    if chan is c1:
        ...
    if chan is c2:
        ...
    if chan is None: # no channel ready, don't wait
        ...
        
Msg = TypeVar("Msg")
async def select_get(*channels: ReceiveChannel[Msg], default: Msg = NoDefault) -> Tuple[ReceiveChannel[Msg], Msg]:
    ...
    
def test_select_get():
    _, value = await select_get(c1, c2, default=0)
```

## Some channel implementations
This package offers several channel implementations :
- `UnicastChannel(ClosableChannel[Msg])`: Unbuffered which can send a value only when another task is waiting for receiving it
- `BufferedChannel(UnicastChannel[Msg])`: Buffered channel which will not block (as long as the buffer is not full) when pushing a value and when receiving one (as long as the buffer is not empty); this is the closest implementation from the Golang one's
- `BroadcastChannel(ClosableChannel[Msg])`: Same as UnicastChannel, but every task receiving at the same time will receive the message sent
- `DefaultChannel(BroadcastChannel[Msg])`: When a message is sent, it is always available for all channel receiving (at the same time or not), until a new message is sent to replace it

## Difference with Go
- Asyncio is not thread-safe, neither are channels (I didn't had  found yet a way to not block the event loop while synchronizing threads)
- *Receiving from a closed channel* can *raise a `ChannelClosed` exception*; for a buffered channel, the buffer will be emptied before raising
- The Go idiom closing a (sometimes untyped) channel to broadcast has a good replacement with BroadcastChannel/DefaultChannel (this last one has been specified to fit this use). Actually, `ChannelClosed` exception is in fact broadcasted and could be used.
- `select` can raise `ChannelClosed` when all the channels are closed and not able to perform the given operation

## My own channel implementation
Some helpers are provided :
- `ClosableChannel(Channel[Msg])`: Adds closing interface and do some magic metaprogramming in order to automatically raise the `ChannelClosed` exception in the method of the deriving class; metaprogramming could seem to be useless or too much compared to overwriting and method addition, but it allows to add the `Closable` capability to a channel just by adding the class in specification, without having to modify the implementation
- `BaseChannel(Channel[Msg])`: Implements the waiting part of the channel
- `BaseClosableChannel(Channel[Msg])`: Merge of the two previous

# TODO
A lot of things ..., but as it is, it's just a one week project.
Proper tests, finish documentations, use cases, code reorg + renaming, etc.
Find a way to make it thread-safe without blocking the event-loop (even if with the GIL, i'm not sure that's an issue ...)
