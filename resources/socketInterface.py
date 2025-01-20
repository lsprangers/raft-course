import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__name__)))

sys.path.append('/Users/lukesprangers/repos/raft_2025_01/lsprangers-raft/part5/')

import logging
# Configure the logger
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

from socket import *
from dataclasses import dataclass
import pickle
from time import time_ns
from resources.errorInterface import InvalidCommandError
from resources.messageInterface import Message

class SocketInterface:
    def __init__(self):
        self.client_reply = "OK"
        self.msg_size_length = 10
        # self.verbose = verbose
    
    def hash_client_command(self, cmd: str) -> int:
        '''
            This should generate a unique hash for a given command
            at the seconds level...so as long as our clients
            don't send the same command within the same second, we should 
            be relatively fine

        '''
        return int(
            (time_ns() % 1000000000) + 
            (hash(cmd) % 10000)
        )

    def serialize_dataclass(self, obj: Message) -> bytes:
        return pickle.dumps(obj)

    def deserialize_dataclass(self, data: bytes) -> Message:
        return pickle.loads(data)    

    def recv_exactly(self, sock: socket, nbytes: int) -> bytes:
        chunks = []
        while nbytes > 0:
            chunk = sock.recv(nbytes)
            if chunk == b'':
                raise IOError("Incomplete message - Failed getting message from self.msg_size_length")
            chunks.append(chunk)

            logger.debug(f"Received: {len(chunk)} bytes")
                
            nbytes -= len(chunk)
        return b''.join(chunks)

    def recv_message(self, sock: socket) -> Message:
        msg_bytes = self.recv_bytes(sock)
        return self.deserialize_dataclass(msg_bytes)
    
    def recv_bytes(self, sock: socket) -> bytes:
        '''loops over length of message and continues to receive in modulo 10 chunks until all bytes are received'''
        msg_size = int(self.recv_exactly(sock, self.msg_size_length))   # Get size of message from the first 10 bytes
        return self.recv_exactly(sock, msg_size)

    def send_message(self, sock: socket, msg: Message) -> None:
        msg_bytes = self.serialize_dataclass(msg)
        self.send_bytes(sock, msg_bytes)
        return
    
    def send_bytes(self, sock: socket, msg: bytes) -> None:
        msg_size = b'%10d' % len(msg)       # Make a 10-byte length field
        sock.sendall(msg_size)              # Send the length field
        sock.sendall(msg)                   # Send the message of that size
        return