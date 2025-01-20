import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__name__)))

from dataclasses import dataclass
from enum import Enum
from typing import Union
import queue

class MessageQueue(queue.Queue):
    def put(self, item, block=True, timeout=None):
        if not isinstance(item, Message):
            raise TypeError("Only Message objects can be added to the queue")
        super().put(item, block, timeout)
        
@dataclass
class LogEntry:
    ''' 
    A single entry in the log
    Params:
        term_no (int) : describes the leaders term_no that issues this command
        command (str) : describes the actual command to be applied to state machine
    '''
    term_no: int
    command: str

@dataclass
class PersistentState:
    current_term: int
    voted_for: Union[None , int]
    log: list[LogEntry]

@dataclass
class AppendEntries:
    leader_term: int
    prev_log_idx: int
    prev_log_term: int
    leader_commit_idx: int
    send_entries: list[LogEntry]

@dataclass
class FollowerAppendEntriesResponse:
    success: bool
    curr_log_idx: int
    prev_log_idx_sent: int

@dataclass
class RequestVote:
    candidate_term: int
    candidate_id: int
    last_log_idx: int
    last_log_term: int

@dataclass
class ClientCommand:
    command: str
    hash: int

class MessageTypes(Enum):
    AppendEntries = 0
    FollowerAppendEntriesResponse = 1
    RequestVote = 2
    VoteYes = 3
    VoteNo = 4
    Ack = 5
    DebugPrintLog = 6
    ClientCommand = 7

@dataclass
class Message:
    '''
    Complete wrapper for all of this crap
        - m = Message(1, 2, MessageTypes.ClientCommand, ClientCommand('foo'))
        - m.type.name = 'ClientCommad'
    - Params:
        - from_server_id (int) : the server id of the sender
        - to_server_id (int) : the server id of the receiver
        - type (MessageTypes) : the type of message
        - data (Union[AppendEntries, FollowerAppendEntriesResponse, ClientCommand, None) : the data of the message
    '''
    from_server_id: int
    to_server_id: int
    type: MessageTypes
    data: Union[AppendEntries, FollowerAppendEntriesResponse, ClientCommand, None]

