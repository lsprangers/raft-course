# Generic notes
- There's no cluster manager, you have to specify all nodes / ports in commands
    - So there's no autoscaling...and if you want to change majority configuration then idk you're just out of luck

# Lil' Helpers
`cd repos/raft_2025_01/lsprangers-raft/part1`
`python src/client.py --server-port=54321 --server-host=localhost`
`ps -fa | grep python`


# Part 3
- Should we do req/resp, or something like actor model? 
    - Based on actor model + idempotent RPC + how RAFT paper discusses it, we should use Actor model