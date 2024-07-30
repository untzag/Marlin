import usb.core
import usb.util
import matplotlib.pyplot as plt
import numpy as np
import sys, os, time
import struct


sl = (slice(None, -1, None), slice(None, -2, None))


class SeekThermal(object):

    def __init__(self):
        # find our Seek Thermal device  289d:0010
        self.dev = usb.core.find(idVendor=0x289d, idProduct=0x0010)
        if not self.dev:
            raise ValueError('Device not found')
        self.cal = 0
        self.init()

    def send_msg(self, bmRequestType, bRequest, wValue=0, wIndex=0, data_or_wLength=None, timeout=None):
        assert (self.dev.ctrl_transfer(bmRequestType, bRequest, wValue, wIndex, data_or_wLength, timeout) == len(data_or_wLength))

    def receive_msg(self, *args, **kwargs):
        return self.dev.ctrl_transfer(*args, **kwargs)

    def deinit(self):
        '''Deinit the device'''
        msg = '\x00\x00'
        for i in range(3):
            self.send_msg(0x41, 0x3C, 0, 0, msg)

    def init(self):

        # set the active configuration. With no arguments, the first configuration will be the active one
        self.dev.set_configuration()

        # get an endpoint instance
        cfg = self.dev.get_active_configuration()
        intf = cfg[(0,0)]

        custom_match = lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
        ep = usb.util.find_descriptor(intf, custom_match=custom_match)   # match the first OUT endpoint
        assert ep is not None


        # Setup device
        try:
            msg = '\x01'
            self.send_msg(0x41, 0x54, 0, 0, msg)
        except Exception as e:
            print(e)
            self.deinit()
            msg = '\x01'
            self.send_msg(0x41, 0x54, 0, 0, msg)

        #  Some day we will figure out what all this init stuff is and
        #  what the returned values mean.

        self.send_msg(0x41, 0x3C, 0, 0, '\x00\x00')
        ret1 = self.receive_msg(0xC1, 0x4E, 0, 0, 4)
        print(ret1)
        ret2 = self.receive_msg(0xC1, 0x36, 0, 0, 12)
        print(ret2)

        self.send_msg(0x41, 0x56, 0, 0, '\x20\x00\x30\x00\x00\x00')
        ret3 = self.receive_msg(0xC1, 0x58, 0, 0, 0x40)
        #print ret3

        self.send_msg(0x41, 0x56, 0, 0, '\x20\x00\x50\x00\x00\x00')
        ret4 = self.receive_msg(0xC1, 0x58, 0, 0, 0x40)
        #print ret4

        self.send_msg(0x41, 0x56, 0, 0, '\x0C\x00\x70\x00\x00\x00')
        ret5 = self.receive_msg(0xC1, 0x58, 0, 0, 0x18)
        #print ret5

        self.send_msg(0x41, 0x56, 0, 0, '\x06\x00\x08\x00\x00\x00')
        ret6 = self.receive_msg(0xC1, 0x58, 0, 0, 0x0C)
        #print ret6

        self.send_msg(0x41, 0x3E, 0, 0, '\x08\x00')
        ret7 = self.receive_msg(0xC1, 0x3D, 0, 0, 2)
        #print ret7

        self.send_msg(0x41, 0x3E, 0, 0, '\x08\x00')
        self.send_msg(0x41, 0x3C, 0, 0, '\x01\x00')
        ret8 = self.receive_msg(0xC1, 0x3D, 0, 0, 2)
        #print ret8

    def get_image(self):
        while True:
            # Send read frame request
            self.send_msg(0x41, 0x53, 0, 0, struct.pack("i", 208 * 156))

            try:
                data  = self.dev.read(0x81, 0x3F60, 1000)
                data += self.dev.read(0x81, 0x3F60, 1000)
                data += self.dev.read(0x81, 0x3F60, 1000)
                data += self.dev.read(0x81, 0x3F60, 1000)
            except usb.USBError as e:
                sys.exit()

            status = data[20]
            data = np.frombuffer(data, dtype=np.int16)

            if status == 1:  # calibration frame
                first_time = isinstance(self.cal, int)
                self.cal = data.reshape(156, 208)[sl]
                if first_time:  # find the dead pixels
                    dmean = self.cal.mean()
                    self.dead_pixels = np.where(self.cal < 0.3 * dmean)

            if status == 3:  # normal frame
                data = data.reshape(156, 208)[sl].astype(np.float64)
                data -= self.cal
                # self.logger.info(f"data shape {data.shape}")
                #for xi, yi in zip(*self.dead_pixels):  # median filter to replace dead pixels
                #    xmin, xmax = max(0, xi - 1), min(xi + 2, data.shape[0] + 1)
                #    ymin, ymax = max(0, yi - 1), min(yi + 2, data.shape[1] + 1)
                #    sli = (slice(xmin, xmax, None), slice(ymin, ymax, None))
                #    old = data[xi, yi]
                #    data[xi, yi] = np.median(data[sli])
                # force pixel 1 and 40 to zero
                #data[0, 1] = np.median(data[0:2, 1:3])
                #data[0, 40] = np.median(data[0:2, 39:42])
                # to deg C
                data *= 0.0179
                data += 42.
                # finish
                return data


camera = SeekThermal()

# set up plot
fig = plt.figure()
ax = fig.add_subplot(111)
ax.set_ylim(0, 1)
zi = camera.get_image()
print(zi.shape)
ai = ax.imshow(zi, cmap="plasma")
cbar = plt.colorbar(ai)
ax.set_xlim(0, zi.shape[0])
ax.set_ylim(0, zi.shape[0])
ax.set_axis_off()
plt.ion()
plt.show()

while True:
    zi = camera.get_image()
    ai.set_data(zi)
    ai.set_clim(zi.min(), zi.max())
    print(zi.min(), zi.max())
    fig.canvas.draw()
    fig.canvas.flush_events()
