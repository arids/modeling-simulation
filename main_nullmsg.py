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

class NullMessageSimulator:
  def __init__(self, sim_params):
    self.incoming_buffer = defaultdict(Queue.PriorityQueue) #incoming queues
    self.pq = Queue.PriorityQueue()
    self.sim_params = sim_params
    self.airports = {} #airport objs for this LP
    self.curr_time = 0
    self.la = calculate_lookhead_matrix(sim_params.get_distance_matrix(), N) #lookahead matrix
    self.create_airports()
    self.logger = EventLogger(rank, name="nullmsg", shard_output_by_lp=True)

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
    airport_id = event_tuple[2] #this is the destination airport_id
    if self.get_curr_time() > conf.max_simulation_time \
            and event_type == EventType.READY_FOR_TAKEOFF: #this ensures a soft stop
      return
    #If the event is supposed to happen on the same logical process
    #add it to the heap, otherwise send it right away
    if airport_id in self.airports.keys():
      airport = self.airports[airport_id]
      airport_event = AirportEvent(event_type, event_time, airport, rank)
      self.pq.put(airport_event)
    else:
      pid = self.get_pid(airport_id)
      event_tuple_with_src = event_tuple + tuple([rank])
      comm.Irsend(np.array(event_tuple_with_src), dest=pid)

  def get_curr_time(self):
    return self.curr_time

  def log(self, event):
    self.logger.log(event, self.curr_time, rank)

  def send_null_msg(self, pid):
    null_msg_tuple = (EventType.NULL_MSG, int(self.get_curr_time() + self.la[rank][pid]), -1, rank)
    comm.Irsend(np.array(null_msg_tuple), dest=pid)

  def is_any_empty(self):
    result = False
    for pid in xrange(N):
      if pid == rank:
        continue
      result = result or self.incoming_buffer[pid].empty()
    return result

  def run(self):
    while self.get_curr_time() <= conf.max_simulation_time + 2*conf.distance_max:
      if self.get_curr_time() == 0:
        for pid in xrange(N):
          if pid == rank:
            continue
          self.send_null_msg(pid)

      #Recv messages if any of the incoming queues is empty
      while self.is_any_empty():
        msg = np.array([-1, -1, -1, -1])
        # Wait for messages
        comm.Recv(msg, source=MPI.ANY_SOURCE)
        # Add the message to local heap
        event_type = msg[0]
        event_time = msg[1]
        airport_id = msg[2]
        source_pid = msg[3]
        airport = None
        #print msg
        if event_type != EventType.NULL_MSG:
          airport = self.airports[airport_id]
        airport_event = AirportEvent(event_type, event_time, airport, source_pid)
        self.pq.put(airport_event)
        self.incoming_buffer[source_pid].put(airport_event)

      event = self.pq.get()
      if event.source_pid != rank:
        self.incoming_buffer[event.source_pid].get()

      old_time = self.get_curr_time()
      self.curr_time = max(self.curr_time, event.time)
      if event.type != EventType.NULL_MSG:
        airport = event.airport
        airport.handle_event(event)

      if self.get_curr_time() - old_time > 0:
        for pid in xrange(N):
          if pid == rank:
            continue
          #TODO: also don't send a null message to the process on which the next
          #TODO: event got scheduled. Could return next_airport_id from handle_event
          self.send_null_msg(pid)



  def print_statistics(self):
    """
    Collect stats at LP zero and print them"""
    total_departures = 0
    total_landings = 0
    total_waiting_time = 0
    total_waiting_time_for_departing = 0
    total_waiting_time_for_landing = 0
    total_passengers_arriving = 0
    for airport in self.airports.values():
      total_waiting_time_for_landing += airport.total_waiting_time_for_landing
      total_waiting_time_for_departing += airport.total_waiting_time_for_departing
      total_waiting_time += airport.total_waiting_time_for_landing +\
                            airport.total_waiting_time_for_departing
      total_landings += airport.cnt_landings
      total_departures += airport.cnt_departures
      total_passengers_arriving += airport.cnt_passengers_arriving

    stats_recv = np.array([0]*6)
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
      print "TOTAL PASSENGERS ARRIVING: ", stats_recv[5]
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
  sim = NullMessageSimulator(sim_params)
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