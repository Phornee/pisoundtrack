""" Decibels calculator utitlty class """
import os
from pathlib import Path
import math
import logging

import numpy
import pyaudio

from influxdb_wrapper import influxdb_factory
from config_yml import Config

SHORT_NORMALIZE = (1.0 / 32768.0)
INPUT_BLOCK_TIME = 0.10
SILENCE_SAMPLE_LEVEL = 251
MIN_AUDIBLE_LEVEL = 0.00727  # 20 uPascals


class Soundtrack():
    """ Samples the sound using a microphone, calculates Decibels, and output them to an influx db.
    """
    def __init__(self):
        self.logger = logging.getLogger()
        self.logger.info("Initializing Soundtrack...")
        template_config_path = os.path.join(Path(__file__).parent.resolve(), './config-template.yml')

        self.config = Config(package_name=self.class_name(),
                             template_path=template_config_path,
                             config_file_name="config.yml")

        influx_conn_type = self.config['influxdbconn'].get('type', 'influx')
        self.conn = influxdb_factory(influx_conn_type)
        self.conn.open_conn(self.config['influxdbconn'])

    @classmethod
    def class_name(cls):
        """ class name """
        return "soundtrack"

    def get_rms(self, block) -> float:
        """ Calculates RMS for a block of samples
            RMS amplitude is defined as the square root of the
            mean over time of the square of the amplitude.
        Args:
            block (bytes): Raw samples
        Returns:
            _type_: _description_
        """
        # SHORT_NORMALIZE = (1.0 / 32768.0)
        SHORT_NORMALIZE = (1.0 / 26000.0)

        # iterate over the block.
        sum_squares = 0.0
        for sample in block:
            norm_sample = sample * SHORT_NORMALIZE
            sum_squares += norm_sample * norm_sample

        return math.sqrt(sum_squares / block.size)

    def open_device(self, device_name):
        """ Open an input device stream """
        self.logger.info("Initializing Pyaudio...")
        pyaud = pyaudio.PyAudio()

        self.logger.info("Getting devices...")
        info = pyaud.get_host_api_info_by_index(0)
        num_devices = info.get('deviceCount')
        input_device = -1
        for i in range(0, num_devices):
            device_info = pyaud.get_device_info_by_host_api_device_index(0, i)
            self.logger.debug("Evaluating device %s...", device_info.get('name'))
            if device_info.get('name').startswith(device_name):
                if (device_info.get('maxInputChannels')) > 0:
                    sampling_rate = int(device_info.get('defaultSampleRate'))
                    self.logger.debug("Input Device id %i - %s", i , device_info.get('name'))
                    self.logger.debug("Sampling Rate - %s", sampling_rate)
                    input_device = i
                    break
                self.logger.error("Device %s has no input channels.", device_name)

        if input_device == -1:
            self.logger.error("Input Device %s not found.", device_name)
            return None, 0

        input_frames_per_block = int(sampling_rate * INPUT_BLOCK_TIME)

        stream = pyaud.open(format=pyaudio.paInt16, channels=1, rate=sampling_rate, input_device_index=input_device,
                            input=True, frames_per_buffer=input_frames_per_block)
        return stream, input_frames_per_block

    def microphone_listen(self):
        """
        Read sensors information
        """
        device_name = 'WordForum USB: Audio'
        stream, input_frames_per_block= self.open_device(device_name)

        if not stream:
            return

        while True:
            num_seconds = 0
            max_read = 0
            while num_seconds < 60:
                raw = stream.read(input_frames_per_block, exception_on_overflow=False)
                samples = numpy.frombuffer(raw, dtype=numpy.int16)
                rms = self.get_rms(samples)
                if rms > max_read:
                    max_read = rms
                self.logger.debug("%0.2f", rms)
                num_seconds += 1

            # Decibel conversion
            if MIN_AUDIBLE_LEVEL > max_read:
                decibels = 0.0
            else:
                decibels = 20 * math.log10(max_read/MIN_AUDIBLE_LEVEL)

            self.logger.info("Decibels = %i", decibels)
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
                self.logger.error("RuntimeError: %s", ex)
                url = self.config['influxdbconn']['url']
                token = self.config['influxdbconn']['token']
                self.logger.error("influxDBURL=%s | influxDBToken=%s", url, token)
