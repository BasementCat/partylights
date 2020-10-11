import os
import glob
import logging
import time
import subprocess
import re

from dmxpy.DmxPy import DmxPy


logger = logging.getLogger(__name__)
hexint = lambda v: int(v, 16)


class _DMXSink:
    def __init__(self):
        self.data = {}

    def setChannel(self, chan, value):
        self.data[chan] = value

    def render(self):
        logger.debug("DMX OUT: %s", self.data)
        self.data = {}


class DMXDevice:
    def __init__(self, spec):
        self.spec = spec
        self.impl = None
        self.last_attempt = None
        self.last_send = None
        self.data = {}

    @property
    def dmx_impl(self):
        if self.impl is False:
            return None

        if self.impl is None:
            if self.spec == 'sink':
                # Literally do nothing
                self.impl = False
                return None
            elif self.spec == 'vsink':
                self.impl = _DMXSink()
            else:
                if self.last_attempt is None or time.time() - self.last_attempt > 1:
                    self.last_attempt = time.time()
                    if not self.spec:
                        logger.error("No DMX device configured")
                        self.impl = False
                        return None

                    try:
                        self.impl = DmxPy(self._find_device_file(self.spec))
                    except:
                        logger.error("Can't open DMX device %s", self.spec, exc_info=True)

        return self.impl

    @classmethod
    def _find_device_file__linux(cls, vendor, product):
        if not os.path.exists('/sys') or not os.path.isdir('/sys'):
            return None
        for dev in glob.glob('/sys/bus/usb-serial/devices/*'):
            devname = os.path.basename(dev)
            with open(os.path.join(dev, '../uevent'), 'r') as fp:
                for line in fp:
                    line = line.strip()
                    if line and '=' in line:
                        param, value = line.split('=')
                        if param == 'PRODUCT':
                            testvendor, testproduct = map(hexint, value.split('/')[:2])
                            if testvendor == vendor and testproduct == product:
                                return os.path.join('/dev', devname)

    @classmethod
    def _find_device_file__macos(cls, vendor, product):
        devices = []
        curdevice = {}

        res = subprocess.check_output(['ioreg', '-p', 'IOUSB', '-l', '-b']).decode('utf-8')
        for line in res.split('\n'):
            line = line.strip()
            if not line:
                continue

            match = re.match(u'^\+-o (.+)\s+<', line)
            if match:
                if curdevice:
                    devices.append(curdevice)
                    curdevice = {}
                continue

            match = re.match(u'^[\|\s]*"([\w\d\s]+)"\s+=\s+(.+)$', line)
            if match:
                k, v = match.groups()
                if v.startswith('"'):
                    v = v[1:-1]
                else:
                    try:
                        v = int(v)
                    except:
                        pass
                curdevice[k] = v

        if curdevice:
            devices.append(curdevice)

        for d in devices:
            if d.get('idVendor') == vendor and d.get('idProduct') == product:
                return '/dev/tty.usbserial-' + d['USB Serial Number']

    @classmethod
    def _find_device_file(cls, name):
        # Name is either a path (/dev/ttyUSB0) which might change, or a device ID (0403:6001) which does not
        if name.startswith('/') or ':' not in name:
            # Assume file
            return name

        if ':' not in name:
            raise ValueError(f"Not a valid device ID: {name}")

        vendor, product = map(hexint, name.split(':'))

        for fn in (self._find_device_file__linux, self._find_device_file__macos):
            try:
                file = fn(vendor, product)
                if file:
                    return file
            except:
                logger.error("Failure in find device file", exc_info=True)

        raise RuntimeError(f"Can't find USB device {name}")

    def setChannel(self, chan, value):
        self.data[chan] = value

    def render(self):
        if self.data:
            dmx = self.dmx_impl
            if dmx:
                for k, v in self.data.items():
                    dmx.setChannel(k, v)
                dmx.render()
                self.data = {}
