from fsm import FSM
from server import message_queue, connections, lock
import time
import random

class RaftNode:
    def __init__(self, my_addr, others, election_timeout_range=(4, 10)):
        self.addr = my_addr
        self.others = others
        self.term = 0
        self.voted_for = None
        self.votes_received = set()
        self.pending_msg = None
        self.election_timeout_range = election_timeout_range
        self.reset_election_timeout()
        self.heartbeat_interval = 1
        self.next_heartbeat_time = 0

        self.fsm_leader = FSM("raft:leader", "follower", [
            # Follower
            ("follower", self.timeout_expired, "candidate", self.become_candidate),
            ("follower", self.has_append_entries, "follower", self.handle_append_entries),
            ("follower", self.has_vote_request, "follower", self.handle_vote_request),
            ("follower", self.has_vote, "follower", self.ignore_vote),

            # Candidate
            ("candidate", self.timeout_expired, "follower", self.back_to_follower_due_to_timeout),
            ("candidate", self.received_majority_votes, "leader", self.become_leader),
            ("candidate", self.has_append_entries, "follower", self.handle_append_entries),
            ("candidate", self.has_vote_request, "candidate", self.handle_vote_request),
            ("candidate", self.has_vote, "candidate", self.handle_vote),

            # Leader
            ("leader", self.has_append_entries, "follower", self.handle_append_entries),
            ("leader", self.has_vote_request, "leader", self.ignore_vote_request),
            ("leader", self.has_vote, "leader", self.ignore_vote),
            ("leader", self.time_for_heartbeat, "leader", self.send_heartbeat),
        ])

    def reset_election_timeout(self):
        min_timeout, max_timeout = self.election_timeout_range
        self.election_timeout = time.time() + random.uniform(min_timeout, max_timeout)
        print(f"Election timeout: {self.election_timeout - time.time()} s")

    # ---------- Condiciones ----------

    def timeout_expired(self):
        return time.time() > self.election_timeout

    def received_majority_votes(self):
        return self.fsm_leader.state == "candidate" and len(self.votes_received) > len(self.others) // 2

    def has_append_entries(self):
        if not message_queue.empty():
            addr, msg = message_queue.queue[0]
            if msg.startswith("AppendEntries"):
                _, term = msg.split()
                if int(term) >= self.term:
                    self.pending_msg = (addr, msg)
                    return True
        return False

    def has_vote_request(self):
        if not message_queue.empty():
            addr, msg = message_queue.queue[0]
            if msg.startswith("VoteRequest"):
                _, term, candidate = msg.split()
                term = int(term)
                if term > self.term or (term == self.term and (self.voted_for is None or self.voted_for == candidate)):
                    self.pending_msg = (addr, msg)
                    return True
        return False

    def has_vote(self):
        if not message_queue.empty():
            addr, msg = message_queue.queue[0]
            if msg.startswith("Vote"):
                _, term, voter = msg.split()
                if int(term) == self.term:
                    self.pending_msg = (addr, msg)
                    return True
        return False

    def time_for_heartbeat(self):
        return time.time() >= self.next_heartbeat_time

    # ---------- Acciones ----------

    def become_candidate(self):
        self.term += 1
        self.voted_for = self.addr
        self.votes_received = {self.addr}
        print(f"[Raft] {self.addr} becomes CADIDATE (term {self.term})")
        self.send_to_all(f"VoteRequest {self.term} {self.addr}")
        self.reset_election_timeout()

    def become_leader(self):
        self.next_heartbeat_time = time.time()
        print(f"[Raft] {self.addr} becomes LEADER (term {self.term})")

    def back_to_follower_due_to_timeout(self):
        self.voted_for = None
        self.votes_received = set()
        self.reset_election_timeout()
        print(f"[Raft] {self.addr} reverts to FOLLOWER due to timeout (term {self.term})")

    def handle_append_entries(self):
        addr, msg = self.pending_msg
        _, term = msg.split()
        term = int(term)
        if term > self.term:
            self.term = term
            self.voted_for = None
        message_queue.get()
        self.reset_election_timeout()

    def handle_vote_request(self):
        addr, msg = self.pending_msg
        _, term, candidate = msg.split()
        term = int(term)

        vote_granted = False
        if term > self.term and self.voted_for is None:
            self.voted_for = candidate
            self.send_to(addr, f"Vote {term} {self.addr}")

        message_queue.get()
        self.reset_election_timeout()

    def handle_vote(self):
        addr, msg = self.pending_msg
        _, term, voter = msg.split()
        term = int(term)
        if self.fsm_leader.state == "candidate" and term == self.term:
            self.votes_received.add(voter)
        message_queue.get()
        self.reset_election_timeout()

    def ignore_vote(self):
        print("Ignored Vote")
        message_queue.get()
        self.reset_election_timeout()

    def ignore_vote_request(self):
        print("Ignored VoteRequest")
        message_queue.get()
        self.reset_election_timeout()

    def send_heartbeat(self):
        self.send_to_all(f"AppendEntries {self.term}")
        self.next_heartbeat_time = time.time() + self.heartbeat_interval

    # ---------- Utilidades ----------

    def fire(self):
        self.fsm_leader.fire()

    def is_leader(self):
        return self.fsm_leader.state == "leader"

    def send_to_all(self, msg):
        print(f"<send_to_all> {msg}")
        with lock:
            for conn in connections:
                try:
                    conn.sendall(msg.encode('utf-8'))
                except:
                    pass

    def send_to(self, addr, msg):
        print(f"<send> {msg}")
        with lock:
            for conn in connections:
                try:
                    conn.sendall(msg.encode('utf-8'))
                except:
                    pass

