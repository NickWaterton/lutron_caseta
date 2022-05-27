#!/usr/bin/env python3

'''
Asyncio library for communicating with Lutron caseta devices via Bridge pro, using LEAP protocol
MQTT interface
Based on https://github.com/gurumitts/pylutron-caseta
LEAP CommandType:
    GoToDimmedLevel
    GoToFanSpeed
    GoToLevel
    PressAndHold
    PressAndRelease
    Release
    ShadeLimitLower
    ShadeLimitRaise
    Raise
    Lower
    Stop
24/5/2022 V 1.0.0 N Waterton - Initial Release
'''

import logging
from logging.handlers import RotatingFileHandler
import sys, argparse, os
from datetime import timedelta
import asyncio

from pylutron_caseta.smartbridge import Smartbridge, _LEAP_DEVICE_TYPES

from mqtt import MQTT

__version__ = __VERSION__ = '1.0.0'

class Device():
    '''
    Generic Device Class
    '''

    def __init__(self, device, parent=None):
        self.log = logging.getLogger('Main.'+__class__.__name__)
        self.device = device
        self.parent = parent
        self.loop = asyncio.get_event_loop()
        
    def __call__(self):
        self.log.info('{}: {}, ID: {} value: {}'.format(self.type, self.name, self.device_id, self.current_state))
        self.publish(self.name, self.current_state)
            
    @property
    def name(self):
        return self.device['name']
        
    @property
    def device_id(self):
        return self.device['device_id']
        
    @property
    def type(self):
        return self.device['type']
        
    @property
    def model(self):
        return self.device['model']
        
    @property
    def serial(self):
        return self.device['serial']
        
    @property
    def zone(self):
        return self.device['zone']
        
    @property
    def occupancy_sensors(self):
        return self.device['occupancy_sensors']
        
    @property
    def current_state(self):
        return self.device.get('current_state')
        
    def publish(self, topic, msg):
        if self.parent:
            self.parent._publish(topic, msg)

class LightDimmer(Device):
    '''
    Dimmer callback class
    '''

    def __init__(self, device, parent=None):
        super().__init__(device, parent)
        self.log = logging.getLogger('Main.'+__class__.__name__)

class LightSwitch(Device):
    '''
    Switch callback class
    '''

    def __init__(self, device, parent=None):
        super().__init__(device, parent)
        self.log = logging.getLogger('Main.'+__class__.__name__)
        
class Fan(Device):
    '''
    Switch callback class
    '''

    def __init__(self, device, parent=None):
        super().__init__(device, parent)
        self.log = logging.getLogger('Main.'+__class__.__name__)
        
    @property
    def fan_speed(self):
        return self.device['fan_speed']
        
class Blind(Device):
    '''
    Switch callback class
    '''

    def __init__(self, device, parent=None):
        super().__init__(device, parent)
        self.log = logging.getLogger('Main.'+__class__.__name__)
        
    @property
    def tilt(self):
        return self.device['tilt']

class PicoButton(Device):
    '''
    Pico Devices callback and utility class
    '''
    
    picobuttons = {"Pico1Button":           {0:"Button"},
                   "Pico2Button":           {0:"On", 1:"Off"},
                   "Pico2ButtonRaiseLower": {0:"On", 1:"Off", 2:"Raise", 3:"Lower"},
                   "Pico3Button":           {0:"On", 1:"Fav", 2:"Off"},
                   "Pico3ButtonRaiseLower": {0:"On", 1:"Fav", 2:"Off", 3:"Raise", 4:"Lower"},
                   "Pico4Button":           {0:"1", 1:"2", 2:"3", 3:"4"},
                   "Pico4ButtonScene":      {0:"On", 1:"Off", 2:"Preset 1", 3:"Preset 2"},
                   "Pico4Button2Group":     {0:"Group 1 On", 1:"Group 1 Off 2", 2:"Group 2 On", 3:"Group 2 Off"},
                   "FourGroupRemote":       {0:"Group 1 On", 1:"Group 2 On 2", 2:"Group 3 On", 3:"Group 4 On"}
                  }
    
    def __init__(self, device, parent=None):
        super().__init__(device, parent)
        self.log = logging.getLogger('Main.'+__class__.__name__)
        self.double_click_time = 0.5    #not long enough to capture Raise and lower double click
        self.long_press_time = 1
        self.start = self.loop.time()
        self._long_press_task = None
        if self.type not in self.picobuttons.keys():
            self.log.warning('Adding button type: {}'.format(self.type))
            self.picobuttons[self.type] = {}
            
    def __call__(self, msg):
        if self.current_state != msg:
            self.current_state = msg
        self.log.info('{}: {}, Button: {}({}), action: {}'.format(self.type, self.name, self.button_number, self.button_name, self.current_state_text))
        self.publish('{}/{}'.format(self.name, self.button_number), self.current_state_text)
        self.timing()
            
    @property
    def button_groups(self):
        return self.device['button_groups']
        
    @property
    def button_number(self):
        return self.device['button_number']
         
    @property
    def button_name(self):
        return self.picobuttons[self.type].get(self.button_number, str(self.button_number))
        
    @property
    def current_state(self):
        return super().current_state == 'Press'
        
    @current_state.setter    
    def current_state(self, state):
        self.device['current_state'] = state
        
    @property
    def current_state_text(self):
        return 'ON' if self.current_state else 'OFF'
        
    @property
    def button_name_upper(self):
        return self.button_name.upper()
        
    def button_number_from_name(self, button_name):
        '''
        get button number from button name
        '''
        if isinstance(button_name, int):
            return button_name
        if button_name.isdigit():
            return int(button_name) 
        return self.button_number if self.button_name_upper == button_name.upper() else None
        
    def match(self, button_number):
        '''
        return True if button_number (name or number) matches this button
        '''
        return self.button_number == self.button_number_from_name(button_number)
            
    def timing(self):
        '''
        generate double click and long press events
        '''
        if self.current_state:  #Press
            self._long_press_task = self.loop.create_task(self.long_press())
            if self.loop.time() - self.start <= self.double_click_time:
                self.publish('{}/double'.format(self.name), self.button_name_upper)
            self.start = self.loop.time()
        elif self._long_press_task:
            self._long_press_task.cancel()
            self._long_press_task = None
            
    async def long_press(self):
        await asyncio.sleep(self.long_press_time)
        self.publish('{}/longpress'.format(self.name), self.button_name_upper)
        self._long_press_task = None
        

class Caseta(MQTT):
    '''
    Represents a Lutron Caseta lighting System, with methods for status and issuing commands
    all methods not starting with '_' can be sent as commands to MQTT topic
    `Smartbridge` provides an API for interacting with the Caséta bridge using LEAP Protocol
    '''
    __version__ = __version__
    
    certs = {"keyfile":"caseta.key", "certfile":"caseta.crt", "ca_certs":"caseta-bridge.crt"}

    def __init__(self, bridgeip=None, log=None, **kwargs):
        super().__init__(log=log, **kwargs)
        self.log = log if log is not None else logging.getLogger('Main.'+__class__.__name__)
        self.log.info(f'{__class__.__name__} library v{__class__.__version__}')
        self.bridgeip = bridgeip
        self.bridge = None
        self.loop = asyncio.get_event_loop()
        
    def _setup(self):
        if all([os.path.exists(f) for f in self.certs.values()]):
            self.bridge = Smartbridge.create_tls(self.bridgeip, **self.certs)
            return True
        return False
        
    async def _pair(self):
        from pylutron_caseta.pairing import async_pair
        def _ready():
            self.log.info("Press the small black button on the back of the bridge.")
        try:
            data = await async_pair(self.bridgeip, _ready)
            with open(self.certs["ca_certs"], "w") as cacert:
                cacert.write(data["ca"])
            with open(self.certs["certfile"], "w") as cert:
                cert.write(data["cert"])
            with open(self.certs["keyfile"], "w") as key:
                key.write(data["key"])
            self.log.info(f"Successfully paired with {data['version']}")
            return True
        except Exception as e:
            self.log.exception('Error pairing: {}'.format(e))
        return False
        
    async def _connect(self):
        while not self._setup():
            while not await self._pair():
                self.log.info('Retry pairing...')
                await asyncio.sleep(1)
        
        try:
            await self.bridge.connect()
            self.log.info("Connected to bridge: {}".format(self.bridgeip))
                
            for id, scene in self.bridge.get_scenes().items():
                self.log.info('Found Scene: {} , {}'.format(id, scene)) 
            for device, setting in self.bridge.get_devices().items():
                self.log.debug("Found Device: {} : settings: {}".format(device, setting))
            for type in _LEAP_DEVICE_TYPES.keys():
                self._subscribe(type)

        except Exception as e:
            self.log.exception(e)
            
    def _subscribe(self, type):
        if type == 'sensor':
            for device in self.bridge.get_buttons().values():
                self.log.info("Found {}: {}".format(type, device))
                callback = PicoButton(device, self)
                self.bridge.add_button_subscriber(callback.device_id, callback)
            return
        for device in self.bridge.get_devices_by_domain(type):
            self.log.info("Found {}: {}".format(type, device))
            if type == 'light':
                callback = LightDimmer(device, self)
            elif type == 'switch':
                callback = LightSwitch(device, self)
            elif type == 'fan':
                callback = Fan(device, self)
            elif type == 'cover':
                callback = Blind(device, self)
            else:
                callback = Device(device, self)
            self.bridge.add_subscriber(callback.device_id, callback)
            callback()     #publish current value
            
    async def set_level(self, device_name, value, fade_time=0):
        '''
        Override set_level in Smartbridge to lookup device_id from name, and parse args
        '''
        if isinstance(value, tuple):
            fade_time = int(value[1])
            value = value[0]
        if isinstance(value, str):
            value = 0 if value.upper() == 'OFF' else 100 if value.upper() == 'ON' else int(value)
        self.log.info('Setting: {}, to: {}%, fade time: {} s'.format(device_name, value, fade_time))
        for device_id, device in self.bridge._subscribers.items():
            if device_name == device.name:
                self.log.info("Found Device: {} : settings: {}".format(device_id, device.device))
                await self.bridge.set_value(device_id, value, timedelta(seconds=fade_time))
                return
        self.log.warning('Device: {} NOT FOUND'.format(device_name))
        
    async def _button_action(self, device_name, button_number, action):
        '''
        Will perform action on the button of a pico device with the given device_name.
        :param device_name: device name to click the button on
        :param button_number: integer idicating button number
        :param action one of "PressAndRelease", "PressAndHold", "Release"
        '''
        self.log.info('{} Pico: {}, button: {}'.format(action, device_name, button_number))
        for button_id, picobutton in self.bridge._button_subscribers.items():
            if device_name == picobutton.name and picobutton.match(button_number):
                self.log.debug("Found Pico: {} : settings: {}".format(button_id, picobutton.device))
                self.log.info('Sending Pico: {}, {} button: {}'.format(device_name, action, picobutton.button_name))
                await self.bridge._request(
                    "CreateRequest",
                    f"/button/{button_id}/commandprocessor",
                    {"Command": {"CommandType": action}},
                )
                return
        self.log.warning('Pico: {} button: {} NOT FOUND'.format(device_name, button_number))
        
    async def click(self, device_name, button_number):
        return await self._button_action(device_name, button_number, "PressAndRelease")
        
    async def press(self, device_name, button_number):
        return await self._button_action(device_name, button_number, "PressAndHold")
        
    async def release(self, device_name, button_number):
        return await self._button_action(device_name, button_number, "Release")
        
    async def activate_scene(self, scene_id, *args):
        #scene_id is a string
        scene_id = str(scene_id)
        if scene_id in self.bridge.get_scenes().keys():
            await self.bridge.activate_scene(scene_id)
            self.log.info('Activated scene: {} : {}'.format(scene_id, self.bridge.get_scenes()[scene_id].get('name')))
        else:    
            self.log.warning('Scene id: {} not found'.format(scene_id))
        return 0
        
    async def refresh(self, refresh):
        if refresh == 1:
            return await self.bridge._login()
        
    def _get_command(self, msg):
        '''
        Override MQTT method
        extract command and args from MQTT msg, add device_name to args
        '''
        device_name = msg.topic.split('/')[-2]
        device_name = None if device_name == self._name else device_name
        command, args = super()._get_command(msg)
        if device_name and args:
            if isinstance(args, list):
                args.insert(0, device_name)
            else:
                args = [device_name, args]
        self.log.info('Received command: command: {}, args: {}'.format(command, args))    
        return command, args
        
    def stop(self):
        try:
            self.loop.run_until_complete(self._stop())
        except RuntimeError:
            self.loop.create_task(self._stop())
        
    async def _stop(self):
        '''
        put shutdown routines here
        '''
        await super()._stop()
        if self.bridge is not None:
            await self.bridge.close()
        
    def _publish(self, topic=None, message=None):
        if message is not None:
            super()._publish(topic, message)
        
    async def _publish_command(self, command, args=None):
        await super()._publish_command(command, args)
        
        
def parse_args():
    
    #-------- Command Line -----------------
    parser = argparse.ArgumentParser(
        description='Forward MQTT data to Lutron API')
    parser.add_argument(
        'bridgeip',
        action='store',
        type=str,
        default=None,
        help='Bridge ip Address (default: %(default)s)')
    parser.add_argument(
        '-t', '--topic',
        action='store',
        type=str,
        default="/lutron/command",
        help='MQTT Topic to send commands to, (can use # '
             'and +) default: %(default)s)')
    parser.add_argument(
        '-T', '--feedback',
        action='store',
        type=str,
        default="/lutron/feedback",
        help='Topic on broker to publish feedback to (default: '
             '%(default)s)')
    parser.add_argument(
        '-b', '--broker',
        action='store',
        type=str,
        default=None,
        help='ipaddress of MQTT broker (default: %(default)s)')
    parser.add_argument(
        '-p', '--port',
        action='store',
        type=int,
        default=1883,
        help='MQTT broker port number (default: %(default)s)')
    parser.add_argument(
        '-U', '--user',
        action='store',
        type=str,
        default=None,
        help='MQTT broker user name (default: %(default)s)')
    parser.add_argument(
        '-P', '--passwd',
        action='store',
        type=str,
        default=None,
        help='MQTT broker password (default: %(default)s)')
    parser.add_argument(
        '-l', '--log',
        action='store',
        type=str,
        default="./lutron.log",
        help='path/name of log file (default: %(default)s)')
    parser.add_argument(
        '-J', '--json_out',
        action='store_true',
        default = False,
        help='publish topics as json (vs individual topics) (default: %(default)s)')
    parser.add_argument(
        '-D', '--debug',
        action='store_true',
        default = False,
        help='debug mode')
    parser.add_argument(
        '--version',
        action='version',
        version="%(prog)s ({})".format(__version__),
        help='Display version of this program')
    return parser.parse_args()
    
def setup_logger(logger_name, log_file, level=logging.DEBUG, console=False):
    try: 
        l = logging.getLogger(logger_name)
        formatter = logging.Formatter('[%(asctime)s][%(levelname)5.5s](%(name)-20s) %(message)s')
        if log_file is not None:
            fileHandler = logging.handlers.RotatingFileHandler(log_file, mode='a', maxBytes=10000000, backupCount=10)
            fileHandler.setFormatter(formatter)
        if console == True:
            #formatter = logging.Formatter('[%(levelname)1.1s %(name)-20s] %(message)s')
            streamHandler = logging.StreamHandler()
            streamHandler.setFormatter(formatter)

        l.setLevel(level)
        if log_file is not None:
            l.addHandler(fileHandler)
        if console == True:
          l.addHandler(streamHandler)
             
    except Exception as e:
        print("Error in Logging setup: %s - do you have permission to write the log file??" % e)
        sys.exit(1)
            
if __name__ == "__main__":
    arg = parse_args()
    
    if arg.debug:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    #setup logging
    log_name = 'Main'
    setup_logger(log_name, arg.log, level=log_level,console=True)
    setup_logger('pylutron_caseta', arg.log, level=log_level,console=True)

    log = logging.getLogger(log_name)
    
    log.info("*******************")
    log.info("* Program Started *")
    log.info("*******************")
    
    log.debug('Debug Mode')

    log.info("{} Version: {}".format(sys.argv[0], __version__))

    log.info("Python Version: {}".format(sys.version.replace('\n','')))
    
    
    loop = asyncio.get_event_loop()
    loop.set_debug(arg.debug)
    try:
        if arg.broker:
            r = Caseta( arg.bridgeip,
                        ip=arg.broker,
                        port=arg.port,
                        user=arg.user,
                        password=arg.passwd,
                        pubtopic=arg.feedback,
                        topic=arg.topic,
                        name="caseta",
                        json_out=arg.json_out,
                        #log=log
                        )
            asyncio.gather(r._connect(), return_exceptions=True)
            loop.run_forever()
        else:
            r = Caseta(arg.bridgeip, log=log)
            log.info(loop.run_until_complete(r._connect()))
            
    except (KeyboardInterrupt, SystemExit):
        log.info("System exit Received - Exiting program")
        if arg.broker:
            r.stop()
        
    finally:
        pass
