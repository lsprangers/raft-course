# RAFT Course
This was a course taken with coworkers and peers to strengthen our software design, testing, and architecture skills while also learning about distributed systems

RAFT is an algorithm designed to create consensus on logs across replicas, and the replicas are typically used for creating strongly consistent, fault tolerant, and highly available logs / KV Stores

[The course](https://www.dabeaz.com/raft.html) was headed by David Beazley, and anyone interested should reach out to him for work groups or solo trip!

## Use Cases
The use cases in the wild today are mostly for configuration K-V stores like etcd, DNS, or other systems which require strong consistency over availability 

### Partitioned K-V Store
![alt text](./QuickNDirty.png)

## Goal
The goal of the course was to create a working implementation of [the raft paper](https://raft.github.io/), and then to use it to create a strongly consistent replicated K-V Store powering a web app

### Use Cases
The use cases in the wild today are mostly for configuration K-V stores like etcd, DNS, or other systems which require strong consistency over availability 

#### Partitioned K-V Store
The setup below depicts a hypothetical structure of a web app powered by a partitioned, distributed, strongly consistent (not necessarily always available) K-V Store
![alt text](./QuickNDirty.png)

### Implementation
The majority of the focus was on creating a configurable RAFT cluster that could be wrapped into a Docker image and deployed on a private network. This cluster should have a bootstrapped leader node, and then after that become a self healing cluster with strong consistency.

#### Reads
A major point I didn't understand was serving reads from RAFT followers. 

Followers were mostly meant to ensure fault tolerance and high availability, but we have all of these 
replicas getting sent information...there must be a way to use the up to date ones for reads

[This paper descibes an implementation](https://www.usenix.org/system/files/conference/hotcloud17/hotcloud17-paper-arora.pdf#:~:text=Since%20writes%20are%20not%20guaran%2D%20teed%20to,are%20han%2D%20dled%20only%20by%20the%20leader.) to do this, but it requires another check between the follower accepting
the user request and the leader to ensure their `lastCommitIdx` and `termNo` are the same - i.e. that is has the latest data

#### DNS
At this point we use hardcoded `localhost` values with ports for our nodes for testing, and hardcoded IP addresses for deployment on a private cloud network

#### Autoscaling
Our RAFT cluster does not autoscale, and sits with 2 or 4 replicas, meaning 3 or 5 nodes altogether, for our K-V store
