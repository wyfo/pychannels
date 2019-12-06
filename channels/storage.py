from collections import deque
from heapq import heappop, heappush
from typing import Callable, Collection, Generic, Type, TypeVar

Container = TypeVar("Container", bound=Collection)
Element = TypeVar("Element")


class Storage(Collection[Element]):
    def __init__(self, store: Type[Container],
                 put: Callable[[Container, Element], None],
                 get: Callable[[Container], Element]):
        self._store = store()
        self._get = get
        self._put = put

    def put(self, elt: Element):
        self._put(self._store, elt)

    def get(self) -> Element:
        return self._get(self._store)

    def __contains__(self, item):
        return item in self._store

    def __len__(self):
        return len(self._store)

    def __iter__(self):
        iter(self._store)


class StorageType(Generic[Element]):
    def __init__(self, store: Type[Container],
                 put: Callable[[Container, Element], None],
                 get: Callable[[Container], Element]):
        self.store = store
        self.put = put
        self.get = get

    def new(self) -> Storage[Element]:
        return Storage(self.store, self.put, self.get)


QUEUE = StorageType(deque, deque.append, deque.popleft)
FIFO = QUEUE
STACK = StorageType(list, list.append, list.pop)
LIFO = STACK
HEAP = StorageType(list, heappush, heappop)
PRIORITY_QUEUE = HEAP
