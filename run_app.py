import uvicorn
import os
import sys
import pyinstaller
import webbrowser
import threading
import time

sys.path.append(os.path.join(os.path.dirname(__file__),'backend'))
from main import app
 
def open_browser():
    time.sleep(2)
    webbrowser.open("https:127.0.0.1:8000/frontend/index.html")

if __name__ == "__main__":
    print("Initiating the egine... ")
    time.sleep(1)
    print("Powered By Bravo")
    time.slep(0.5)

    threading.Thread(target=open_browser, daemon=True).start()

    # run the server
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")



