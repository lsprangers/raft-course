import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__name__)))

sys.path.append('/Users/lukesprangers/repos/raft_2025_01/lsprangers-raft/part5/')

from resources.errorInterface import InvalidCommandError

class Command:
    def __init__(self):
        self.commands = set(["get", "set", "delete", "snapshot", "restore"])
        self.needs_value = set(["set"])

    def parse_command(self, command) -> list[str]:
        ''' 
        Parse the command to get the key and value
        
        Parameters:
        command (str): The command to parse
        '''
        response = []
        command_list = command.split(" ")
        if len(command_list) < 2:
            # return InvalidCommandError(f"Invalid command {command} - should be [get/set/delete] [key] [optional:value]")
            return InvalidCommandError
        this_command = command_list[0]
        if this_command not in self.commands:
            # return InvalidCommandError(f"Invalid command {this_command} - should be [get/set/delete] [key] [optional:value]")
            return InvalidCommandError
            
        this_key = command_list[1]

        if this_command in self.needs_value:
            if len(command_list) < 3:
                # return InvalidCommandError(f"Invalid command {this_command} - should be [get/set/delete] [key] [optional:value]")
                return InvalidCommandError
            
        this_value = command_list[2] if len(command_list) > 2 else None

        return (this_command, this_key, this_value)