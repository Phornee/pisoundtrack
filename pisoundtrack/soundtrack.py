
from influxdb import InfluxDBClient, client
from baseutils_phornee import ManagedClass
from baseutils_phornee import Logger
from baseutils_phornee import Config
from datetime import datetime
import math
import struct

SHORT_NORMALIZE = (1.0 / 32768.0)
INPUT_BLOCK_TIME = 0.40

class Soundtrack(ManagedClass):

    def __init__(self):
        super().__init__(execpath=__file__)
        self.logger = Logger({'modulename': self.getClassName(), 'logpath': 'log', 'logname': 'soundtrack'})
        self.logger.info("Initializing Soundtrack...")
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

        return math.sqrt(sum_squares / block.size)

    def get_max(self, block):
        # Ge peak sample normalized to 0..1
        # iterate over the block.
        max_amplitude = 0.0
        for sample in block:
            norm_sample = sample
            if norm_sample > max_amplitude:
                max_amplitude = norm_sample

        return max_amplitude

    def sensorRead(self):
        """
        Read sensors information
        """
        have_readings = False

        import numpy
        import pyaudio

        print("Initializing Pyaudio....")
        self.logger.info("Initializing Pyaudio...")
        pyaud = pyaudio.PyAudio()

        device_name = u'WordForum USB: Audio'
        device_rate = 0

        print("Getting devices...")
        info = pyaud.get_host_api_info_by_index(0)
        num_devices = info.get('deviceCount')
        input_device = -1
        for i in range(0, num_devices):
            device_info = pyaud.get_device_info_by_host_api_device_index(0, i)
            print("Evaluating device {}...".format(device_info.get('name')))
            if device_info.get('name').startswith(device_name):
                if (device_info.get('maxInputChannels')) > 0:
                    sampling_rate = int(device_info.get('defaultSampleRate'))
                    print("Input Device id {} - {}".format(i, device_info.get('name')))
                    print("Sampling Rate - {}".format(sampling_rate))
                    input_device = i
                    break
                else:
                    self.logger.error("Device {} has no input channels.".format(device_name))

        if input_device == -1:
            self.logger.error("Input Device {} not found.".format(device_name))
            return -1

        input_frames_per_block = int(sampling_rate * INPUT_BLOCK_TIME)

        stream = pyaud.open(format=pyaudio.paInt16, channels=1, rate=sampling_rate, input_device_index=input_device,
                            input=True, frames_per_buffer=input_frames_per_block)

        while True:
            num_seconds = 0
            max_read = 0
            while num_seconds < 60:
                raws = stream.read(input_frames_per_block, exception_on_overflow=False)
                samples = numpy.fromstring(raws, dtype=numpy.int16)
                rms = self.get_rms(samples)
                if rms > max_read:
                    max_read = rms
                print("{:.2f}".format(rms))
                # raw_max = self.get_max(samples)
                # if raw_max > max_read:
                #     max_read = raw_max
                # print("{:.2f}".format(raw_max))

                num_seconds += 1

            # Decibel conversion
            silence_raw_level = 0

            if silence_raw_level > max_read:
                decibels = 0
            else:
                # decibels = 20 * math.log10(float(max_read - silence_raw_level) * SHORT_NORMALIZE)
                decibels = 20 * math.log10(max_read/0.00002)

            self.logger.info("Decibels = {}".format(decibels))
            json_body = [
                {
                    "measurement": "sound",
                    "tags": {
                        "soundid": self.config['id']
                    },
                    "time": datetime.utcnow(),
                    "fields": {
                        "max": float(max_read),
                        "max_raw": float(max_read / SHORT_NORMALIZE),
                        "db_raw": 20 * math.log10(max_read),
                        "db": float(decibels)
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





