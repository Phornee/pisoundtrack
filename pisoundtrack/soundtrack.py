""" """
import os
from datetime import datetime
from pathlib import Path
import math

import numpy
import pyaudio

from influxdb_wrapper import influxdb_factory
from log_mgr import Logger
from config_yml import Config

SHORT_NORMALIZE = (1.0 / 32768.0)
INPUT_BLOCK_TIME = 0.10
SILENCE_SAMPLE_LEVEL = 251
MIN_AUDIBLE_LEVEL = 0.00727  # 20 uPascals


class Soundtrack():
    def __init__(self, dry_run: bool = False):
        self.logger = Logger(self.class_name(), 'soundtrack', dry_run=dry_run)
        self.logger.info("Initializing Soundtrack...")
        template_config_path = os.path.join(Path(__file__).parent.resolve(), './config-template.yml')

        self.config = Config(package_name=self.class_name(),
                             template_path=template_config_path,
                             config_file_name="config.yml")

        influx_conn_type = self.config['influxdbconn'].get('type', 'influx')
        self.conn = influxdb_factory(influx_conn_type)
        self.conn.openConn(self.config['influxdbconn'])

    @classmethod
    def class_name(cls):
        return "soundtrack"

    def get_rms(self, block):
        # RMS amplitude is defined as the square root of the
        # mean over time of the square of the amplitude.

        # SHORT_NORMALIZE = (1.0 / 32768.0)
        SHORT_NORMALIZE = (1.0 / 26000.0)

        # iterate over the block.
        sum_squares = 0.0
        for sample in block:
            norm_sample = sample * SHORT_NORMALIZE
            sum_squares += norm_sample * norm_sample

        return math.sqrt(sum_squares / block.size)

    def sensorRead(self):
        """
        Read sensors information
        """
        have_readings = False

        print("Initializing Pyaudio....")
        self.logger.info("Initializing Pyaudio...")
        pyaud = pyaudio.PyAudio()

        device_name = u'WordForum USB: Audio'

        print("Getting devices...")
        info = pyaud.get_host_api_info_by_index(0)
        num_devices = info.get('deviceCount')
        input_device = -1
        for i in range(0, num_devices):
            device_info = pyaud.get_device_info_by_host_api_device_index(0, i)
            print(f"Evaluating device {device_info.get('name')}...")
            if device_info.get('name').startswith(device_name):
                if (device_info.get('maxInputChannels')) > 0:
                    sampling_rate = int(device_info.get('defaultSampleRate'))
                    print(f"Input Device id {i} - {device_info.get('name')}")
                    print(f"Sampling Rate - {sampling_rate}")
                    input_device = i
                    break
                else:
                    self.logger.error(f"Device {device_name} has no input channels.")

        if input_device == -1:
            self.logger.error(f"Input Device {device_name} not found.")
            return -1

        input_frames_per_block = int(sampling_rate * INPUT_BLOCK_TIME)

        stream = pyaud.open(format=pyaudio.paInt16, channels=1, rate=sampling_rate, input_device_index=input_device,
                            input=True, frames_per_buffer=input_frames_per_block)

        while True:
            num_seconds = 0
            max_read = 0
            while num_seconds < 60:
                raw = stream.read(input_frames_per_block, exception_on_overflow=False)
                samples = numpy.frombuffer(raw, dtype=numpy.int16)
                rms = self.get_rms(samples)
                if rms > max_read:
                    max_read = rms
                print("{:.2f}".format(rms))
                num_seconds += 1

            # Decibel conversion
            if MIN_AUDIBLE_LEVEL > max_read:
                decibels = 0.0
            else:
                decibels = 20 * math.log10(max_read/MIN_AUDIBLE_LEVEL)

            self.logger.info(f"Decibels = {decibels}")
            points = [
                {
                    "tags": {
                        "soundid": self.config['id']
                    },
                    "fields": {
                        "max": float(max_read),
                        "max_raw": float(max_read / SHORT_NORMALIZE),
                        "db_raw": 20 * math.log10(max_read),
                        "db": float(decibels)
                    }
                }
            ]

            try:
                self.conn.insert("sound", points)
            except Exception as ex:
                self.logger.error(f"RuntimeError: {ex}")
                url = self.config['influxdbconn']['url']
                token = self.config['influxdbconn']['token']
                self.logger.error(f"influxDBURL={url} | influxDBToken={token}")

if __name__ == "__main__":
    sensors_instance = Soundtrack()
    sensors_instance.sensorRead()





