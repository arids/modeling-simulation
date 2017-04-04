#!/usr/bin/python

import os
import math
import numpy as np
import shutil
import sys

from airport_sim import EventType

"""
Various util methods go here
"""

class EventLogger:
  def __init__(self, rank, name, shard_output_by_lp=False):
    self.shard_output=shard_output_by_lp
    self.name = name
    self.output_dir = os.path.join(os.curdir, self.name)
    if rank == 0:
      self.setup_dir()

  def setup_dir(self):
    if os.path.exists(self.output_dir):
      shutil.rmtree(self.output_dir)
    os.mkdir(self.output_dir)

  def log(self, event, curr_time, rank=0):
    output_path = os.path.join(self.output_dir, 'output_{r}.txt'.format(r=rank))
    with open(output_path, 'a') as output_file:
      eventtype_msg_map = {EventType.PLANE_ARRIVES: "Plane arrives at ",
                           EventType.PLANE_LANDED : "Plane landed at ",
                           EventType.READY_FOR_TAKEOFF: "Plane ready for takeoff from ",
                           EventType.PLANE_DEPARTS: "Plane departing from "}
      line = "{time}: {eventtype_msg} {airport_name}\n".format(
        time=curr_time, eventtype_msg=eventtype_msg_map[event.type],
        airport_name=event.airport.name)
      output_file.write(line)


def calculate_lookhead_matrix(distance, num_processes):
  num_airports = len(distance)
  airports_per_process = int(math.ceil(float(num_airports) / num_processes))
  la = np.zeros((num_processes, num_processes))
  la.fill(sys.maxint)
  for i in xrange(num_airports):
    for j in xrange(num_airports):
      pid1 = i/airports_per_process
      pid2 = j/airports_per_process
      la[pid1][pid2] = min(la[pid1][pid2], distance[i][j])
      la[pid2][pid1] = la[pid1][pid2]
  return la