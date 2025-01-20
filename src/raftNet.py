import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__name__)))

# Debugger /Tests need this crap
sys.path.append('/Users/lukesprangers/repos/raft_2025_01/lsprangers-raft/part5/')
sys.path.append('/Users/lukesprangers/repos/raft_2025_01/lsprangers-raft/part5/src/')

import logging
# Configure the logger
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


from typing import Union 
from socket import *
from threading import *
from resources.socketInterface import SocketInterface
from resources.messageInterface import *
from resources.raftConfig import raftConfig
from raftLog import RaftLog
from select import select
from queue import *
from collections import defaultdict
from time import time
import random

# Entry can be considered committed if it is safe for that entry to be applied to state machine
#   An entry is considered safe to apply to the state machine if it is in the log of a majority of the servers (quorum)
#   If an entry is committed, then all preceding entries are also committed
#   If an entry is committed, then all preceding entries are also safe to apply to the state machine
#   leader.commit_idx = min(leader.commit_idx, follower.commit_idx) over all followers
#       This comes out to finding the median(commit_idx) of all followers
#       follower commit idx = [2, 4, 7, 8, 8] --> commit idx = 7

class RaftNode:
    def __init__(self, server_id):
        self.server_id = server_id


        # Common Configurations + DNS
        self.config = raftConfig()
        self.host, self.port = self.config.SERVERS[self.server_id]
        self.delimiter = self.config.delimiter
        self.NETWORK_TICK = self.config.NETWORK_TICK
        self.HEARTBEAT_TICK = self.config.HEARTBEAT_TICK
        self.ELECTION_TIMEOUT = self.config.ELECTION_TIMEOUT

        # Volatile State on Servers
        self.last_heartbeat = time()
        self.last_election = time()
        self.commit_idx = 0
        # self.last_applied_entry_idx = self.raft_log.last_log_idx ???
        self.received_votes_for_leadership = 1 # we always vote for ourselves

        # We should be able to store the entry_no and # acks 
        self.client_command_acks = defaultdict(int)

        # Raft Log
        self.raft_log = RaftLog()
        self.states = self.config.STATES
        self.state = self.states.FOLLOWER
        self.am_leader = False
        self.leader_id = self.config.BOOTSTRAP_LEADER_ID
        if self.server_id == self.config.BOOTSTRAP_LEADER_ID:
            self.am_leader = True
            self.state = self.states.LEADER

        # Not persisted yet, but will be eventually
        self.persistent_state = PersistentState(
            current_term = 0,
            voted_for = None,
            log = self.raft_log.entries
        )
        
        # Set each other server's last log index to our known last log idx
        self.other_servers_last_log_idx = {
            server_id: self.raft_log.last_log_idx 
            for server_id in self.config.SERVERS.keys() 
            if server_id != self.server_id
        }

        # Networking
        self.socket = self.create_server_socket()
        # self.socket.settimeout(self.NETWORK_TICK)  # Set a timeout for the socket
        # self.socket.setblocking(0)  
     
        # Actor Model      
        self.socketInterface = SocketInterface()
        self.egress_queue = MessageQueue()
        self.ingress_queue = MessageQueue()

    def create_server_socket(self):
        sock = socket(AF_INET, SOCK_STREAM)
        sock.bind((self.host, self.port))
        sock.listen(5)
        return sock

    def receive(self):
        conn, addr = self.socket.accept()
        logger.debug(f"receive - Connection from {conn} {addr} has been established!")
        msg = self.socketInterface.recv_message(conn)
        logger.debug(f"receive - Received message: {msg.data} on server {self.server_id} --> putting in queue")
        self.ingress_queue.put(msg)
        conn.close()

    def receiver(self):
        while True:
            readable, _, _ = select([self.socket], [], [], self.NETWORK_TICK)
            if self.socket in readable:
                self.receive()

    def egress(self, addr: tuple[str, int], msg: Message) -> None:
        # Should we create a socket connector, or just leave this here? eh 
        send_to_socket = socket(AF_INET, SOCK_STREAM)
        try:
            logger.debug(f"egress - Connecting to {addr} from {self.server_id} and sending message {msg.data}")
                
            send_to_socket.connect(addr)
            self.socketInterface.send_message(send_to_socket, msg)
            
            logger.debug(f"egress - Sent message {msg.data} from server {self.server_id} to {addr}")
                
            send_to_socket.close()            
        except ConnectionRefusedError as e:
            # Chance there's a network partition - in this scenario whatyagonnado?
            print(f"Connection refused to {msg.to_server_id} is the server running?")
            # raise e 
        except TimeoutError:
            print(f"Timeout error to {msg.to_server_id} is the server running?")
            self.egress_queue.put(msg)


    def create_append_entries_rpc(self, send_to_server_id: int) -> AppendEntries:

        # > if we have new entries, = if just a heartbeat...if it's less than what we know to be their last log, we r fooked
        assert(self.raft_log.last_log_idx + 1 >= self.other_servers_last_log_idx[send_to_server_id] + 1)
        send_entries = []
        for idx in range(self.other_servers_last_log_idx[send_to_server_id] + 1, self.raft_log.last_log_idx + 1):
            send_entries.append(self.raft_log.entries[idx])

        return AppendEntries(
            leader_term = self.persistent_state.current_term,
            prev_log_idx = self.other_servers_last_log_idx[send_to_server_id],
            prev_log_term = self.raft_log.entries[max(0, self.raft_log.last_log_idx - 1)].term_no,
            leader_commit_idx = self.commit_idx,
            send_entries = send_entries
        )
    def create_request_vote_rpc(self) -> RequestVote:
        return RequestVote(
            candidate_term = self.persistent_state.current_term,
            candidate_id = self.server_id,
            last_log_idx = self.raft_log.last_log_idx,
            last_log_term = self.raft_log.entries[self.raft_log.last_log_idx].term_no
        )
    
    def update_heartbeat(self):
        self.last_heartbeat = time()
        
    def send_heartbeats(self):
        logger.debug(f"send_heartbeats - Sending heartbeats from server {self.server_id}")
        
        for send_to_server_id in self.config.SERVERS:
            if send_to_server_id != self.server_id:
                self.egress_queue.put(
                    Message(
                        from_server_id = self.server_id,
                        to_server_id = send_to_server_id,
                        type = MessageTypes.AppendEntries,
                        data = self.create_append_entries_rpc(send_to_server_id)
                    )
                )
        self.update_heartbeat()

    def reply_to_append_entries_rpc(self, incoming_message: Message):
        assert incoming_message.type == MessageTypes.AppendEntries, "Expected AppendEntries message type"
        
        # Need to check our current term, not our logs or anything else weird...if we got a RequestVote and we reply yes we update term
        if self.persistent_state.current_term > incoming_message.data.leader_term:
            is_successful = False
        else:
            is_successful = self.raft_log.append_entries(
                leader_term = incoming_message.data.leader_term,
                prev_log_idx = incoming_message.data.prev_log_idx,
                prev_log_term = incoming_message.data.prev_log_term,
                send_entries = incoming_message.data.send_entries
            )
        
        if is_successful and incoming_message.data.leader_commit_idx > self.commit_idx:
            self.commit_idx = min(incoming_message.data.leader_commit_idx, self.raft_log.last_log_idx)
            
        resp_rpc = FollowerAppendEntriesResponse(
            success = is_successful,
            curr_log_idx = self.raft_log.last_log_idx,
            prev_log_idx_sent=incoming_message.data.prev_log_idx
        )
        self.egress_queue.put(
            Message(
                from_server_id = self.server_id, 
                to_server_id = incoming_message.from_server_id,
                type = MessageTypes.FollowerAppendEntriesResponse,
                data = resp_rpc
            )
        )
        
        # if is_successful and incoming_message.data.leader_term >= self.persistent_state.current_term:
        #     self.update_heartbeat()

    def reply_to_request_vote_rpc(self, incoming_message: Message):
        assert incoming_message.type == MessageTypes.RequestVote, "Expected RequestVote message type"
        self.reset_election_timeout()
        
        # If it's a request vote, we need to check if we should vote
        # If the term of the candidate is greater than our term, then we should vote

        # RequestVote RPC implementation #1 in Figure 2         
        if self.persistent_state.current_term > incoming_message.data.candidate_term:
            self.egress_queue.put(
                Message(
                    from_server_id = self.server_id,
                    to_server_id = incoming_message.from_server_id,
                    type = MessageTypes.VoteNo,
                    data = None
                )
            )
        
        # RequestVote RPC implementation #2 in Figure 2 
        elif (self.persistent_state.voted_for is None or self.persistent_state.voted_for == incoming_message.from_server_id) and incoming_message.data.last_log_idx >= self.raft_log.last_log_idx:
            self.persistent_state.voted_for = incoming_message.from_server_id
            self.persistent_state.current_term = incoming_message.data.candidate_term
            self.state = self.states.FOLLOWER
            
            self.egress_queue.put(
                Message(
                    from_server_id = self.server_id,
                    to_server_id = incoming_message.from_server_id,
                    type = MessageTypes.VoteYes,
                    data = None
                )
            )

    def update_commit_idx(self, incoming_message: Message):
        assert incoming_message.type == MessageTypes.FollowerAppendEntriesResponse, "Expected FollowerAppendEntriesResponse message type"
        for idx in range(incoming_message.data.prev_log_idx_sent + 1, incoming_message.data.curr_log_idx):
            
            # Basically only for leader to update
            if self.raft_log.entries[idx].term_no == self.persistent_state.current_term and self.client_command_acks[idx] > len(self.config.SERVERS) // 2:
                assert(self.am_leader) # I don't think any other state could get here, but let's check
                self.commit_idx = idx
            else:
                # if we have a gap in the log, we can't commit anything after certainly
                return
            
    def update_follower_ack_counts(self, incoming_message: Message):
        assert incoming_message.type == MessageTypes.FollowerAppendEntriesResponse, "Expected FollowerAppendEntriesResponse message type"
        '''
        Since 
            - The append entries RPC sends prev_log_idx, which is last known
            stable log_idx from follower, and then a list of entries of size n
            - The append entries response sends back prev_log_idx sent and then
            the current index that the follower is in sync with leader (prev_log_idx_sent + n)
            we can basically update all of the client command acks from prev_log_idx_sent to curr_log_idx
            with a +1

        Example:
            - prev_log_idx = 1, so our log is [LogEntry(1, 'x'), LogEntry(1, 'y')]
            - send_entries = [LogEntry(1, 'z'), LogEntry(1, 'a')]
            - prev_log_idx_sent = 1, curr_log_idx = 3
        '''
        assert(incoming_message.type == MessageTypes.FollowerAppendEntriesResponse)

        # The amonut of off-by-one errors in here is too damn high
        for idx in range(incoming_message.data.prev_log_idx_sent + 1, incoming_message.data.curr_log_idx):
            self.client_command_acks[idx] += 1

    def send_request_vote(self):
        for send_to_server_id in self.config.SERVERS:
            if send_to_server_id != self.server_id:
                self.egress_queue.put(
                    Message(
                        from_server_id = self.server_id,
                        to_server_id = send_to_server_id,
                        type = MessageTypes.RequestVote,
                        data = self.create_request_vote_rpc()
                    )
                )
        self.update_heartbeat()

    def start_election(self):
        '''Get some funding'''
        self.persistent_state.current_term += 1
        self.last_election = time()
        self.state = self.states.CANDIDATE
        self.send_request_vote()

    def check_if_im_leader(self):
        if self.received_votes_for_leadership > len(self.config.SERVERS) // 2:
            self.am_leader = True
            self.state = self.states.LEADER
            self.leader_id = self.server_id
            logger.debug(f"check_if_im_leader - I, {self.server_id}, am now the leader")
            self.send_heartbeats()
    
    def reset_election_timeout(self):
        '''
        we don't want 0, but some much lower bound versus our typical timeout...
        if we're debugging set it to 1 tho
        '''
        self.ELECTION_TIMEOUT = random.uniform(
            min(1, self.config.ELECTION_TIMEOUT * 0.1),
            self.config.ELECTION_TIMEOUT
        )
         
    def tick_checks(self):
        '''Always check your clothes after camping'''
        
        # hack - let's not do leader election for now...
        if not self.am_leader and time() > self.last_election + self.ELECTION_TIMEOUT:
            self.start_election()
        elif self.state == self.states.CANDIDATE:
            self.check_if_im_leader()

            
    def ingress_driver(self):
        while True:

            try:
                incoming_message = self.ingress_queue.get(timeout=self.NETWORK_TICK)
                self.update_heartbeat() # we got it from somewhere!
                                             
                logger.debug(f"ingress_driver - Received Message on server {self.server_id} from {incoming_message.from_server_id}: {incoming_message.data}")

                # If CLI
                if incoming_message.from_server_id == self.config.CLI_SERVER_ID:

                    # If from CLI, and I'm the leader, send to all followers
                    if self.am_leader:

                        if incoming_message.type == MessageTypes.DebugPrintLog:
                            print(self.raft_log.entries) 

                        else:
                            # Append entry to my own log!
                            self.raft_log.force_add_new_command(self.persistent_state.current_term, incoming_message.data.command)
                            
                            # we have acknowledged this one ourselves
                            self.client_command_acks[self.raft_log.last_log_idx] = 1

                        for send_to_server_id in self.config.SERVERS:
                            if send_to_server_id != self.server_id:
                                # rpc_out = AppendEntries(
                                #     prev_log_idx = self.raft_log.last_log_idx,
                                #     prev_log_term = self.raft_log.entries[self.raft_log.last_log_idx].term_no,
                                #     send_entries = [LogEntry(self.raft_log.entries[self.raft_log.last_log_idx].term_no, incoming_message.data)]
                                # )
                                # Let's dummy out some data for now, and let's ensure we're sending just the command
                                assert(incoming_message.type in (MessageTypes.ClientCommand, MessageTypes.DebugPrintLog))
                                if incoming_message.type == MessageTypes.ClientCommand:
                                    rpc_out = self.create_append_entries_rpc(send_to_server_id)
                                    self.egress_queue.put(
                                        Message(
                                            from_server_id = self.server_id, 
                                            to_server_id = send_to_server_id,
                                            type = MessageTypes.AppendEntries,
                                            data = rpc_out
                                        )
                                    )                 
                                else:
                                    rpc_out = self.create_append_entries_rpc(send_to_server_id)
                                    self.egress_queue.put(
                                        Message(
                                            from_server_id = self.server_id, 
                                            to_server_id = send_to_server_id,
                                            type = MessageTypes.DebugPrintLog,
                                            data = None
                                        )
                                    )
                        # self.update_heartbeat()


                    # from CLI and I'm not the leader, dumb forward to leader
                    elif not self.am_leader:
                        self.egress_queue.put(
                            Message(
                                from_server_id = self.config.CLI_SERVER_ID,
                                to_server_id = self.leader_id,
                                type=MessageTypes.ClientCommand,
                                data = incoming_message.data
                            )
                        )

                # If from leader
                elif incoming_message.from_server_id == self.leader_id:

                    if incoming_message.type == MessageTypes.DebugPrintLog:
                        print(self.raft_log.entries)       

                    # if from leader, and is append entry
                    elif incoming_message.type == MessageTypes.AppendEntries:
                        self.reply_to_append_entries_rpc(incoming_message)
                    
                    elif incoming_message.type == MessageTypes.RequestVote:
                        self.reply_to_request_vote_rpc(incoming_message)
                    
                    # self.update_heartbeat()

                elif incoming_message.from_server_id in self.config.SERVERS.keys():

                    # If it's from another node

                    # If I'm a leader
                    if self.am_leader:
                        if incoming_message.type == MessageTypes.FollowerAppendEntriesResponse:
                            if incoming_message.data.success:
                                self.update_follower_ack_counts(incoming_message)
                                self.other_servers_last_log_idx[incoming_message.from_server_id] = incoming_message.data.curr_log_idx
                                self.update_commit_idx(incoming_message)
                            else:
                                # Small optimization instead of going backwards - when new node came online (kill process reboot) - we can just send the last log idx
                                # ACTUALLY - the incoming message from a follower would have last_log_idx as the one LEADER sends, so this should be
                                #   the last log idx that the follower has - and follower responds with "curr_log_idx" as it's current
                                # self.other_servers_last_log_idx[incoming_message.from_server_id] = incoming_message.data.prev_log_idx_sent
                                self.other_servers_last_log_idx[incoming_message.from_server_id] = incoming_message.data.curr_log_idx
                                
                    # Or if I'm a candidate
                    elif self.state == self.states.CANDIDATE: 
                        if incoming_message.type == MessageTypes.VoteYes:
                            self.received_votes_for_leadership += 1
                            self.check_if_im_leader()

                        elif incoming_message.type == MessageTypes.VoteNo:
                            pass
                    

                    # In general, if I get an AppendEntries...what happens if I get this from a Candidate as a follower?
                    if incoming_message.type == MessageTypes.AppendEntries and incoming_message.data.term_no >= self.persistent_state.current_term:
                        self.state = self.states.FOLLOWER
                        self.leader_id = incoming_message.from_server_id
                        self.reply_to_append_entries_rpc(incoming_message)
                        # self.update_heartbeat()

                    elif incoming_message.type == MessageTypes.RequestVote:
                        # If we're a follower, and we get a vote request, we need to check if we should vote
                        # If we're a candidate, and we get a vote request, we need to check if we should vote
                        # If we're a leader, and we get a vote request, we need to check if we should vote
                        if self.state == self.states.FOLLOWER:
                            self.reply_to_request_vote_rpc(incoming_message)
                            self.reset_election_timeout()

                        elif self.state == self.states.CANDIDATE:
                            # I already voted for myself
                            self.egress_queue.put(
                                Message(
                                    from_server_id = self.server_id,
                                    to_server_id = incoming_message.from_server_id,
                                    type = MessageTypes.VoteNo,
                                    data = None
                                )
                            )
                        # self.update_heartbeat()
                
                else:
                    raise Exception("Unknown server ID ", incoming_message.from_server_id)                                              


            except Empty:
                self.tick_checks()
                continue
    
    def egress_driver(self):
        while True:
            try:
                out_msg = self.egress_queue.get(timeout=self.NETWORK_TICK)
                to_server_host = self.config.SERVERS[out_msg.to_server_id][0]
                to_server_port = self.config.SERVERS[out_msg.to_server_id][1]
                logger.debug(f"egress_driver - Sending message {out_msg.type} {out_msg.data} from server {self.server_id} to {to_server_host}:{to_server_port}")
                self.egress((to_server_host, to_server_port), out_msg)
                
            except Empty:
                if time() > self.last_heartbeat + self.HEARTBEAT_TICK:
                    self.send_heartbeats() 
    
    def quit_handler(self):
        self.socket.close()
        try:
            self.receiver_thread.join()
            self.ingress_thread.join()
            self.egress_thread.join()
        except Exception as e:
            pass
        
    def start(self):
        self.receiver_thread = Thread(target=self.receiver)
        self.ingress_thread = Thread(target=self.ingress_driver)
        self.egress_thread = Thread(target=self.egress_driver)

        self.receiver_thread.start()
        self.ingress_thread.start()
        self.egress_thread.start()

        self.receiver_thread.join()
        self.ingress_thread.join()
        self.egress_thread.join()


if __name__ == "__main__":

    node_id = input("What Node ID is this? 0-4 >")

    node = RaftNode(int(node_id))    
    try:
        # Start threads
        node.start()

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        node.quit_handler()