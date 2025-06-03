import datetime
import functools
from enum import Enum, auto
from typing import Any, Callable, Tuple, Type, TypeVar

import grpc

from h2pcontrol.pb.h2pcontrol import (
    DataPacket,
    Empty,
    FetchServersResponse,
    ManagerStub,
)

TStub = TypeVar("TStub")


class ServerAccessor:
    def __init__(self, server_names):
        super().__init__()
        for name in server_names:
            # Only allow valid Python identifiers as attributes
            if name.isidentifier():
                setattr(self, name, name)


class H2PControl:
    def __init__(self, address: str):
        self.address = address
        self.channel = None
        self.manager = None
        self.servers = []

    async def connect(self):
        self.channel = grpc.aio.insecure_channel(self.address)
        self.manager = ManagerStub(self.channel)

        fetchServerResponse: FetchServersResponse = await self.manager.fetch_servers(
            Empty()
        )

        server_names = [server.name for server in fetchServerResponse.servers]
        self.servers = ServerAccessor(server_names)

    async def register_server(
        self, name: str, stub: Type[TStub]
    ) -> Tuple[grpc.aio.Channel, TStub]:
        response: FetchServersResponse = await self.manager.fetch_servers(Empty())
        for server in response.servers:
            if server.name == name:
                channel = grpc.aio.insecure_channel(server.addr)
                server = stub(channel)
                return channel, server
        raise ValueError(f"Server named {name} not found")

    async def close(self):
        if self.channel:
            await self.channel.close()
            self.channel = None
            self.manager = None


class Mode(Enum):
    In = auto()
    Out = auto()


F = TypeVar("F", bound=Callable[..., Any])


class H2PDataSink:
    def __init__(self, *modes: Mode):
        self.log_in = Mode.In in modes
        self.log_out = Mode.Out in modes

    def __call__(self, func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if self.log_in:
                print(f"Calling {func.__name__} with args: {args}, kwargs: {kwargs}")
                dp = DataPacket(
                    timestamp=datetime.datetime.now(),
                    proto_file="todo",
                    function="function",
                    # data_in=bytes(args),
                    data_in=print(args.to_json()),
                )

                print(dp)
            result = func(*args, **kwargs)
            if self.log_out:
                print(f"{func.__name__} returned: {result}")
            return result

        return wrapper
