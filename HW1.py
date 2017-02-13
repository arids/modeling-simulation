"""
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
        self.time_circling = 0

    def plane_arrives(self, plane):
        """A ```plane``` arrives at the airport and requests runway to land. We must update the arrival time
        attribute of the plane in order to keep track of how long the plane spent circling before it landed.


        """
        print('Time {}: {} arrives at airport {}'.format(self.env.now, plane.name, self.name))
        plane.arrival_time = self.env.now
        # request the runway
        with self.runway.request() as request:
            # wait for it to become available
            yield request
            print('Time {}: {} begins landing at airport {}'.format(self.env.now, plane.name, self.name))

            # update the time_circling attribute of the airport
            self.time_circling += self.env.now - plane.arrival_time

            # keep runway occupied while plane is landing
            yield self.env.timeout(self.required_runway_time)
            print('Time {}: {} completes landing at airport {}. It is now being prepared for its next flight'.format(
                self.env.now, plane.name, self.name))

        # now prepare the plane for it's next flight
        yield self.env.process(self.prepare_plane_for_next_flight(plane))

    def prepare_plane_for_next_flight(self, plane):
        """Here the ```plane``` incurs a delay while it is being prepared for the next flight.

        """
        yield self.env.timeout(self.required_time_on_ground)
        print('Time {}: {} is now ready for its next flight'.format(self.env.now, plane.name))

    def plane_departs(self, plane):
        with self.runway.request() as request:
            # request the runway to take off
            yield request

            # take off when the runway is available - occupy the resource for required_runway_time
            print('Time {}: {} using runway to depart {}'.format(self.env.now, plane.name, self.name))
            yield self.env.timeout(self.required_runway_time)

            # the plane has finished using the runway to depart and is now in the air
            print('Time {}: {} has left {} en route to {} carrying {} passengers'.format(
                self.env.now, plane.name, self.name, plane.destination.name, plane.num_passengers))


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
        self.arrival_time = None
        self.in_the_air = False


    def fly(self):
        """The fly process causes a plane to depart from one airport to another airport and request a runway to land.

        """
        while True:
            # the plane must arrive at the airport and land
            yield self.env.process(self.destination.plane_arrives(self))

            # choose a new airport and calculate flight time
            current_airport = self.destination
            new_dest = random.choice(
                [self.airports[i] for i in range(len(self.airports)) if self.airports[i] != self.destination])
            self.destination = new_dest
            flightDist = self.distances[current_airport][new_dest]
            flightTime = int((flightDist / self.speed)  * 60)
            self.num_passengers = random.randint(0,200)

            # request the runway and depart to new destination
            yield self.env.process(current_airport.plane_departs(self))

            # fly to new destination
            print('flight time for {} is {} minutes'.format(self.name, flightTime))
            yield self.env.timeout(flightTime)


def main():
    """This is the main execution of the simulation. Here we will create instances of airports and planes.

    """
    num_airports = 2
    num_planes = 5

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
        plane = Plane(env, 'plane ' + str(i), airports, distances, airports[0], 200, random.randint(0,200), 550)
        planes.append(plane)
        env.process(plane.fly())

    # run the simulation
    env.run(until=1000)

    # look at how much time planes spent circling the different airports
    for airport in airports:
        print('total circling time at airport {} was {} minutes'.format(airport.name, airport.time_circling))


if __name__ == '__main__':
    main()

