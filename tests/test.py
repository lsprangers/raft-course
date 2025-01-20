import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__name__)))

# Debugger needs this
sys.path.append('/Users/lukesprangers/repos/raft_2025_01/lsprangers-raft/part5/')

import unittest
from unittest.mock import patch, MagicMock
from socket import *
from threading import *

from src.raftNet import RaftNode
from src.raftLog import RaftLog
from resources.socketInterface import SocketInterface
from resources.messageInterface import *
from resources.raftConfig import raftConfig
from resources.errorInterface import InvalidCommandError


class TestRaftLeader(unittest.TestCase):

    def setUp(self):
        self.config = raftConfig()
        # Leader
        self.node = RaftNode(server_id=0)
        self.node.quit_handler()

    def test_initialization(self):
        self.assertEqual(self.node.server_id, 0)
        self.assertEqual(self.node.state, self.node.states.LEADER)
        self.assertTrue(self.node.am_leader)
        self.assertEqual(self.node.leader_id, self.config.BOOTSTRAP_LEADER_ID)

    @patch('raftNet.socket')
    def test_create_server_socket(self, mock_socket):
        mock_socket_instance = MagicMock()
        mock_socket.return_value = mock_socket_instance
        sock = self.node.socket
        mock_socket.assert_called_with(AF_INET, SOCK_STREAM)
        mock_socket_instance.bind.assert_called_with((self.node.host, self.node.port))
        mock_socket_instance.listen.assert_called_with(5)
        # sock.close()

    @patch('raftNet.socket')
    def test_receive(self, mock_socket):
        mock_socket_instance = MagicMock()
        mock_socket.return_value = mock_socket_instance
        mock_conn = MagicMock()
        mock_socket_instance.accept.return_value = (mock_conn, ('127.0.0.1', 12345))
        mock_conn.recv.return_value = b'10         {"from_server_id": 1, "to_server_id": 0, "type": "ClientCommand", "data": {"command": "test", "hash": 123456}}'
        
        self.node.socketInterface = MagicMock()
        self.node.socketInterface.recv_message.return_value = Message(from_server_id=1, to_server_id=0, type=MessageTypes.ClientCommand, data=ClientCommand(command="test", hash=123456))
        
        self.node.receive()
        self.node.socketInterface.recv_message.assert_called_with(mock_conn)
        self.assertEqual(self.node.ingress_queue.qsize(), 1)

    def test_start_election(self):
        self.node.start_election()
        self.assertEqual(self.node.state, self.node.states.CANDIDATE)
        self.assertEqual(self.node.current_term, 1)
        self.assertGreaterEqual(self.node.last_election, time() - 1)

    def test_check_if_im_leader(self):
        self.node.received_votes_for_leadership = len(self.config.SERVERS) // 2 + 1
        self.node.check_if_im_leader()
        self.assertTrue(self.node.am_leader)
        self.assertEqual(self.node.state, self.node.states.LEADER)
        self.assertEqual(self.node.leader_id, self.node.server_id)

    def test_reset_election_timeout(self):
        self.node.reset_election_timeout()
        self.assertGreaterEqual(self.node.ELECTION_TIMEOUT, 1)
        self.assertLessEqual(self.node.ELECTION_TIMEOUT, self.config.ELECTION_TIMEOUT)

    @patch('raftNet.random.uniform')
    def test_tick_checks(self, mock_random_uniform):
        mock_random_uniform.return_value = 5
        self.node.tick_checks()
        self.assertEqual(self.node.ELECTION_TIMEOUT, 5)

if __name__ == '__main__':
    unittest.main()