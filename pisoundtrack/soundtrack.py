
from influxdb import InfluxDBClient, client
from baseutils_phornee import ManagedClass
from baseutils_phornee import Logger
from baseutils_phornee import Config
from datetime import datetime
import math
import struct

class Soundtrack(ManagedClass):

    def __init__(self):
        super().__init__(execpath=__file__)

        self.logger = Logger({'modulename': self.getClassName(), 'logpath': 'log'})
        self.config = Config({'modulename': self.getClassName(), 'execpath': __file__})

        host = self.config['influxdbconn']['host']
        user = self.config['influxdbconn']['user']
        password = self.config['influxdbconn']['password']
        bucket = self.config['influxdbconn']['bucket']

        self.conn = InfluxDBClient(host=host, username=user, password=password, database=bucket)

    @classmethod
    def getClassName(cls):
        return "soundtrack"

    def get_rms(self, block):
        # RMS amplitude is defined as the square root of the
        # mean over time of the square of the amplitude.

        SHORT_NORMALIZE = (1.0 / 32768.0)

        # iterate over the block.
        sum_squares = 0.0
        for sample in block:
            norm_sample = sample * SHORT_NORMALIZE
            sum_squares += norm_sample * norm_sample

        return math.sqrt(sum_squares / block.size) / SHORT_NORMALIZE


    def sensorRead(self):
        """
        Read sensors information
        """
        have_readings = False

        import numpy
        import pyaudio

        pyaud = pyaudio.PyAudio()

        device_name = 'Micrófono (HD USB Camera)'
        device_rate = 0

        info = pyaud.get_host_api_info_by_index(0)
        numdevices = info.get('deviceCount')
        for i in range(0, numdevices):
            device_info = pyaud.get_device_info_by_host_api_device_index(0, i)
            if device_info.get('name') == device_name:
                if (device_info.get('maxInputChannels')) > 0:
                    print("Input Device id {} - {}".format(i, device_info.get('name')))
                else:
                    self.logger.error("Device {} has no input channels.".format(device_name))
            else:
                self.logger.error("Input Device {} not found.".format(device_name))

        stream = pyaud.open(format=pyaudio.paInt16, channels=1, rate=44100, input_device_index=2, input=True)


        while True:
            num_seconds = 0
            max_read = 0
            while num_seconds < 60:
                raws = stream.read(44*1024, exception_on_overflow=False)
                samples = numpy.fromstring(raws, dtype=numpy.int16)
                rms = self.get_rms(samples)
                if rms > max_read:
                    max_read = rms
                #print("{:.2f}".format(self.get_rms(samples)))
                num_seconds += 1

            json_body = [
                {
                    "measurement": "sound",
                    "tags": {
                        "soundid": self.config['id']
                    },
                    "time": datetime.utcnow(),
                    "fields": {
                        "max": float(max_read)
                    }
                }
            ]
            try:
                self.conn.write_points(json_body)

            except Exception as e:
                self.logger.error("RuntimeError: {}".format(e))
                self.logger.error("influxDBURL={} | influxDBToken={}".format(self.config['influxdbconn']['url'],
                                                                             self.config['influxdbconn']['token']))

if __name__ == "__main__":
    sensors_instance = Soundtrack()
    sensors_instance.sensorRead()





