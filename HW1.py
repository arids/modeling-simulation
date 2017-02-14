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
import sys
import numpy as np
import pandas as pd
import argparse

# send standard out to a file
#sys.stdout = open('Simulation_log.txt', 'w')


class Airport:
    """An airport has a limited number of runways (```NUM_RUNWAYS```) for planes to takeoff or land. Each runway can
    only accommodate one plane at a time.

    """
    def __init__(self, env, name, num_runways, required_runway_time, required_time_on_ground):
        self.env = env
        self.name = name
        self.runway = simpy.Resource(env, num_runways)
        self.required_runway_time = required_runway_time
        self.required_time_on_ground = required_time_on_ground

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
            circling_time.loc[(var_num_planes, self.name), 'circling_time'] = self.time_circling

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

    def fly(self):
        """The fly process causes a plane to depart from one airport to another airport and request a runway to land.

        """
        while True:
            # the plane must arrive at the airport and land
            yield self.env.process(self.destination.plane_arrives(self))

            # choose a new airport and calculate flight time
            current_airport = self.destination
            new_dest = np.random.choice(
                [self.airports[i] for i in range(len(self.airports)) if self.airports[i] != self.destination])
            self.destination = new_dest
            flightDist = self.distances[current_airport][new_dest]
            flightTime = int((flightDist / self.speed)  * 60)
            self.num_passengers = np.random.randint(0,200)

            # request the runway and depart to new destination
            yield self.env.process(current_airport.plane_departs(self))

            # fly to new destination
            print('flight time for {} is {} minutes'.format(self.name, flightTime))
            yield self.env.timeout(flightTime)


def main():
    """This is the main execution of the simulation. Here we will create instances of airports and planes.

    """
    # take in the command line arguments
    parser = argparse.ArgumentParser(description='Run an airport simulation')
    parser.add_argument("-planes", type=int, help="number of airplanes", required=False, default=5)
    parser.add_argument("-airports", type=int, help="number of airports", required=False, default=5)
    parser.add_argument("-runways", type=int, help="number of runways at each airport", required=False, default=1)
    parser.add_argument("-run_multiple", type=bool, help="run multiple iterations for different numbers of planes",
                        required=False, default=False)
    parser.add_argument("-simulation_time", type=int, help="number of minutes the simulation should run for",
                        required=False, default=1000)

    args = parser.parse_args()

    num_airports = args.airports
    num_planes = args.planes

    #num_airports = 5
    #num_planes = 50
    #n_runways = 2

    # initialize a dataframe to keep track of the time circling at each airport
    ind = pd.MultiIndex.from_product([np.array(list(range(1,num_planes+1))),
                                        np.array(['A0', 'A1', 'A2', 'A3', 'A4'])])
    global circling_time
    circling_time = pd.DataFrame(columns=['circling_time'], index=ind, data=np.zeros(len(ind)))

    # determine how many simulation runs based off the -run_multiple arg
    if args.run_multiple:
        begin = 1
    else:
        begin = num_planes


    global var_num_planes
    for var_num_planes in range(begin,num_planes+1):
        num_planes = var_num_planes

        # set the random seed in order to make the simulation repeatable
        np.random.seed(0)

        # generate the simpy environment
        env = simpy.Environment()

        # create some airports
        airports = []
        for i in range(num_airports):
            airport = Airport(env, name='A' + str(i), num_runways=args.runways, required_runway_time=10,
                                    required_time_on_ground=15)
            airports.append(airport)

        # create a random distnace matrix for the airport
        distances = np.random.randint(600, 3000, size=(num_airports, num_airports))
        distances = np.triu(distances, 1) + np.triu(distances,1).T
        distances = pd.DataFrame(distances, columns = airports, index = airports)

        # create some planes
        planes = []
        for i in range(num_planes):
            plane = Plane(env, 'plane ' + str(i), airports, distances, np.random.choice(airports), 200,
                          np.random.randint(0,200), 550)
            planes.append(plane)
            env.process(plane.fly())

        # run the simulation
        env.run(until=args.simulation_time)


if __name__ == '__main__':
    main()

