from channels.operations import ChannelOperation


class ChannelError(Exception):
    pass


class ChannelClosed(ChannelError):
    pass


class ChannelNotReady(ChannelError):
    def __init__(self, op: ChannelOperation):
        self.operation = op
