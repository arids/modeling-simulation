#!/usr/bin/python

import numpy as np

import airport_conf as conf

from collections import deque
from enum import IntEnum


class EventType(IntEnum):
  PLANE_ARRIVES       = 1 #When a plane enters the flying zone around an airport
  PLANE_LANDED        = 2 #When a plane has landed and is off the runway
  READY_FOR_TAKEOFF = 3 #When the plane is on the runway and is taking off
  PLANE_DEPARTS       = 4 #When the plane has departed and the runway can be used by next plane


class AirportEvent(object):
  def __init__(self, event_type, event_time, airport):
    self.type = event_type
    self.time = event_time
    self.airport = airport #the airport at which this event occurs

  def __cmp__(self, other):
    return cmp(self.time, other.time)


class Airport(object):
  """
  Handles all events at a given airport and schedules new events at other airports"""
  def __init__(self, id, simulator):
    self.id = id
    self.name = "AIRPORT-" + str(id)
    self.sim = simulator
    self.cnt_runways_in_use = 0
    self.q_waiting_to_land = deque()
    self.q_waiting_to_depart = deque()
    #Variables to compute statistics
    self.cnt_waiting_to_land = 0
    self.cnt_waiting_to_depart = 0
    self.total_waiting_time_for_landing = 0
    self.total_waiting_time_for_departing = 0
    self.cnt_landings = 0
    self.cnt_departures = 0



  def handle_event(self, event):
    event_type = event.type
    curr_time = self.sim.get_curr_time()
    self.sim.log(event)
    if event_type == EventType.PLANE_ARRIVES:
      if self.cnt_runways_in_use < conf.num_runways_per_airport:
        self.cnt_runways_in_use += 1
        nxt_event_tuple = (EventType.PLANE_LANDED, curr_time+conf.runway_time_to_land, self.id)
        self.sim.schedule(nxt_event_tuple)
      else:
        self.cnt_waiting_to_land += 1
        self.q_waiting_to_land.appendleft(event)

    elif event_type == EventType.PLANE_LANDED:
      self.cnt_landings += 1
      self.cnt_runways_in_use -= 1
      nxt_event_tuple = (EventType.READY_FOR_TAKEOFF, curr_time+conf.required_time_on_ground, self.id)
      self.sim.schedule(nxt_event_tuple)
      assert self.cnt_runways_in_use >= 0
      self.notify_waiting_planes(curr_time)

    elif event_type == EventType.READY_FOR_TAKEOFF:
      if self.cnt_runways_in_use < conf.num_runways_per_airport:
        self.cnt_runways_in_use += 1
        nxt_event_tuple = (EventType.PLANE_DEPARTS, curr_time+conf.runway_time_to_takeoff, self.id)
        self.sim.schedule(nxt_event_tuple)
      else:
        self.cnt_waiting_to_depart += 1
        self.q_waiting_to_depart.appendleft(event)

    elif event_type == EventType.PLANE_DEPARTS:
      self.cnt_departures += 1
      self.cnt_runways_in_use -= 1
      airport_ids = set(self.sim.get_all_airport_ids())
      airport_ids.remove(self.id)
      airport_ids = list(airport_ids)
      nxt_airport_id = np.random.choice(airport_ids, 1)[0]
      travel_time = self.sim.get_distance(self.id, nxt_airport_id)
      nxt_event_tuple = (EventType.PLANE_ARRIVES, curr_time+travel_time, nxt_airport_id)
      self.sim.schedule(nxt_event_tuple)
      assert self.cnt_runways_in_use >= 0
      self.notify_waiting_planes(curr_time)



  def notify_waiting_planes(self, curr_time):
    """Prefers planes waiting to land over those waiting to depart"""
    if self.cnt_waiting_to_land > 0:
      assert self.cnt_waiting_to_land == len(self.q_waiting_to_land)
      self.cnt_runways_in_use += 1
      self.cnt_waiting_to_land -= 1
      pending_event = self.q_waiting_to_land.pop()
      assert pending_event.type == EventType.PLANE_ARRIVES
      assert curr_time >= pending_event.time
      self.total_waiting_time_for_landing = curr_time - pending_event.time
      nxt_event_tuple = (EventType.PLANE_LANDED, curr_time+conf.runway_time_to_land, self.id)
      self.sim.schedule(nxt_event_tuple)
    elif self.cnt_waiting_to_depart > 0:
      assert self.cnt_waiting_to_depart == len(self.q_waiting_to_depart)
      self.cnt_runways_in_use += 1
      self.cnt_waiting_to_depart -= 1
      pending_event = self.q_waiting_to_depart.pop()
      assert pending_event.type == EventType.READY_FOR_TAKEOFF
      assert curr_time >= pending_event.time
      self.total_waiting_time_for_departing = curr_time - pending_event.time
      nxt_event_tuple = (EventType.PLANE_DEPARTS, curr_time+conf.runway_time_to_takeoff, self.id)
      self.sim.schedule(nxt_event_tuple)