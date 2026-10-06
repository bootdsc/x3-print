import time

import serial
from serial.tools import list_ports

from . import proto

VID, PID = 0x0483, 0x5720
ROW_BYTES = 108
ROWS_PER_FRAME = 4
DOTS_PER_MM = 300 / 25.4


def find_port():
    for p in list_ports.comports():
        if p.vid == VID and p.pid == PID:
            return p.device
    return None


class Printer:
    def __init__(self, port=None):
        port = port or find_port()
        if not port:
            raise OSError("X3 not found on USB")
        self.s = serial.Serial(port, 115200, timeout=0.02)
        self.dec = proto.Decoder()
        self.seq = 0
        self.last_status = None
        self.replies = []

    def close(self):
        self.s.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def send(self, cmd, payload=b""):
        self.s.write(proto.frame(cmd, payload, self.seq))
        self.seq = (self.seq + 1) & 0x3F

    def poll(self):
        n = self.s.in_waiting
        if n:
            for c, _, p in self.dec.feed(self.s.read(n)):
                if c in proto.R_STATUS and len(p) >= 8:
                    self.last_status = proto.status(p)
                else:
                    self.replies.append((c, p))
        return self.last_status

    def query(self, cmd, reply, timeout=1.0):
        self.replies.clear()
        self.send(cmd)
        end = time.time() + timeout
        while time.time() < end:
            self.poll()
            for c, p in self.replies:
                if c == reply:
                    return p
            time.sleep(0.01)
        return None

    def model(self):
        p = self.query(proto.Q_MODEL, proto.R_MODEL)
        return p.decode("ascii", "replace") if p else None

    def wait_status(self, timeout=1.5):
        end = time.time() + timeout
        while time.time() < end:
            if self.poll():
                return self.last_status
            time.sleep(0.01)
        return None

    def print_rows(self, data, density=None, speed=None, feed_mm=8, rate=0, cancel=None, progress=None):
        if len(data) % ROW_BYTES:
            raise ValueError("raster length must be a multiple of 108")
        if speed is not None:
            self.send(proto.SPEED, bytes((speed,)))
        if density is not None:
            self.send(proto.DENSITY, bytes((density,)))
        self.send(proto.PAPER_TYPE, bytes((1, 0)))
        rows = len(data) // ROW_BYTES
        t0 = time.perf_counter()
        for r in range(0, rows, ROWS_PER_FRAME):
            if cancel and cancel.is_set():
                return r
            if rate:
                wait = t0 + r / rate - time.perf_counter()
                if wait > 0:
                    time.sleep(wait)
            self.send(proto.RASTER, data[r * ROW_BYTES:(r + ROWS_PER_FRAME) * ROW_BYTES])
            if r % 32 == 0:
                self.poll()
                if progress:
                    progress(r)
        dots = round(feed_mm * DOTS_PER_MM)
        if dots:
            self.send(proto.FEED_FORWARD, dots.to_bytes(2, "little"))
        if progress:
            progress(rows)
        return rows
