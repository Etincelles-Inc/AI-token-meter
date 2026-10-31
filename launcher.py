"""Desktop entry point used by source runs and PyInstaller."""
import sys
sys.dont_write_bytecode = True
from token_speedometer.cli import main
if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        if sys.stderr:
            raise
        else:
            import tkinter.messagebox
            tkinter.messagebox.showerror("Etincelles Token Meter", type(exc).__name__ + ": " + str(exc))
