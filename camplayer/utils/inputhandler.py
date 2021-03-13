#!/usr/bin/python3

import time
import threading

import evdev
import queue

from evdev import ecodes 

class InputMonitor(object):

    def __init__(self, event_type=['release', 'press', 'hold'], scan_interval=2500):
        self._devices = []
        self._event_queue = queue.Queue(maxsize=10)
        self._scan_interval = scan_interval / 1000
        self._event_up = True if 'release' in event_type else False
        self._event_down = True if 'press' in event_type else False
        self._event_hold = True if 'hold' in event_type else False
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor, daemon=True).start()
        self._x=0
        self._y=0
        self._firstClickTime=0
        self._inGrid=True
        self._swipeXstart=0
        self._swipeYstart=0
        self._grabSwipeStartX=False
        self._grabSwipeStartY=False

    def destroy(self):
        """Stop monitoring thread"""

        self._running = False

    def get_events(self):
        """Get queued keyboard events"""

        events = []
        while not self._event_queue.empty():
            event = self._event_queue.get_nowait()
            self._event_queue.task_done()
            events.append(event)
            
        return events

    def _scan_devices(self):
        """Scan for input devices"""

        return [evdev.InputDevice(path) for path in evdev.list_devices()]

    def _monitor(self):
        """Key monitoring thread"""

        last_scan_time = -self._scan_interval
        
        while self._running and threading.main_thread().is_alive():

            if time.monotonic() > last_scan_time + self._scan_interval:
                self._devices = self._scan_devices()
                last_scan_time = time.monotonic()

            # TODO fix
            # Somehow evdev misses button presses in its own loop
            # Looping faster than the expected time between button presses, hides this issue...
            # https://github.com/gvalkov/python-evdev/issues/101
            time.sleep(0.025)

            for device in self._devices:
                try:
                    while True:
                        event = device.read_one()
                        if event:
                            if event.type == evdev.ecodes.EV_KEY:
                                #print(event)
                                if self._event_up and event.code!=evdev.ecodes.BTN_TOUCH and event.value == 0:
                                    self._event_queue.put_nowait(event)
                                elif self._event_down and event.code!=evdev.ecodes.BTN_TOUCH and event.value == 1:
                                    #print("Got a keypress event with code ",event.code)
                                    self._event_queue.put_nowait(event)
                                    #print("***enqueue key down***")
                                elif self._event_hold and event.code!=evdev.ecodes.BTN_TOUCH and event.value == 2:
                                    self._event_queue.put_nowait(event)
                                elif event.code == evdev.ecodes.BTN_TOUCH and event.value==0:
                                    #this is button UP (i.e. release)
                                    #if we got a button up event, there was obviously a button down
                                    #so lets check it its a swipe
                                    #if it is, we'll cancel out the double click timer
                                    #and issue the correspinding command
                                    #print("old x = ",self._swipeXstart)
                                    #print("new x = ",self._x)
                                    if abs(self._x-self._swipeXstart) > 150:
                                        #print("******THIS IS A SWIPE*****")
                                        self._firstClickTime=0
                                        if self._x < self._swipeXstart:
                                            #this is a swipe from right to left (left swipe)
                                            #map this to the right arrow key
                                            ev = evdev.events.InputEvent(event.sec, event.usec, ecodes.EV_KEY, ecodes.KEY_RIGHT, 1)
                                            self._event_queue.put_nowait(ev)
                                        else:
                                            #this is a swipe for left to right (right swipe)
                                            #map this to the left arrow key
                                            ev = evdev.events.InputEvent(event.sec, event.usec, ecodes.EV_KEY, ecodes.KEY_LEFT, 1)
                                            self._event_queue.put_nowait(ev)
                                    #else:
                                    #    print("%%%%%%THIS IS NOT A SWIPE%%%%%%")

                                elif event.code == evdev.ecodes.BTN_TOUCH and event.value==1:
                                    #this is button DOWN (i.e. click)
                                    if self._firstClickTime == 0:
                                        #print("----got a touch----")
                                        
                                        #start a timer for when the click started
                                        #this is used for figuring out if there is a double click
                                        self._firstClickTime=time.perf_counter()

                                        #in case this isn't a double click and instead is a swipe,
                                        #tell the position portion to record where the pointer was
                                        #the next time a position comes in
                                        #this is necessary because when the BTN_TOUCH comes in
                                        #the position hasn't yet been updated so you can't
                                        #tell where the swipe starts
                                        self._grabSwipeStartX=True
                                        self._grabSwipeStartY=True
                                    else:
                                        timeNow=time.perf_counter()
                                        if timeNow-self._firstClickTime < 0.5:
                                            #print("Got a double tap")
                                            self._firstClickTime=0

                                            if self._inGrid:
                                                # We're in a grid, so we're going to full screen a 
                                                # particular stream
                                                if self._x<400 :
                                                    if(self._y<240):
                                                        #print("Upper Left")
                                                        ev = evdev.events.InputEvent(event.sec, event.usec, ecodes.EV_KEY, ecodes.KEY_1, 1)
                                                        self._event_queue.put_nowait(ev)
                                                        #print("***enqueue 1***")
                                                        #del ev
                                                    else:
                                                        #print("Lower Left")
                                                        ev = evdev.events.InputEvent(event.sec, event.usec, ecodes.EV_KEY, ecodes.KEY_3, 1)
                                                        self._event_queue.put_nowait(ev)
                                                        #print("***enqueue 3***")
                                                        #del ev
                                                else:
                                                    if(self._y<240):
                                                        #print("Upper Right")
                                                        ev = evdev.events.InputEvent(event.sec, event.usec, ecodes.EV_KEY, ecodes.KEY_2, 1)
                                                        self._event_queue.put_nowait(ev)
                                                        #print("***enqueue 2***")
                                                        #del ev
                                                    else:
                                                        #print("Lower Right")
                                                        ev = evdev.events.InputEvent(event.sec, event.usec, ecodes.EV_KEY, ecodes.KEY_4, 1)
                                                        self._event_queue.put_nowait(ev)
                                                        #print("***enqueue 4***")
                                                        #del ev
                                                self._inGrid=False
                                            else:
                                                # We're not in a grid, so we're going to go
                                                # back to a grid
                                                ev = evdev.events.InputEvent(event.sec, event.usec, ecodes.EV_KEY, ecodes.KEY_ESC, 1)
                                                self._event_queue.put_nowait(ev)
                                                #print("***enqueue ESC***")
                                                self._inGrid=True
                                                #del ev

                                        else:
                                            self._firstClickTime=timeNow
                                            self._grabSwipeStartX=True
                                            self._grabSwipeStartY=True
                            elif event.type == evdev.ecodes.EV_ABS:
                                if event.code == evdev.ecodes.ABS_X:
                                    self._x = event.value
                                    if self._grabSwipeStartX:
                                        self._swipeXstart=event.value
                                        self._grabSwipeStartX=False
                                        #if self._grabSwipeStartY==False:
                                        #    print("Start of swipe ",self._swipeXstart,",",self._swipeYstart)
                                    #print("Coordinate:",self._x,",",self._y)
                                elif event.code == evdev.ecodes.ABS_Y:
                                    self._y = event.value
                                    if self._grabSwipeStartY:
                                        self._swipeYstart=event.value
                                        self._grabSwipeStartY=False
                                        #if self._grabSwipeStartX==False:
                                        #    print("Start of swipe ",self._swipeXstart,",",self._swipeYstart)
                                    #print("Coordinate: ",self._x,",",self._y)
                            del event
                        else:
                            break
                except BlockingIOError:
                    pass
                except OSError:
                    pass
                except queue.Full:
                    pass

        for device in self._devices:
            try:
                device.close()
            except:
                pass
