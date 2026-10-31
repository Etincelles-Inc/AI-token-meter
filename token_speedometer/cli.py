import argparse
import json
import sys
import time
from . import __version__
from .config import load_config, save_config, validate_config
from .controller import Controller
from .proxy import CaptureProxy
from .install import NAME, install, uninstall

def main():
    parser = argparse.ArgumentParser(description=NAME + ": engine-native Read / Write tok/s.")
    parser.add_argument("--version", action="version", version=NAME + " " + __version__)
    parser.add_argument("--backend", choices=["auto", "vllm", "llamacpp", "ollama", "native"])
    parser.add_argument("--upstream", help="Engine base URL (not the capture proxy)")
    parser.add_argument("--model", help="Exact model name; empty means automatic")
    parser.add_argument("--proxy-port", type=int)
    parser.add_argument("--headless", action="store_true", help="Run the proxy and print numeric samples")
    parser.add_argument("--samples", type=int, default=0, help="Print this many samples, then exit")
    parser.add_argument("--install", action="store_true", help="Install for the current user")
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--yes", action="store_true", help="Confirm command-line uninstall")
    args = parser.parse_args()
    if args.install:
        print(install())
        return
    if args.uninstall:
        if not args.yes:
            if not sys.stdin or not sys.stdin.isatty():
                parser.error("Use --uninstall --yes to confirm removal.")
            if input("Uninstall " + NAME + "? [y/N] ").lower() != "y":
                return
        print(uninstall())
        return
    config = load_config()
    changes = {key: getattr(args, key) for key in ["backend", "upstream", "model", "proxy_port"] if getattr(args, key) is not None}
    config = validate_config({**config, **changes})
    if changes:
        save_config(config)
    if config["upstream"] in (f"http://127.0.0.1:{config['proxy_port']}", f"http://localhost:{config['proxy_port']}"):
        parser.error("Upstream URL cannot be the capture proxy itself.")
    controller = Controller(config)
    proxy = CaptureProxy(controller.get_config, controller.store, config["proxy_port"])
    proxy.start()
    controller.start()
    try:
        if args.headless or args.samples:
            index = 0
            while not args.samples or index < args.samples:
                print(json.dumps(controller.snapshot(), allow_nan=False), flush=True)
                index += 1
                time.sleep(1)
        else:
            from .gui import run
            run(controller, proxy)
    except KeyboardInterrupt:
        pass
    finally:
        controller.close()
        proxy.close()
