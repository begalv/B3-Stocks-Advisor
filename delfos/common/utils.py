from delfos.common.configs import Configs
from datetime import datetime
import pandas as pd
import sys
import os
import warnings

warnings.simplefilter("ignore")

CONFIGS = Configs()

MARKET_OPEN_HOUR = CONFIGS.CONSTANTS["MARKET_OPEN_HOUR"]
MARKET_CLOSE_HOUR = CONFIGS.CONSTANTS["MARKET_CLOSE_HOUR"]



def block_print():
    sys.stdout = open(os.devnull, 'w')

def enable_print():
    sys.stdout = sys.__stdout__

def is_market_hours():
    now = datetime.now()
    if now.hour >= MARKET_OPEN_HOUR and now.hour < MARKET_CLOSE_HOUR:
        return True
    else:
        return False
