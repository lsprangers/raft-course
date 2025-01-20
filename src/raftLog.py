
from dataclasses import dataclass
from resources.messageInterface import *

# prevIdx = previous index, starting at 1, that the leader knows is in the follower's log
#   followers don't keep up with leaders nextIdx / req/resp with other followers...so if leader dies, other machine comes up
#       and doesn't know what the last index was that the leader knew about
#   that is solved by new follower sets prevIdx = len(log) - 1
# prevTerm = leader term of the previous index...you basically just find prevTerm = log[prevIdx].term

class RaftLog:
    def __init__(self):
        self.entries = { 0: LogEntry(0, '') }
        self.last_log_idx = 0

    def __eq__(self, other):
        # Equality check useful for testing
        return (self.entries == other.entries and
                self.last_log_index == other.last_log_index)

    def __repr__(self):
        return f'RaftLog<last_log_index={self.last_log_index}, {sorted(self.entries.items())}>'
        
    def force_add_new_command(self, leader_term: int, command: str):
        ''' 
        Add a new command to the log, and return the index of the command
        it will look like this:
        {
            0: LogEntry(1, 'x'),
            1: LogEntry(1, 'y'),
            2: LogEntry(1, 'z')
            ...
        }
        '''
        entry = LogEntry(leader_term, command)
        self.last_log_idx += 1
        self.entries[self.last_log_idx] = entry

        # send appendEntries RPC (leader_term, command) to all servers
        # if consensus, then apply_entry
        # self.last_applied += 1

    def append_entries(self, prev_log_idx: int, prev_log_term: int, send_entries: list[LogEntry]):
        ''' 
        Append entries to the log
        Params:
            prev_log_idx (int) : the index of the previous log entry of leader (sent in RPC)
            prev_log_term (int) : the term of the previous log entry of leader (sent in RPC)
        '''
        # If the log doesn't contain an entry at prev_log_idx, return False
        #  This basically means if we don't have something at the previous index, we can't append
        if prev_log_idx not in self.entries.keys():
            return(False)
        
        # (Receiver Implementation #2 on Figure 2)
        if self.entries[prev_log_idx].term_no != prev_log_term:
            return(False)
              
        # If the log doesn't contain an entry at prev_log_idx or the term doesn't match, return False
        if prev_log_idx > self.last_log_idx:
            return(False)

        
        # At this point we know our term is consistent with leader, and that everything up
        #  to the previous log term matches
        # (Receiver Implementation #3 & #4 on Figure 2)

        # Basically, if our prev_log_idx match from comparison above, then the new
        #   entries should be prev_log_idx + 1 and onwards
        for idx, entry in enumerate(send_entries, start=prev_log_idx+1):
            # If we already have something there, get rid of it
            if idx in self.entries and self.entries[idx].term_no != entry.term_no:
                self.delete_all_entries_from(idx)
            
            self.entries[idx] = entry
            self.last_log_idx = max(idx, self.last_log_idx)

        return True

    def delete_all_entries_from(self, index):
        self.last_log_idx = index - 1
        while self.entries.pop(index, None):
            index += 1

    def get_entries(self, start, end):
        # Get log entries within a range of indices (inclusive)
        return [self.entries[n] for n in range(start, end+1)]


def test_raftlog():
    log = RaftLog()
    # Leader appends should always just work
    log.force_add_new_command(1, 'x')
    log.force_add_new_command(1, 'y')
    assert log.get_entries(1, 2) == [ LogEntry(1, 'x'), LogEntry(1, 'y') ]

    # Test various follower-appends
    log = RaftLog()
    assert log.append_entries(prev_log_idx=0, prev_log_term=0, send_entries=[ LogEntry(1, 'x') ])
    assert log.append_entries(prev_log_idx=1, prev_log_term=1, send_entries=[ LogEntry(1, 'y') ])
    assert log.get_entries(1, 2) == [ LogEntry(1, 'x'), LogEntry(1, 'y') ]

    # Repeated operations should be ok (idempotent)
    assert log.append_entries(prev_log_idx=0, prev_log_term=0, send_entries=[ LogEntry(1, 'x') ])
    assert log.append_entries(prev_log_idx=1, prev_log_term=1, send_entries=[ LogEntry(1, 'y') ])
    assert log.get_entries(1, 2) == [ LogEntry(1, 'x'), LogEntry(1, 'y') ]
    
    # Can't have holes
    assert log.append_entries(prev_log_idx=10, prev_log_term=1, send_entries=[ LogEntry(1, 'z')]) == False

    # Can't append if the previous term doesn't match up right
    assert log.append_entries(prev_log_idx=2, prev_log_term=2, send_entries = [LogEntry(2, 'z') ]) == False

    # If adding an entry with a conflicting term, all entries afterwards should
    # go away
    assert log.append_entries(prev_log_idx=0, prev_log_term=0, send_entries=[LogEntry(3, 'w')]) == True
    assert log.last_log_idx == 1

    # Adding empty entries should work as log as term/index is okay
    assert log.append_entries(prev_log_idx=1, prev_log_term=3, send_entries=[]) == True
    assert log.append_entries(prev_log_idx=1, prev_log_term=2, send_entries=[]) == False

if __name__ == '__main__':
    test_raftlog()