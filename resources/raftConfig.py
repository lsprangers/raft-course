from enum import Enum

# For testing, let's focus on 0 and 1 nodes for now

class RaftStates(Enum):
    FOLLOWER = 0
    CANDIDATE = 1
    LEADER = 2
    
class raftConfig:
    def __init__(self):
        self.SERVERS = {
            0: ('localhost', 15000),
            1: ('localhost', 16000),
            2: ('localhost', 17000),
            # 3: ('localhost', 18000),
            # 4: ('localhost', 19000),
        }
        self.CLI_SERVER_ID = -1
        self.BOOTSTRAP_LEADER_ID = 0
        self.NETWORK_TICK = 10
        self.HEARTBEAT_TICK = 30
        self.ELECTION_TIMEOUT = 90

        self.STATES = RaftStates

        self.delimiter = ':::'