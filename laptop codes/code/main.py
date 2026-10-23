# Smart Cabin - main program.
# For now it runs a demo: everyone gets a status, then a few random people change every few seconds.
# Later this file will call the camera, detector and status logic modules instead.

import random
import time

import config
import demo_data
import people
import webpage


def main():
    # Read people, timetable and programmes from the CSV files
    people_list = people.load_people()
    timetable = people.load_timetable()
    programs = people.load_programs()
    sensors = demo_data.sample_sensors()
    history = []

    # Give everyone a starting status
    statuses = {}
    for person in people_list:
        statuses[person["id"]] = demo_data.random_status(person, timetable)

    data = webpage.build_site_data(people_list, timetable, statuses, sensors, history, programs)
    webpage.write_status(data)
    webpage.open_dashboard()
    print("Dashboard opened for", len(people_list), "people. Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(config.DEMO_SECONDS)

            # Change a few random people's status
            for person in random.sample(people_list, config.CHANGES_PER_CYCLE):
                new = demo_data.random_status(person, timetable)
                statuses[person["id"]] = new

                # Keep a short log of changes for the history tables
                history.insert(0, {"time": time.strftime("%H:%M:%S"), "person": person["name"],
                                   "status": new["status"], "source": "demo",
                                   "note": new["reason"] or new["evidence"][0]})
                print(person["name"], "->", new["status"])
            history = history[:50]

            data = webpage.build_site_data(people_list, timetable, statuses, sensors, history, programs)
            webpage.write_status(data)
    except KeyboardInterrupt:
        print("Stopped.")


if __name__ == "__main__":
    main()
