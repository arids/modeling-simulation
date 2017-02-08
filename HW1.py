"""
Practice putting this code on GIT


Scenario:
  We have 5 airports. The airports are each a certain distance away from each other.
  Planes should travel between the different airports. Planes should have attributes such as speed and capacity.
  For each flight, the number of passengers and destination of the flight should be selected from
  some random distribution.

  Keep stats on the number of passengers arriving and departing from each airport. Also track the
  sum(time circling airport) for each airport

"""

import simpy
import random
import numpy as np
import pandas as pd


class Airport:
    """An airport has a limited number of runways (```NUM_RUNWAYS```) for planes to takeoff or land. Each runway can
    only accommodate one plane at a time.

    """
    def __init__(self, env, name, num_runways, required_runway_time, required_time_on_ground, lat, long):
        self.env = env
        self.name = name
        self.runway = simpy.Resource(env, num_runways)
        self.required_runway_time = required_runway_time
        self.required_time_on_ground = required_time_on_ground
        self.lat = lat
        self.long = long

        # initialize some attributes to keep track of metrics at the airport
        self.num_passengers_arrived = 0
        self.num_passengers_departed = 0

    def plane_arrives(self, plane):
        """The arrival process takes a ```plane``` and tries to schedule it for landing

        """
        pass

    def plane_lands(self, plane):
        """The landing process takes a ```plane```  and XXXXXX"""
        yield self.env.timeout(self.required_runway_time)

    def prepare_plane_for_next_flight(self, plane):
        yield self.env.timeout(self.required_time_on_ground)

    def plane_departs(self, plane):
        yield self.env.timeout(self.required_runway_time)


class Plane:
    """A plane has an origin, destination, speed, capacity, num_passengers, in_the_air.

    """
    def __init__(self, env, name, airports, distances, destination, capacity, num_passengers, speed):
        self.env = env
        self.name = name
        self.airports = airports
        self.distances = distances
        self.destination = destination
        self.capacity = capacity
        self.num_passengers = num_passengers
        self.speed = speed
        self.in_the_air = False

    def fly(self):
        """The fly process causes a plane to depart from one airport to another airport and request a runway to land.

        """
        while True:
            print('%s arrives at airport %s at time %.2f.' % (self.name, self.destination.name, self.env.now))
            with self.destination.runway.request() as request:
                # wait for access
                yield request

                # land
                print('%s clear to land at airport %s at time %.2f.' % (self.name, self.destination.name, self.env.now))
                yield self.env.process(self.destination.plane_lands(self.name))

                print('%s is done with runway at airport %s at time %.2f.' % (self.name, self.destination.name, self.env.now))

            # the plane is unable to fly again until ```required_time_on_ground``` has elapsed
            yield self.env.process(self.destination.prepare_plane_for_next_flight(self.name))
            #print('%s is now clear to depart airport %s at time %.2f.' % (self.name, self.destination.name, self.env.now))

            # choose a new airport and calculate flight time
            current_airport = self.destination
            new_dest = random.choice(
                [self.airports[i] for i in range(len(self.airports)) if self.airports[i] != self.destination])
            self.destination = new_dest
            flightDist = self.distances[current_airport][new_dest]
            flightTime = flightDist / self.speed
            self.num_passengers = random.randint(0,200)

            # request the runway to take off
            with current_airport.runway.request() as request:
                # wait for access
                yield request

                # take off
                print('{} using runway to depart {} at time {}.'.format(
                    self.name, current_airport.name, self.env.now))
                yield self.env.process(current_airport.plane_departs(self.name))

            # fly to new destination
            print('{} has left {} en route to {} carrying {} passengers at time {}. Flight time is {} minutes'.format(
                self.name, current_airport.name, new_dest.name, str(self.num_passengers), self.env.now, str(flightTime)))
            yield self.env.timeout(flightTime)


def main():
    """This is the main execution of the simulation. Here we will create instances of airports and planes.

    """
    num_airports = 5
    num_planes = 4

    env = simpy.Environment()

    # create some airports
    airports = []
    for i in range(num_airports):
        airports.append(Airport(env, 'A' + str(i), 1, 10, 15, None, None))

    # create a random distnace matrix for the airport
    distances = np.random.randint(600, 3000, size=(num_airports, num_airports))
    distances = np.triu(distances, 1) + np.triu(distances,1).T
    distances = pd.DataFrame(distances, columns = airports, index = airports)

    # create some planes
    planes = []
    for i in range(num_planes):
        plane = Plane(env, 'plane ' + str(i), airports, distances, airports[0], 200, random.randint(0,200), 550/60)
        planes.append(plane)
        env.process(plane.fly())

    # run the simulation
    env.run(until=100)


if __name__ == '__main__':
    main()

