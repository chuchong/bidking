# run_gui_tk.py

import tkinter as tk
from bidking_gui_tk import BidKingOverlayTk


def main():
    root = tk.Tk()
    app = BidKingOverlayTk(root)
    root.mainloop()


if __name__ == "__main__":
    main()
