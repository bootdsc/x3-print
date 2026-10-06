import argparse
import sys
import time


def cmd_status(a):
    from . import link
    with link.Printer(a.port) as p:
        print("model  ", p.model())
        st = p.wait_status()
        if st:
            print(f"battery {st['battery']} %  heat {st['density']}  speed {st['speed']}")
            flags = [k for k in ("printing", "cover_open", "low_battery", "overheat", "paper_out") if st[k]]
            print("flags  ", ", ".join(flags) or "none")


def cmd_print(a):
    from . import link, raster
    width = raster.HEAD if not a.width_mm else min(raster.HEAD, round(a.width_mm * raster.DOTS_PER_MM))
    img = raster.load(a.image, width, a.rotate, a.nearest)
    img = raster.adjust(img, a.brightness, a.contrast, a.gamma, a.invert)
    data = raster.pack(raster.pad_to_head(raster.dither(img, a.dither, a.threshold), a.align))
    with link.Printer(a.port) as p:
        for c in range(a.copies):
            t = time.time()
            rows = p.print_rows(data, density=a.density, speed=a.speed, feed_mm=a.feed)
            print(f"copy {c + 1}: {rows} rows ({rows / raster.DOTS_PER_MM:.1f} mm) sent in {time.time() - t:.2f} s")
        end = time.time() + 2 + rows / 200
        while time.time() < end:
            p.poll()
            time.sleep(0.05)
        st = p.last_status
        bad = [k for k in ("paper_out", "cover_open", "overheat") if st and st[k]]
        if bad:
            print("ERROR printer reports:", ", ".join(bad))


def main(argv=None):
    if not (argv if argv is not None else sys.argv[1:]):
        from . import app
        return app.main()
    from .raster import MODES
    ap = argparse.ArgumentParser(prog="x3print", description="Run with no arguments to open the app.")
    ap.add_argument("--port", help="COM port; found automatically by default")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    pr = sub.add_parser("print")
    pr.add_argument("image")
    pr.add_argument("--dither", choices=MODES, default="bayer2")
    pr.add_argument("--threshold", type=float, default=0.5)
    pr.add_argument("--brightness", type=float, default=0.0)
    pr.add_argument("--contrast", type=float, default=0.0)
    pr.add_argument("--gamma", type=float, default=1.0)
    pr.add_argument("--invert", action="store_true")
    pr.add_argument("--nearest", action="store_true", help="pixel art: nearest-neighbour scaling")
    pr.add_argument("--rotate", type=int, choices=(0, 90, 180, 270), default=0)
    pr.add_argument("--width-mm", type=float)
    pr.add_argument("--align", choices=("left", "center", "right"), default="center")
    pr.add_argument("--density", type=int, default=9, help="heat, 1-15")
    pr.add_argument("--speed", type=int, default=100)
    pr.add_argument("--feed", type=float, default=8.0, help="mm fed after the image")
    pr.add_argument("--copies", type=int, default=1)
    pr.set_defaults(fn=cmd_print)
    a = ap.parse_args(argv)
    try:
        a.fn(a)
    except OSError as e:
        print("ERROR", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
