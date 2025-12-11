import machine
import os
import json
import network
from time import sleep
from http_server import Server

CONFIG_FILE = "config.json"

def load_config():
    if CONFIG_FILE in os.listdir():
        with open(CONFIG_FILE) as file:
            return json.load(file)
    return None

def connect(ssid, password) -> bool:
    """Connect to a Wi-Fi hotspot using SSID and password. Returns True if connected successfully; False otherwise."""
    print(ssid, password)
    # Configure network to run in station (client) mode
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    print(network.WLAN(network.STA_IF).scan())
    print("STA active:", sta.active())
    sleep(1)
    sta.connect(ssid, password)
    

    # Check connection status every second for 15s
    for _ in range(15):
        if sta.isconnected():
            print('Connected to', ssid)
            print('IP address:', sta.ifconfig()[0])
            return True
        sleep(1)
    
    # No connection after 15s
    print("Connection failed")
    sta.disconnect()
    sta.active(False) # disable device so it can be later used for AP mode
    return False

def create_ap():
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid='MicroPython', password='Password1234')
    return ap

def server(config_mode=True):
    server = Server(config_mode=config_mode)
    server.listener()
    
config = load_config()
if config:
    # Means there is a config file
    try_connect = connect(config['ssid'], config['password'])
    if try_connect == True:
        # Connection good
        print("Connection good, starting server")
        server(config_mode=False)
    else:
        # Connection bad go to AP mode
        print("Connection bad, starting config mode")
        create_ap()
        server(config_mode=True)
else:
    # No config so just go to config mode
    print("No config file, go to config mode")
    create_ap()
    server(config_mode=True)
    