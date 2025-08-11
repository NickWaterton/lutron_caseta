# lutron.py
A python Asyncronous MQTT interface to Lutron Casetta Devices

Uses the LEAP protocol.

## Requirements

Needs a Lutron Bridge or Bridge Pro 2  
Python 3.6 or above only (uses asyncio)

### Packages required  
pylutron-caseta (see https://github.com/gurumitts/pylutron-caseta)
MQTTMixin (pip install https://github.com/NickWaterton/MQTTMixin.git)

## Usage

```
usage: lutron.py [-h] [-t TOPIC] [-T FEEDBACK] [-b BROKER] [-p PORT] [-U USER] [-P PASSWD] [-l LOG] [-J] [-D] [--version] bridgeip

Forward MQTT data to Lutron API

positional arguments:
  bridgeip              Bridge ip Address (default: None)

optional arguments:
  -h, --help            show this help message and exit
  -t TOPIC, --topic TOPIC
                        MQTT Topic to send commands to, (can use # and +) default: /lutron/command)
  -T FEEDBACK, --feedback FEEDBACK
                        Topic on broker to publish feedback to (default: /lutron/feedback)
  -b BROKER, --broker BROKER
                        ipaddress of MQTT broker (default: None)
  -p PORT, --port PORT  MQTT broker port number (default: 1883)
  -U USER, --user USER  MQTT broker user name (default: None)
  -P PASSWD, --passwd PASSWD
                        MQTT broker password (default: None)
  -l LOG, --log LOG     path/name of log file (default: ./lutron.log)
  -J, --json_out        publish topics as json (vs individual topics) (default: False)
  -D, --debug           debug mode
  --version             Display version of this program
```

## Example

```
./lutron.py 192.168.100.141 -b 192.168.100.16
```

Where `192.168.100.141` is the ip address of your bridge, and `192.168.100.16` is the ip address of your MQTT broker

The first time you run the command, you will be prompted to pair with the bridge by pressing the button on the bridge. This will download the neccessary certificates to allow secure communications. You only need to do this the first time you connect.