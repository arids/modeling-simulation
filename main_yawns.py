#!/usr/bin/python

import math
import numpy as np
import Queue
import sys
import time

import airport_conf as conf

from airport_conf import SimulatorParams
from airport_sim import Airport
from airport_sim import AirportEvent
from airport_sim import EventType
from airport_util import calculate_lookhead_matrix
from airport_util import EventLogger

from collections import defaultdict
from mpi4py import MPI


comm = MPI.COMM_WORLD
rank = comm.Get_rank() #the rank of this process
N = comm.Get_size() #the number of parallel processes
assert conf.num_airports >= N
airports_per_process = int(math.ceil(float(conf.num_airports)/N))

class YawnsSimulator:
  def __init__(self, sim_params):
    self.outgoing_buffer = defaultdict(list) #map from pid to list of event tuples
    self.pq = Queue.PriorityQueue()
    self.sim_params = sim_params
    self.airports = {} #airport objs for this LP
    self.curr_time = 0
    self.la = calculate_lookhead_matrix(sim_params.get_distance_matrix(), N) #lookahead matrix
    self.create_airports()
    self.logger = EventLogger(rank, name="yawns", shard_output_by_lp=True)

  def get_pid(self, airport_id):
    """Returns the logical process id corresponding to the airport_id"""
    return airport_id/airports_per_process

  def create_airports(self):
    airport_ids = self.sim_params.get_all_airport_ids()
    for airport_id in airport_ids:
      #only create the airports this logical process is responsible for
      if self.get_pid(airport_id) == rank:
        self.airports[airport_id] = Airport(airport_id, self)

  def get_all_airport_ids(self):
    return self.sim_params.get_all_airport_ids()

  def get_curr_airport_ids(self):
    """airport_ids managed by the current LP"""
    cur_airport_ids = []
    for airport_id in self.get_all_airport_ids():
      if self.get_pid(airport_id) == rank:
        cur_airport_ids.append(airport_id)
    return cur_airport_ids

  def get_distance(self, airport_id1, airport_id2):
    return self.sim_params.get_distance_between(airport_id1, airport_id2)

  def schedule(self, event_tuple):
    event_type = event_tuple[0]
    event_time = event_tuple[1]
    airport_id = event_tuple[2]
    if self.get_curr_time() > conf.max_simulation_time \
            and event_type == EventType.READY_FOR_TAKEOFF: #this ensures a soft stop
      return
    #If the event is supposed to happen on the same logical process
    #add it to the heap, otherwise add it to the corresponding outgoing queue
    if airport_id in self.airports.keys():
      airport = self.airports[airport_id]
      airport_event = AirportEvent(event_type, event_time, airport)
      self.pq.put(airport_event)
    else:
      pid = self.get_pid(airport_id)
      self.outgoing_buffer[pid].append(event_tuple)

  def get_curr_time(self):
    return self.curr_time

  def log(self, event):
    self.logger.log(event, self.curr_time, rank)


  def exchange_messages(self):
    outgoing_sizes = []
    for pid in xrange(0, N):
      #this LP sends len(self.outgoing_lists[pid]) msgs to LP=pid
      outgoing_sizes.append(len(self.outgoing_buffer[pid]))
    assert outgoing_sizes[rank] == 0 #No messages should be sent from airports in this LP
    outgoing_sizes = np.array(outgoing_sizes)
    incoming_sizes = np.array([0]*N)
    comm.Allreduce(outgoing_sizes, incoming_sizes, op=MPI.SUM)
    #Send outgoing messages asynchronously
    for pid in self.outgoing_buffer.keys():
      if pid == rank:
        continue
      for event_tuple in self.outgoing_buffer[pid]:
        comm.Irsend(np.array(event_tuple), dest=pid)
      self.outgoing_buffer[pid] = [] #clear the list after sending messages
    #Recv incoming messages synchronously and add them to heap
    cnt_expected_recv = incoming_sizes[rank]
    cnt_actual_received = 0
    while cnt_actual_received < cnt_expected_recv:
      incoming_event_tuple = np.array([-1, -1, -1])
      comm.Recv(incoming_event_tuple, source=MPI.ANY_SOURCE)
      cnt_actual_received += 1
      event_type = incoming_event_tuple[0]
      event_time = incoming_event_tuple[1]
      airport_id = incoming_event_tuple[2]
      airport = self.airports[airport_id]
      assert self.get_pid(airport_id) == rank
      airport_event = AirportEvent(event_type, event_time, airport)
      self.pq.put(airport_event)


  def get_lbts(self):
    send_clock = np.array([0]*N)
    recv_clock = np.array([0]*N)
    send_clock[rank] = self.get_curr_time()
    comm.Allreduce(send_clock, recv_clock, op=MPI.SUM)
    recv_clock = recv_clock + self.la[rank]
    recv_clock[rank] = sys.maxint
    return np.min(recv_clock)

  def run(self):
    voteToHalt = False
    lbts = 0
    while not voteToHalt:
      while not self.pq.empty():
        event = self.pq.get()
        if event.time > lbts:
          self.pq.put(event)
          break
        self.curr_time = event.time
        airport = event.airport
        airport.handle_event(event)
      #update clock
      self.curr_time = lbts

      # Barrier sync
      comm.Barrier()
      #Recv messages from prev iteration
      self.exchange_messages()
      comm.Barrier()

      #update lbts
      lbts = self.get_lbts()

      #voteToHalt (find whether simulation should end or not)
      out = np.array([0] * N)
      if self.pq.empty():
        out[rank] = 1 #Im voting to halt
      res = np.array([0] * N)
      comm.Allreduce(out, res, op=MPI.SUM)
      #If heaps at all LP's are empty then voteToHalt
      if np.sum(res) == N:
        voteToHalt=True


  def print_statistics(self):
    """
    Collect stats at LP zero and print them"""
    total_departures = 0
    total_landings = 0
    total_waiting_time = 0
    total_waiting_time_for_departing = 0
    total_waiting_time_for_landing = 0
    for airport in self.airports.values():
      total_waiting_time_for_landing += airport.total_waiting_time_for_landing
      total_waiting_time_for_departing += airport.total_waiting_time_for_departing
      total_waiting_time += airport.total_waiting_time_for_landing +\
                            airport.total_waiting_time_for_departing
      total_landings += airport.cnt_landings
      total_departures += airport.cnt_departures

    stats_recv = np.array([0]*5)
    stats_send = np.array([total_departures, total_landings, total_waiting_time,
                           total_waiting_time_for_departing, total_waiting_time_for_landing])
    comm.Reduce(stats_send, stats_recv, op=MPI.SUM, root=0)

    if rank == 0:
      print "TOTAL DEPARTURES: ", stats_recv[0]
      print "TOTAL_LANDINGS  : ", stats_recv[1]
      print "TOTAL WAIT TIME : ", stats_recv[2]
      print "TOTAL_WAIT_TIME_FOR_DEPARTURES: ", stats_recv[3]
      print "TOTAL_WAIT_TIME_FOR_LANDINGS: ", stats_recv[4]
      print "AVG WAITING TIME: ", float(stats_recv[2])/(stats_recv[0] + stats_recv[1])
      print "(Remember landings were preferred over departures)"


def bootstrap_initial_events(sim):
  """
  Creates the initial events to bootstrap the simulation
  Each LP is responsible for scheduling a subset of all the planes
  This ensures that all initial events are in designated heaps
  and not waiting in any pending send buffers or in transit
  """
  airplanes_per_process = int(conf.num_airplanes/N)
  cnt_planes_for_curr_lp = airplanes_per_process
  #The zeroeth process takes care of the difference
  #(num_airplanes needn't be a multiple of N)
  if rank == 0:
    diff = conf.num_airplanes - (airplanes_per_process * N)
    cnt_planes_for_curr_lp += diff
  cur_airport_ids = sim.get_curr_airport_ids()
  for i in xrange(cnt_planes_for_curr_lp):
    airport_id = np.random.choice(cur_airport_ids, 1)[0]
    init_departure_time = np.random.randint(20, size=1)[0]
    sim.schedule((EventType.READY_FOR_TAKEOFF, init_departure_time, airport_id))


def main():
  sim_params = SimulatorParams()
  sim = YawnsSimulator(sim_params)
  bootstrap_initial_events(sim)

  comm.Barrier() #Make sure everyone is initialized before running the simulation
  start = time.time()
  sim.run()
  end = time.time()

  comm.Barrier()
  #The max time is the process time
  time_send = np.array([end-start])
  time_recv = np.array([0.0])
  comm.Allreduce(time_send, time_recv, op=MPI.SUM)
  if rank == 0:
    print "Simulation ended in ", float(time_recv[0])/N, "seconds"
  sim.print_statistics()


if __name__ == "__main__":
  main()