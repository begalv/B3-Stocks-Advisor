from pathlib import Path
import json
import os



class Configs():

    with open(Path("./delfos/data/market/tickers.json"), "r", encoding="utf8") as tickers_file:
        TICKERS_DICT = json.load(tickers_file) #dicionário com todas as informações fixas das ações listadas na B3


    with open(Path("./delfos/data/broker/cash.json"), "r+", encoding="utf8") as cash_file:
        CASH = json.load(cash_file) #lista de dicionários com o patrimonio liquido ao longo do tempo


    REQUESTS_HEADER = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.75 Safari/537.36", 'Accept-Encoding': 'gzip, deflate', 'Accept': '*/*', 'Connection': 'keep-alive'
    }

    DEFAULTS = {
        "SESSION_FREQ_PER_YEAR": 248,
        "N_THREADS": 12
    }

    URLS = {
        "FUNDAMENTUS": "https://fundamentus.com.br/detalhes.php?papel=",
        "BACEN": "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{}/dados?formato=json",
        "YFINANCE_CALENDAR": "https://finance.yahoo.com/calendar/",
        "YFINANCE_HISTORY": "https://finance.yahoo.com/quote/{}/history?p={}"
    }

    CONSTANTS = {
        "BACEN_SELIC_CODE": "432",
        "BACEN_SELIC_CUM_CODE": "11",
        "MARKET_OPEN_HOUR": 10,
        "MARKET_CLOSE_HOUR": 19
    }

    PATHS = {
        "movements_folder": Path("./delfos/data/broker/movements/"),
        "cash": Path("./delfos/data/broker/cash.json")
    }
