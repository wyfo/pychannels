from asyncio.events import get_running_loop
from asyncio.futures import Future

from channels.storage import QUEUE, StorageType

Waiter = Future


class WaitGroup:
    def __init__(self, storage=QUEUE):
        storage: StorageType[Future]
        self.waiters = storage.new()

    @property
    def empty(self) -> bool:
        return not self.waiters

    def wakeup_next(self):
        while self.waiters:
            waiter = self.waiters.get()
            if not waiter.done():
                waiter.set_result(None)
                break

    def wakeup_all(self):
        while self.waiters:
            waiter = self.waiters.get()
            if not waiter.done():
                waiter.set_result(None)

    async def wait(self):
        waiter = get_running_loop().create_future()
        self.waiters.put(waiter)
        await waiter

    def abort(self, exc: Exception):
        while self.waiters:
            waiter = self.waiters.get()
            if not waiter.done():
                waiter.set_exception(exc)
