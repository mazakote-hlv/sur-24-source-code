from machine import UART
from micropyGPS import MicropyGPS
import time

class A9G:
    _connected = False
    _connected_time = 0
    
    def __init__(self, uart_id):
        self.uart = UART(uart_id, 115200, timeout=20)
        self.gps = MicropyGPS(location_formatting='dd')
        self.reset()

    def reset(self):
        return self.command("ATZ", timeout=1000)

    def _expect(self, text, timeout=200):
        time_limit = time.time_ns() + timeout * 1000000
        response = ""
        while (not text in response) and (time.time_ns() < time_limit):
            if self.uart.any():
                response = str(self.uart.readline())
            else:
                time.sleep(0.01)
        return (text in response)
        
    def command(self, command, expect="OK", timeout=20):
        self.write(command + "\r\n")
        return self._expect(text=expect, timeout=timeout)
    
    def write(self, command):
        self.uart.write(command)

    def http_get(self, url):
        self.command(f'AT+HTTPGET="{url}"')

    def sms(self, dest, text):
        self.command("AT+CMGF=1")
        self.command(f'AT+CMGS="{dest}"\r\n{text}{chr(0x1a)}')
                    
    def gps_init(self):
        self.command("AT+GPS=1")
    
    def gps_periodic_update(self, seconds):
        self.command(f"AT+GPSRD={seconds}")       

    def gps_fixed(self):
        return self.gps.fix_type >= 2
    
    def conn_init(self):
        self.command("AT+CMGF=1", timeout=100)
        self.command("AT+CGATT=1", timeout=100)
        self.command('AT+CGDCONT=1,"IP","orangeworld"', timeout=100)
        self.command("AT+CGACT=1,1", timeout=100)

    def is_connected(self):
        now = time.time()
        if now > self._connected_time + 10:
            self._connected = self.command("AT+CIPSTATUS?", expect="INITIAL", timeout=20)
            self._connected_time = now
        return self._connected

    def update(self):
        while self.uart.any():
            buffer = self.uart.read()
            for char in buffer:
                self.gps.update(chr(char))
