from abc import ABC, abstractmethod
from functools import wraps
from typing import Generic, Optional, TypeVar

from channels.errors import ChannelClosed, ChannelNotReady
from channels.storage import QUEUE, StorageType
from channels.utils import NO_MSG, NoMessage, OptMsg
from channels.wait_group import WaitGroup

Msg = TypeVar("Msg")


class SendChannel(ABC, Generic[Msg]):
    @abstractmethod
    def _ready_to_send(self) -> bool:
        """
        :return: if the channel is ready to send a message
        """
        ...

    @abstractmethod
    async def _wait_send(self):
        """
        Waits for the channel to be ready for message sending
        """
        ...

    @abstractmethod
    def _send(self, msg: Msg):
        """
        Sends a message through the channel
        :param msg: the message sent
        """
        ...

    def _no_send(self):
        """
        Must be called when _wait_send is not followed by _send
        """
        pass

    async def send(self, msg: Msg):
        """
        Sends a message through the channel
        :param msg: the message sent
        """
        while not self._ready_to_send():
            await self._wait_send()
        self._send(msg)

    def send_nowait(self, msg: Msg):
        from channels.operations import ChannelOperation
        if not self._ready_to_send():
            raise ChannelNotReady(ChannelOperation.SEND)
        self._send(msg)


class ReceiveChannel(Generic[Msg], ABC):
    @abstractmethod
    def _ready_to_receive(self) -> bool:
        """
        :return: if the channel is ready to receive a message
        """
        ...

    @abstractmethod
    async def _wait_receive(self):
        """
        Waits for the channel to be ready for message receiving
        """
        ...

    @abstractmethod
    def _receive(self) -> Msg:
        """
        Receives a message from the channel
        :return: the message received
        """
        ...

    def _no_receive(self):
        """
        Must be called when _wait_receive is not followed by _receive
        """
        pass

    async def receive(self) -> Msg:
        """
        Receives a message from the channel after waiting for it to be ready
        :return: the message received
        """
        while not self._ready_to_receive():
            await self._wait_receive()
        return self._receive()

    def receive_nowait(self) -> Msg:
        from channels.operations import ChannelOperation
        if not self._ready_to_receive():
            raise ChannelNotReady(ChannelOperation.RECV)
        return self._receive()


class Channel(SendChannel[Msg], ReceiveChannel[Msg], ABC):
    pass


class Closable(ABC):
    @abstractmethod
    def close(self):
        ...

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class ClosableChannel(Channel[Msg], Closable, ABC):
    def __init_subclass__(cls, *args, **kwargs):
        super().__init_subclass__(*args, **kwargs)
        init = cls.__init__
        ready_to_send = cls._ready_to_send
        ready_to_receive = cls._ready_to_receive

        @wraps(init)
        def __init__(self, *args, **kwargs):
            init(self, *args, **kwargs)  # noqa
            self._closed = False

        @wraps(ready_to_send)
        def _ready_to_send(self: ClosableChannel) -> bool:
            if self.closed:
                raise ChannelClosed()
            return ready_to_send(self)

        @wraps(ready_to_receive)
        def _ready_to_receive(self: ClosableChannel) -> bool:
            ready = ready_to_receive(self)
            if not ready and self.closed:
                raise ChannelClosed()
            return ready

        cls_alias = cls  # use cls alias because of pycharm "bug"
        cls_alias.__init__ = __init__
        cls_alias._ready_to_send = _ready_to_send
        cls_alias._ready_to_receive = _ready_to_receive

    def _close(self):
        pass

    def close(self):
        self._close()
        self._closed = True  # noqa

    @property
    def closed(self) -> bool:
        return self._closed

    def __aiter__(self):
        return self

    async def __anext__(self) -> Msg:
        try:
            return await self.receive()
        except ChannelClosed:
            raise StopIteration()


class BaseChannel(Channel[Msg], ABC):
    def __init__(self):
        self._senders = WaitGroup()
        self._receivers = WaitGroup()

    async def _wait_send(self):
        await self._senders.wait()

    async def _no_send(self):
        self._senders.wakeup_next()

    async def _wait_receive(self):
        await self._receivers.wait()

    async def _no_receive(self):
        self._receivers.wakeup_next()


class BaseClosableChannel(BaseChannel[Msg], ClosableChannel[Msg], ABC):
    def __init_subclass__(cls, *args, **kwargs):
        super().__init_subclass__(*args, **kwargs)
        receive = cls._receive

        @wraps(cls.receive)
        def _receive(self: BaseClosableChannel) -> Msg:
            msg = receive(self)
            if self.closed and not self._ready_to_receive():
                self._receivers.abort(ChannelClosed())
            return msg

        cls_alias = cls  # use cls alias because of pycharm "bug"
        cls_alias._receive = _receive

    def _close(self):
        # Notifies (aborts) waiting senders that the channel is closed
        self._senders.abort(ChannelClosed())
        # When empty, aborts waiting receivers too
        # Otherwise, remaining getters handling is done in Channel.get_nowait
        if not self._ready_to_receive():
            self._receivers.abort(ChannelClosed())
        # Only receivers that overflow from the closed queue could be aborted,
        # but that could lead to concurrent situations where closed receiver is
        # waken up before not closed one, which are thus avoided


class _XcastChannel(BaseClosableChannel[Msg]):
    def __init__(self):
        super().__init__()
        self._message: OptMsg = NO_MSG

    def _ready_to_send(self) -> bool:
        return self._message is NO_MSG and not self._receivers.empty

    @abstractmethod
    def _wakeup_receivers(self):
        ...

    def _send(self, msg: Msg):
        assert self._message is NO_MSG
        self._message = msg
        self._wakeup_receivers()

    def _ready_to_receive(self) -> bool:
        return self._message is not NO_MSG

    def _receive(self) -> Msg:
        assert not isinstance(self._message, NoMessage)
        msg = self._message
        self._message = NO_MSG
        self._senders.wakeup_next()
        return msg


class UnicastChannel(_XcastChannel[Msg]):
    def _wakeup_receivers(self):
        self._receivers.wakeup_next()


class BroadcastChannel(_XcastChannel[Msg]):
    def _wakeup_receivers(self):
        self._receivers.wakeup_all()


class DefaultChannel(BroadcastChannel[Msg]):
    def __init__(self, default_msg: OptMsg = NO_MSG):
        super().__init__()
        self._message = default_msg

    def reset(self):
        self._message = NO_MSG

    def _ready_to_send(self) -> bool:
        return True

    async def _wait_send(self):
        pass

    def _send(self, msg: Msg):
        self._message = msg
        self._receivers.wakeup_all()


class BufferedChannel(UnicastChannel[Msg]):
    def __init__(self, maxsize: Optional[int] = None,
                 storage: StorageType[Msg] = QUEUE):
        super().__init__()
        self.maxsize = maxsize
        self._messages = storage.new()

    @property
    def empty(self) -> bool:
        return not self._messages

    @property
    def full(self) -> bool:
        return self.maxsize is not None and self.size >= self.maxsize

    @property
    def size(self):
        return len(self._messages)

    def _ready_to_send(self) -> bool:
        if self.maxsize == 0:
            return self.empty and not self._receivers.empty
        else:
            return not self.full

    def _send(self, msg: Msg):
        self._messages.put(msg)
        self._receivers.wakeup_next()

    def _ready_to_receive(self) -> bool:
        return not self.empty

    def _receive(self) -> Msg:
        msg = self._messages.get()
        self._senders.wakeup_next()
        return msg
