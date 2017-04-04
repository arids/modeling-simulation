#!/usr/bin/python

import numpy as np

from airport_util import calculate_lookhead_matrix


"""
Define configuration parameters here
Change these to run for various configurations
"""
num_runways_per_airport = 5
num_airports = 3
num_airplanes = 1000

distance_min = 600
distance_max = 4000

runway_time_to_land = 30
required_time_on_ground = 100
runway_time_to_takeoff = 30

seed = 1
max_simulation_time = 100000

""" -------------------------------------------"""

np.random.seed(seed)

class SimulatorParams:
  def __init__(self):
    self.distance = self.prepare_distance_matrix()

  def prepare_distance_matrix(self):
    d = np.random.random_integers(distance_min, distance_max, size=(num_airports, num_airports))
    d = d - np.triu(d)
    return (d + d.T)/2

  def get_all_airport_ids(self):
    return range(num_airports)

  def get_distance_matrix(self):
    return self.distance

  def get_distance_between(self, id1, id2):
    return self.distance[id1][id2]


if __name__ == "__main__":
  sp = SimulatorParams()
  dis = sp.prepare_distance_matrix()
  calculate_lookhead_matrix(dis, 3)