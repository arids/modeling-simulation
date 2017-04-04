#!/usr/bin/python

import Queue
import numpy as np
import time

import airport_conf as conf

from airport_conf import SimulatorParams
from airport_sim import Airport
from airport_sim import AirportEvent
from airport_sim import EventType
from airport_util import EventLogger

class SingleThreadSimulator:
  def __init__(self, sim_params):
    self.pq = Queue.PriorityQueue()
    self.sim_params = sim_params
    self.airports = {}
    self.create_airports()
    self.curr_time = 0
    self.logger = EventLogger(0, name="singlethread", shard_output_by_lp=False)

  def create_airports(self):
    airport_ids = self.sim_params.get_all_airport_ids()
    for airport_id in airport_ids:
      self.airports[airport_id] = Airport(airport_id, self)

  def get_all_airport_ids(self):
    return self.sim_params.get_all_airport_ids()

  def get_distance(self, airport_id1, airport_id2):
    return self.sim_params.get_distance_between(airport_id1, airport_id2)

  def schedule(self, event_tuple):
    event_type = event_tuple[0]
    event_time = event_tuple[1]
    airport = self.airports[event_tuple[2]]
    if self.get_curr_time() > conf.max_simulation_time \
            and event_type == EventType.READY_FOR_TAKEOFF:
      return
    airport_event = AirportEvent(event_type, event_time, airport)
    self.pq.put(airport_event)

  def get_curr_time(self):
    return self.curr_time

  def log(self, event):
    self.logger.log(event, self.curr_time)

  def run(self):
    while not self.pq.empty():
      event = self.pq.get()
      self.curr_time = event.time
      airport = event.airport
      airport.handle_event(event)

  def print_statistics(self):
    total_waiting_time_for_landing = 0
    total_waiting_time_for_departing = 0
    total_waiting_time = 0
    total_landings = 0
    total_departures = 0
    for airport in self.airports.values():
      total_waiting_time_for_landing += airport.total_waiting_time_for_landing
      total_waiting_time_for_departing += airport.total_waiting_time_for_departing
      total_waiting_time += airport.total_waiting_time_for_landing +\
                            airport.total_waiting_time_for_departing
      total_landings += airport.cnt_landings
      total_departures += airport.cnt_departures
    print "TOTAL DEPARTURES: ", total_departures
    print "TOTAL_LANDINGS  : ", total_landings
    print "TOTAL WAIT TIME : ", total_waiting_time
    print "TOTAL_WAIT_TIME_FOR_DEPARTURES: ", total_waiting_time_for_departing
    print "TOTAL_WAIT_TIME_FOR_LANDINGS: ", total_waiting_time_for_landing
    print "AVG WAITING TIME: ", float(total_waiting_time) / (total_departures + total_landings)
    print "(Remember landings were preferred over departures)"


def bootstrap_initial_events(sim):
  airport_ids = sim.get_all_airport_ids()
  #Bootstrap initial events
  for i in xrange(conf.num_airplanes):
    airport_id = np.random.choice(airport_ids, 1)[0]
    init_departure_time = np.random.randint(20, size=1)[0]
    sim.schedule((EventType.READY_FOR_TAKEOFF, init_departure_time, airport_id))


def main():
  sim_params = SimulatorParams()
  sim = SingleThreadSimulator(sim_params)
  bootstrap_initial_events(sim)
  start = time.time()
  sim.run()
  end = time.time()
  print "Simulation ended in ", (end - start), "seconds"
  sim.print_statistics()


if __name__ == "__main__":
  main()