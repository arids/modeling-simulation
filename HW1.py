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


class Airport:
    """An airport has a limited number of runways (```NUM_RUNWAYS```) for planes to takeoff or land. Each runway can
    only accommodate one plane at a time.

    """
    def __init__(self, env, name, num_runways, runway_time_to_land, required_time_on_ground, lat, long):
        self.env = env
        self.name = name
        self.runway = simpy.Resource(env, num_runways)
        self.runway_time_to_land = runway_time_to_land
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
        yield self.env.timeout(self.runway_time_to_land)

    def prepare_plane_for_next_flight(self, plane):
        yield self.env.timeout(self.required_time_on_ground)

    def plane_departs(self, plane):
        pass


class Plane:
    """A plane has an origin, destination, speed, capacity, num_passengers, in_the_air.

    """
    def __init__(self, env, name, origin, destination, capacity, num_passengers, speed):
        self.env = env
        self.name = name
        self.origin = origin
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

                # do something
                print('%s clear to land at airport %s at time %.2f.' % (self.name, self.destination.name, self.env.now))
                yield self.env.process(self.destination.plane_lands(self.name))

                print('%s completed landing at airport %s at time %.2f.' % (self.name, self.destination.name, self.env.now))

            # the plane is unable to fly again until ```required_time_on_ground``` has elapsed
            yield self.env.process(self.destination.prepare_plane_for_next_flight(self.name))
            print('%s is now clear to depart airport %s at time %.2f.' % (self.name, self.destination.name, self.env.now))


def main():
    env = simpy.Environment()
    a1 = Airport(env, 'LAX', 1, 10, 15, 0, 0)
    p1 = Plane(env, 'p1', 'Nowhere', a1, 50, 40, 100)
    env.process(p1.fly())
    env.run(until=100)


if __name__ == '__main__':
    main()

