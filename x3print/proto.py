START, END, SEED = 0x64, 0x9B, 0x12345678

RASTER = 0x00
FEED_FORWARD = 0x02
DENSITY = 0x09
SPEED = 0x0A
PAPER_TYPE = 0x28
Q_MODEL = 0x12
R_MODEL = 0xF2
R_STATUS = (0x80, 0x81, 0xFF)


def frame(cmd, payload=b"", seq=0):
    head = bytes((START, cmd, seq & 0x3F)) + len(payload).to_bytes(2, "little") + payload
    integ = (SEED + sum(head) + END) & 0xFFFFFFFF
    return head + integ.to_bytes(4, "little") + bytes((END,))


class Decoder:
    def __init__(self):
        self.buf = bytearray()

    def feed(self, data):
        self.buf += data
        out = []
        while True:
            i = self.buf.find(START)
            if i < 0:
                self.buf.clear()
                return out
            del self.buf[:i]
            if len(self.buf) < 5:
                return out
            n = int.from_bytes(self.buf[3:5], "little") + 10
            if len(self.buf) < n:
                return out
            pkt = bytes(self.buf[:n])
            integ = int.from_bytes(pkt[-5:-1], "little")
            if pkt[-1] != END or integ not in (0, (SEED + sum(pkt[:-5]) + END) & 0xFFFFFFFF):
                del self.buf[0]
                continue
            out.append((pkt[1], pkt[2], pkt[5:-5]))
            del self.buf[:n]


def status(payload):
    bits = int.from_bytes(payload[2:4], "little")
    return {
        "bits": bits,
        "printing": bool(bits & 1 << 3),
        "cover_open": bool(bits & 1 << 8),
        "low_battery": bool(bits & 1 << 9),
        "overheat": bool(bits & 1 << 10),
        "paper_out": bool(bits & 1 << 11),
        "density": payload[4],
        "auto_off": payload[5],
        "speed": payload[6],
        "battery": payload[7],
    }
