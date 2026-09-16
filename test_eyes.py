import time
from interface.cli.eyes import Eyes

eyes = Eyes()

import threading
threading.Thread(target=eyes.start, daemon=True).start()

time.sleep(8)

eyes.stop()
print("Done.")
