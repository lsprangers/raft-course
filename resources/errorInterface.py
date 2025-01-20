import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__name__)))

sys.path.append('/Users/lukesprangers/repos/raft_2025_01/lsprangers-raft/part5/')

class InvalidCommandError(Exception):
    pass