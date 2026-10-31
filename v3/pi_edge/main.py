# Smart Cabin edge device - run it on the Raspberry Pi:   sudo python3 main.py
#   start at every boot:                                   sudo python3 main.py --autostart
#   on Windows / any computer that is not a Pi:            python main.py --server https://localhost:8080
#     it runs as usual without the Pi's hardware: camera = the webcam (or --picture photo.jpg, or --no-webcam),
#     card reader = the "Tap card" box on the device page, LED = its colour on the page.
#     --serial SIM-2 --port 8001 pretends to be a second device. --sim does the same on a real Pi.
#
# What it does:
#   1. installs what is missing, turns SPI on, gets the models (install.py)
#   2. starts one thread per job:
#        rfid     : card taps (in / out, or linking a card during registration)
#        vision   : one picture every 5 s -> headcount + face -> presence
#        presence : re-checks the in / out timeouts every second
#        server   : hello + a report every 5 s to the laptop server
#        discovery: listens for the server's announcement, so the device finds the server by itself
#   3. serves this device's page on port 8000 (web.py)

import os
import sys
import threading

import settings
import install


def make_autostart():
    # Two services that start at every boot and restart by themselves if they ever stop:
    #   smartcabin           : this app
    #   smartcabin-blackbox  : the black box (blackbox.py), which records the board's health
    service = ("[Unit]\nDescription=Smart Cabin edge device\nAfter=network-online.target\nWants=network-online.target\n\n"
               "[Service]\nWorkingDirectory=" + settings.FOLDER + "\nExecStart=" + sys.executable + " "
               + os.path.join(settings.FOLDER, "main.py") + "\nRestart=always\nRestartSec=5\nUser=root\n\n"
               "[Install]\nWantedBy=multi-user.target\n")
    with open("/etc/systemd/system/smartcabin.service", "w") as f:
        f.write(service)
    os.system("systemctl daemon-reload && systemctl enable --now smartcabin.service")
    import blackbox
    blackbox.install()
    print("Done: the app and the black box start at every boot.")
    print("  App log:          sudo journalctl -u smartcabin -f")
    print("  Stop the app:     sudo systemctl stop smartcabin   (stop autostart: sudo systemctl disable --now smartcabin)")
    print("  Black box report: python3 blackbox.py --report")


def on_tap(card_id):
    # Every card tap goes to the registration first (if it is waiting for a card), else to presence
    import person_data
    import presence
    import registration
    import server_link
    import vision
    from logbook import log
    if registration.card_tapped(card_id):
        log.info("card %s taken by the registration", card_id)
        return
    if person_data.card_tapped(card_id, server_link.call):    # "Add another RFID card" was waiting for it
        return
    log.info("card tap: %s", presence.card_tapped(card_id))
    vision.wake(card_tap=True)


def on_card_left(card_id):
    import buzzer
    import led
    from logbook import log
    log.warning("a card has been left on the reader")
    buzzer.beep("warning")
    led.flash("red", 0.25, times=2)


def start_thread(name, target, *args):
    def run():
        from logbook import log
        try:
            target(*args)
        except Exception as problem:                    # a part that crashes is reported; the rest keeps running
            import shared
            shared.set_part(name, False, "stopped: " + str(problem))
            log.exception("thread %s stopped", name)
    threading.Thread(target=run, name=name, daemon=True).start()


def main():
    if settings.ON_PI and not settings.SIMULATE and os.geteuid() != 0:
        sys.exit("Run it with sudo (the LED and installing need it):  sudo python3 main.py")
    if "--autostart" in sys.argv:
        install.run()
        make_autostart()
        return
    install.run()
    if not install.spi_ready():
        sys.exit("SPI (for the card reader" + (" and, on a Pi 5, the NeoPixel" if settings.IS_PI5 else "")
                 + ") was off and is now on. Restart the Pi (sudo reboot) and run this again.")

    import buzzer
    import identity
    import led
    import presence
    import rfid
    import server_link
    import shared
    import vision
    import web
    from logbook import log

    log.info("Smart Cabin edge device starting: %s, serial %s", identity.model(), identity.serial())
    if settings.SIMULATE:
        log.info("no Pi hardware on this computer (%s): the software runs as usual; card reader and LED are on the "
                 "device page, the camera is %s", settings.COMPUTER,
                 "the --picture file" if settings.TEST_PICTURE_GIVEN else "the webcam, if there is one" if settings.USE_WEBCAM else "off (--no-webcam)")
    shared.update(device=identity.load().get("device", ""))
    led.start()
    led.show("red")
    buzzer.start()
    try:
        rfid.start()
    except Exception as problem:
        shared.set_part("rfid", False, str(problem))
    start_thread("rfid", rfid.loop, on_tap, on_card_left)
    start_thread("vision", vision.loop)
    start_thread("presence", presence.loop)
    start_thread("server", server_link.loop)
    start_thread("discovery", server_link.listen)          # finds the server by its announcement
    try:
        web.serve()
    except OSError as problem:
        sys.exit("The device page could not start on port " + str(settings.PAGE_PORT) + ": " + str(problem)
                 + " - is the program already running?")
    except KeyboardInterrupt:
        led.show("off")
        print("Stopped.")


if __name__ == "__main__":
    main()
