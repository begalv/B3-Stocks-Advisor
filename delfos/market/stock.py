from delfos.common.configs import Configs
import delfos.common.utils as utils
from yflive import QuoteStreamer #live stream dos preços
import yfinance as yf #package para se conectar a api do yahoo finance
import requests #package para fazer requests HTTP ao site Fundamentus
import pandas as pd
from datetime import datetime
import datetime as dt
import random #fix_split_dates
import time #testes

CONFIGS = Configs()

FUNDAMENTUS_URL = CONFIGS.URLS["FUNDAMENTUS"] #url para puxar informações como número de ações em circulação e indicadores fundamentalistas
YFINANCE_HISTORY_URL = CONFIGS.URLS["YFINANCE_HISTORY"] #url para o histórico das ações no yahoo finance
MARKET_OPEN_HOUR = CONFIGS.CONSTANTS["MARKET_OPEN_HOUR"] #hora que o mercado abre
MARKET_CLOSE_HOUR = CONFIGS.CONSTANTS["MARKET_CLOSE_HOUR"] #hora que o mercado fecha
REQUESTS_HEADER = CONFIGS.REQUESTS_HEADER #header para requisições HTTP, usado para web scrapping

NOW = datetime.now()


class Stock():
    """
    Classe que representa uma ação. Possui uma empresa, infomaçõs sobre esta e uma data de análise. O conjunto ticker + data de análise é o id da ação analisada.
    """

    def __init__(self, ticker, analysis_date=NOW, company="undefined", sector="undefined", sub_sector="undefined", segment="undefined", cnpj="undefined"):
        """
        Parameters
        ----------
        ticker : str
            O ticker (símbolo) da ação.
        analysis_date : datetime
            A data para a análise da ação. (default é a data atual)
        company : str
            O nome da empresa. (default é 'undefined')
        sector : str
            O setor de atuação da empresa. (default é 'undefined')
        sub_sector : str
            O sub setor de atuação da empresa. (default é 'undefined')
        segment : str
            O segmento de atuação da empresa. (default é 'undefined')
        cnpj : str
            O CNPJ da empresa. (default é 'undefined')

        Raises
        ------
        TypeError
            Se os parâmetros não baterem com seus respectivos tipos.
        """
        #checando se os tipos dos parâmetros estão corretos
        if not isinstance(ticker, str):
            raise TypeError("Argument 'ticker' must be a string.")
        if not isinstance(analysis_date, datetime):
            raise TypeError("Argument 'analysis_date' must be a datetime object.")
        if not isinstance(company, str):
            raise TypeError("Argument 'company' must be a string.")
        if not isinstance(sector, str):
            raise TypeError("Argument 'sector' must be a string.")
        if not isinstance(sub_sector, str):
            raise TypeError("Argument 'sub_sector' must be a string.")
        if not isinstance(segment, str):
            raise TypeError("Argument 'segment' must be a string.")
        if not isinstance(cnpj, str):
            raise TypeError("Argument 'cnpj' must be a string.")

        self.__is_active = True #assume inicialmente que a ação está ativa na data de análise
        self.__ticker = ticker
        self.__analysis_date = analysis_date
        #todas estas inormações podem ser encontradas no site da B3
        self.__company = company
        self.__sector = sector
        self.__sub_sector = sub_sector
        self.__segment = segment
        self.__cnpj = cnpj

        self.__set_type()

        #ajeitando o ticker da ação para a API do yahoo finance (OBS: LIMITA O USO DO CÓDIGO PARA AÇÕES BRASILEIRAS)
        if self.__ticker[0] != "^": #se o ticker for um índice, não adicionar o SA (SÃO PAULO)
            self.__yahoo_ticker = self.__ticker + ".SA"
        else:
            self.__yahoo_ticker = self.__ticker



#--------------------------------------- GETTERS ---------------------------------------------------------#

    @property
    def ticker(self):
        return self.__ticker #símbolo da companhia

    @property
    def analysis_date(self):
        return self.__analysis_date #data para a análise da ação

    @property
    def is_active(self):
        return self.__is_active #se a ação está ativa na data de análise

    @property
    def company(self):
        return self.__company #nome da companhia

    @property
    def sector(self):
        return self.__sector #setor da companhia

    @property
    def sub_sector(self):
        return self.__sub_sector #sub setor da companhia

    @property
    def segment(self):
        return self.__segment #segmento da companhia

    @property
    def cnpj(self):
        return self.__cnpj #identificação da empresa

    @property
    def type(self):
        return self.__type #tipo da ação (ordinária, preferencial e etc)

    @property
    def history(self):
        return self.get_history() #histórico de dados técnicos da ação até a data de análise

    @property
    def current_price(self):
        return self.get_current_price() #preço atual da ação para a data de análise

    @property
    def current_volume(self):
        return self.get_current_volume() #volume atual da ação para a data de análise

    @property
    def current_open_price(self):
        return self.get_current_open_price() #preço de abertura atual da ação para a data de análise

    @property
    def current_high_price(self):
        return self.get_current_high_price() #preço máximo atual da ação para a data de análise

    @property
    def current_low_price(self):
        return self.get_current_low_price() #preço mínimo atual da ação para a data de análise

    @property
    def shares_outstanding(self):
        return self.get_shares_outstanding() #número atual de ações em circulação

    @property
    def equity(self):
        return self.get_equity() #patrimônio líquido atual da companhia

    @property
    def earnings(self):
        return self.get_earnings() #lucro líquido atual da companhia (últimos 12 meses)

    @property
    def eps(self):
        return self.get_eps() #lucro por ação atual

    @property
    def bvps(self):
        return self.get_bvps() #valor patrimonial por ação atual

    @property
    def roe(self):
        return self.get_roe() #retorno sobre o valor patrimonial atual

    @property
    def market_cap(self):
        return self.get_market_cap() #valor de mercado da companhia

    @property
    def price_to_book(self):
        return self.get_price_to_book() #razão entre preço atual e o valor patrimonial por ação

    @property
    def price_to_earnings(self):
        return self.get_price_to_earnings() #razão entre preço atual e o lucro por ação

#---------------------------------------------------------------------------------------------------------#


    def __set_type(self):
        """
        Determina o tipo da ação de acordo com os números no final do ticker e a codificação estabelecida pela B3.

        OBS: LIMITA O USO DO CÓDIGO PARA AÇÕES BRASILEIRAS.

        Raises
        -------
        ValueError
            Se o atributo 'ticker' não tiver numeração válida para os códigos estabelecidos pela B3.
        """

        if self.__ticker[0] == "^":
            self.__type = "INDEX"
        elif self.__ticker[-1] == "3":
            self.__type = "ON" #ação ordinária
        elif self.__ticker[-1] == "4":
            self.__type = "PN" #ação preferencial
        elif self.__ticker[-1] == "5":
            self.__type = "PNA" #ação preferencial classe A
        elif self.__ticker[-1] == "6":
            self.__type = "PNB" #ação preferencial classe B
        else:
            self.__type = "undefined" #ações preferenciais de outras classes

        if self.__ticker[-2:] == "34" or self.__ticker[-2:] == "33":
            self.__type = "BDR" #ações de fora do brasil negociadas na B3

        elif self.__ticker[-2:] == "11":
            if self.__sub_sector == "Fundos":
                if self.__segment == "Fundos Imobiliários":
                    self.__type = "FII"
                else:
                    self.__type = "ETF"
            else:
                self.__type = "UNT"



    def __correct_stream_error(self, error):
        """
        Trata os erros no streamer de infos sobre os preços da ação.
        Se for um erro de conexão e esta for fechada, o método reabre a conexão setando novamente o streamer.

        Parameters
        ----------
        error : Error
            Erro no stream ao vivo dos preços da ação
        """
        #print(self.__ticker, ":", error)
        if str(error) == "Connection to remote host was lost.":
            self.__set_price_streamer()



    def __set_price_streamer(self):
        """
        Se a data de análise for a data atual, for um dia de semana e estiver em horário de pregão, abre a conexão com o socket do yflive.
        O socket estabelece um stream ao vivo de informações de preço (High, Low, Close, Volume).
        O recebimento ao vivo das infos é feito em uma thread separada, e portanto não trava o programa.
        """
        if self.__analysis_date.date() == NOW.date():
            weekday = NOW.date().weekday()
            if weekday != 5 and weekday != 6 and utils.is_market_hours():

                price_streamer = QuoteStreamer()
                price_streamer.subscribe([self.__yahoo_ticker]) #se inscreve no streamer para receber infos da ação específica

                price_streamer.on_quote = lambda price_streamer, quote: self.__update_current_price(quote) #a cada Quote (infos) recebida, ajusta os preços atuais e o histórico da ação
                price_streamer.on_error = lambda price_streamer, error: self.__correct_stream_error(error) #se um erro ocorrer, é tratado pela função passada
                price_streamer.start(should_thread=True) #começa a live stream de infos em uma thread separada



    def __fix_splits_dates(self, period):
        """
        Elimina os desdobramento duplicados no histórico baixado pelo yfinance,
        checando se existe mais de 1 split no mesmo ano e, se sim, deletando todos que não sejam o último.
        (yfinance duplica alguns splits e apenas o último é o correto)

        Reajusta os preços para datas de análise anteriores a Splits mais recentes. (yfinance ajusta todos os preços, independente da data)

        Parameters
        ----------
        period : int
            O período de tempo do histórico em anos. (default é 6 anos)

        Raises
        ------
        TypeError
            Se o parâmetro 'period' não for do tipo int.
        """
        #validando os tipos dos parâmetros
        if not isinstance(period, int):
            raise TypeError("Argument 'period' must be an integer.")

        if not self.__history.empty:
            #para cada ano entre o início do período de análise e a data atual
            for year in range(self.__analysis_date.year - period, NOW.year+1):
                #filtra todas as datas do ano em que REALMENTE ocorreram split
                splits_dates = self.__history[(self.__history["Stock Splits"] > 0) & (self.__history.index.year==year)].index

                #para cada data em que ocorreu split
                for split_date in splits_dates:
                    #print(self.__ticker)
                    #se a data do split for mais recente que a data de análise, reverte o split (para as colunas Open, High, Low, Close)
                    if split_date.date() > self.__analysis_date.date():
                        split = self.__history["Stock Splits"][split_date]
                        for col in self.__history.columns[:-3]:
                            self.__history[col] = self.__history[col] * split



    def download_history(self, period=6):
        """
        Cria um dataframe com o histórico da ação considerando um período de tempo e a data de análise,
        inclui: volume, preços de abertura, fechamento, máximo e mínimo, assim como dividendos e desdobramentos.
        Os dados são baixados com a api do yfinance, que acessa os dados do yahoo finance.
        Caso a api não consiga os dados mais recentes, o método utiliza um scraper para o site do Yahoo Finance
        Armazena o dataframe no atributo 'history'.

        A ação é ativa se a data de análise for um dia de semana e a última data do histórico é a data de análise (ou a última data válida antes da de análise para casos em que o pregão ainda não começou)

        OBS: Se a ação estiver inativa só na data mais recente, o histórico ainda é setado, mas o atributo 'is_active' vira False.

        Parameters
        ----------
        period : int
            O período de tempo do histórico em anos. (default é 6 anos)

        Raises
        ------
        TypeError
            Se o parâmetro 'period' não for do tipo int.

        Returns
        -------
        bool
            Verdadeiro se o download do histórico foi um sucesso.
        """
        #validando os tipos dos parâmetros
        if not isinstance(period, int):
            raise TypeError("Argument 'period' must be an integer.")

        success = True #assume inicialmente que o download do histórico foi um sucesso

        #ajusta as datas para o download dos dados
        end_date = self.__analysis_date
        start_year = self.__analysis_date.year - period
        start_date = datetime(start_year, 1, 1)

        try:
            #faz o download dos dados pela API do yahoo finance
            self.__history = yf.Ticker(self.__yahoo_ticker).history(period="{}y".format(period))
            #print(self.__history.index[-1].date())
            self.__history = self.__history[~self.__history.index.duplicated(keep="last")] #exclui datas duplicadas do histórico

            #exclui uma row se todos os preços mais o volume forem NaNs (em dia de dividendos ou stock splits os preços podem vir como NaNs erroneamnte pela API)
            #exclui para baixar o dado certo através do scraper do Yahoo Finance
            self.__history = self.__history.drop(self.__history[self.__history.Open.isna() &
                self.__history.High.isna() &
                self.__history.Low.isna() & self.__history.Close.isna() &
                self.__history.Volume.isna()].index)

            #se a data de análise é a data atual e os últimos dados, não: atualiza os dados pelo site do yahoo finance ao invés da api yfinance
            if self.__analysis_date.date() == NOW.date():
                #se a última data válida não é a atual
                if self.__history.index[-1].date() != NOW.date():
                    #se a ação não está inoperante por mais de 5 dias
                    if len(self.__history[(self.__history["Close"].duplicated()) & (self.__history["Close"] == self.__history["Close"][-1])]) <= 5:

                        #descobre se faz sentido a última data não ser a atual (dia de semana e horário com relação a abertura e fechamento do mercado)
                        weekday = NOW.date().weekday() #dia da semana
                        yesterday = NOW.date() - dt.timedelta(days=1)
                        yesterday_weekday = yesterday.weekday()
                        is_valid_day = False
                        #se não é nem sábado e nem domingo
                        if weekday != 5 and weekday != 6:
                            #se é horário de mercado
                            if utils.is_market_hours():
                                is_valid_day = True
                                last_active_day = NOW.date()

                            #se é antes da abertura do mercado
                            if datetime.now().hour < MARKET_OPEN_HOUR:
                                #se ontem não foi domingo
                                if yesterday_weekday != 6:
                                    #se a última data válida não é a de ontem
                                    if self.__history.index[-1].date() != yesterday:
                                        is_valid_day = True
                                        last_active_day = yesterday
                                #se ontem foi domingo
                                else:
                                    friday = yesterday - dt.timedelta(days=2)
                                    #se a última data válida não é a de sexta
                                    if self.__history.index[-1].date() != friday:
                                        is_valid_day = True
                                        last_active_day = friday

                            #se é depois do fechamento do mercado
                            else:
                                if datetime.now().hour > MARKET_CLOSE_HOUR:
                                    is_valid_day = True
                                    last_active_day = NOW.date()

                        #se é umm sábado ou domingo
                        else:
                            if yesterday_weekday == 5: #se ontem foi sábado
                                friday = yesterday - dt.timedelta(days=1)
                                if self.__history.index[-1].date() != friday:
                                    is_valid_day = True
                                    last_active_day = friday
                            else: #se ontem foi sexta
                                if self.__history.index[-1].date() != yesterday:
                                    is_valid_day = True
                                    last_active_day = yesterday

                        #se faz sentido atualizar os dados através do scraper do Yahoo Finance
                        if is_valid_day:
                            response = requests.get(YFINANCE_HISTORY_URL.format(self.__yahoo_ticker, self.__yahoo_ticker), headers=REQUESTS_HEADER)

                            current_data = pd.read_html(response.text)[0]

                            current_data = current_data.drop(columns=["Close*"]) #excluindo coluna com preços não ajustados
                            current_data = current_data.rename(columns={"Adj Close**": "Close"}) #renomeando coluna com preços ajustados

                            #exclui rows que todos os preços mais o volume são "-"
                            #pode acontecer no site do Yahoo Finance antes do mercado abrir
                            current_data = current_data.drop(current_data[current_data.Open.str.contains("-") &
                                current_data.High.str.contains("-") &
                                current_data.Low.str.contains("-") & current_data.Close.str.contains("-") &
                                current_data.Volume.str.contains("-")].index)

                            #exlui a última row do histórico baixado (não é dado válido)
                            current_data = current_data.drop(current_data.tail(1).index)

                            current_data["Date"] = pd.to_datetime(current_data["Date"]) #convertendo a coluna de Data para datetime
                            current_data = current_data.set_index("Date")

                            #guarda informações de dividendos e splits mineradas pelo scraper do Yahoo Finnce (não da maneira correta na tabela do histórico)
                            dividend = None
                            stock_split = None
                            #procura por rows de dividendos e splits apenas nas 5 primeiras linhas do histórico
                            for i, row in current_data.head().iterrows():
                                #se a linha for referente a data do últimdo pregão
                                if i.date() == last_active_day:
                                    #minera dividendo
                                    if "Dividend" in row["Close"]:
                                        dividend = float(row["Close"].strip("Dividend").strip())
                                    #minera stock split
                                    if "Stock Split" in row["Close"]:
                                        stock_split = row["Close"].strip("Stock Split").strip().split(":")
                                        stock_split = float(stock_split[0]) / float(stock_split[1])

                            #exclui datas duplicadas do historico baixado e mantém a primeira (histórico invertido)
                            #importante pois linhas de dividendos, splits e preço são separadas para a mesma data
                            current_data = current_data[~current_data.index.duplicated(keep="first")]

                            #se a data do último dia válido for a segunda linha do histórico baixado (para casos antes da abertura do mercado que já tenham a linha do dia, mas ainda sem os dados)
                            if current_data.index[1].date() == last_active_day:
                                current_data = current_data.drop(current_data.tail(len(current_data)-2).index) #mantendo apenas as duas primeiras linhas do histórico
                                current_data = current_data.drop(current_data.head(1).index) #excluindo a primeira linha e deixando apenas a segunda no histórico
                            #se o último dia válido for a primeira linha do histórico baixado
                            else:
                                current_data = current_data.drop(current_data.tail(len(current_data)-1).index) #mantendo apenas a primeira linha do histórico

                            #para cada coluna do histórico baixado (Open, Low, High, Close e Volume)
                            for col in current_data.columns:
                                current_data[col] = current_data[col].str.replace("-", "0")
                                try:
                                    #tenta transformar o valor da coluna em número
                                    current_data[col] = pd.to_numeric(current_data[col])
                                except:
                                    #se não conseguir, o download falhou
                                    current_data = pd.DataFrame()
                                    break

                            if current_data.empty:
                                self.__is_active = False
                            else:
                                #se o preço baixado não for NaN e seja referente a data do último pregão)
                                if not pd.isna(current_data["Close"][-1]) and current_data.index[-1].date() == last_active_day:

                                    #checa se foram encontrados dividendos e splits nos dados baixados do scraper do Yahoo Finance
                                    if dividend != None:
                                        current_data["Dividends"] = [dividend] #se sim, adiciona a coluna com o respectivo valor no histórico baixado
                                    if stock_split != None:
                                        current_data["Stock Splits"] = [stock_split]

                                    #atualiza a data atual no histórico
                                    self.__history = pd.concat([self.__history, current_data]) #junta o histórico da ação com o histórico baixado pelo scraper (Dividendos e Splits quando não existirem ficam como NaN)
                                    self.__history = self.__history.fillna(0) #substitui os NaNs de Dividends e Stock Splits no histórico da ação

                                    #se a data de análise não fora sábado ou domingo, a ação está ativa
                                    if weekday != 5 and weekday != 6:
                                        self.__is_active = True
                                    else:
                                        self.__is_active = False

                                    #print("Histórico puxado do site yahoo: ", self.__ticker) #teste
                                    #print() #teste
                                else:
                                    #print("Yahoo Finance errado: ", self.__ticker) #teste
                                    #print() #teste
                                    self.__is_active = False

                    #se a ação está inoperante por mais de 5 dias
                    else:
                        self.__is_active = False
                #se a data de análise é a atual e tamém a última data do histório
                else:
                    self.__is_active = True
            #se a data de análise não é a atual
            else:
                #se a última data do histório for a data de análise, a ação estava ativa
                if self.__analysis_date == self.__history.index[-1].date():
                    self.__is_active = True
                else:
                    self.__is_active == False

        except Exception as e:
            #print(e) #teste
            #se o download dos dados falhar ou todos os dados baixados forem NaNs
            self.__history = pd.DataFrame() #o atributo 'history' se torna um dataframe vazio

        self.__fix_splits_dates(period) #mantém apenas os splits reais no histórico (alguns estão duplicados)
        self.__history = self.__history[self.__history.index <= end_date] #mantém o histórico da data de início do período de análise até a data de análise

        if self.__history.empty:
            #print("Não conseguiu baixar o historico: " + self.__ticker) #teste
            self.__is_active = False
            self.__current_price = 0
            self.__current_volume = 0
            self.__current_open_price = 0
            self.__current_high_price = 0
            self.__current_low_price = 0
            success = False

        else:
            self.__set_price_streamer()
            #preço atual é igual ao preço do ultimo pregão em que a ação estava ativa
            self.__current_price = float(self.__history["Close"][self.__history["Close"].last_valid_index()])
            self.__current_volume = float(self.__history["Volume"][self.__history["Volume"].last_valid_index()])
            self.__current_open_price = float(self.__history["Open"][self.__history["Open"].last_valid_index()])
            self.__current_high_price = float(self.__history["High"][self.__history["High"].last_valid_index()])
            self.__current_low_price = float(self.__history["Low"][self.__history["Low"].last_valid_index()])

        return success



    def get_history(self):
        """
        Getter do atributo 'history', que armazena o histórico da ação em um período de tempo.
        O atributo é declarado pelo getter, caso ainda não tenha sido.

        Returns
        -------
        DataFrame
            Dataframe com o histórico da ação, de acordo com a data de análise e um período de tempo. (Pode estar vazio)
        """
        try:
            return self.__history
        except:
            self.download_history()
            return self.__history



    def __update_current_price(self, quote):
        """
        Atualiza os preços/volume atuais e o histórico, de acordo com a Quote (infos) vinda do streamer de preços do yflive.

        Parameters
        ----------
        quote : yflive.Quote
            Objeto com as informações da ação sendo streamadas ao vivo.
        """
        if hasattr(quote, "price"):
            self.__current_price = quote.price
            self.__history.loc[self.__history.index.date == NOW.date(), "Close"] = self.__current_price

            if self.current_price > self.current_high_price:
                self.__current_high_price = self.__current_price
                self.__history.loc[self.__history.index.date == NOW.date(), "High"] = self.__current_high_price

            if self.current_price < self.current_low_price:
                self.__current_low_price = self.__current_price
                self.__history.loc[self.__history.index.date == NOW.date(), "Low"] = self.__current_low_price

        if hasattr(quote, "dayVolume"):
            self.__current_volume = quote.dayVolume
            self.__history.loc[self.__history.index.date == NOW.date(), "Volume"] = self.__current_volume



    def get_current_price(self):
        """
        Getter do atributo 'current_price', que armazena o preço mais recente da ação para a data de análise.
        O atributo é declarado pelo getter, caso ainda não tenha sido.

        Returns
        -------
        float
            O preço mais recente da ação para a data de análise. (Igual a 0, para ações cujo download falhou)
        """
        try:
            return self.__current_price
        except:
            self.download_history()
            return self.__current_price



    def get_current_volume(self):
        """
        Getter do atributo 'current_volume', que armazena o volume mais recente da ação para a data de análise.
        O atributo é declarado pelo getter, caso ainda não tenha sido.

        Returns
        -------
        float
            O volume mais recente da ação para a data de análise. (Igual a 0, para ações cujo download falhou)
        """
        try:
            return self.__current_volume
        except:
            self.download_history()
            return self.__current_volume



    def get_current_open_price(self):
        """
        Getter do atributo 'current_open_price', que armazena o preço de abertura mais recente da ação para a data de análise.
        O atributo é declarado pelo getter, caso ainda não tenha sido.

        Returns
        -------
        float
            O preço de abertura mais recente da ação para a data de análise. (Igual a 0, para ações cujo download falhou)
        """
        try:
            return self.__current_open_price
        except:
            self.download_history()
            return self.__current_open_price



    def get_current_high_price(self):
        """
        Getter do atributo 'current_high_price', que armazena a alta diária mais recente da ação para a data de análise.
        O atributo é declarado pelo getter, caso ainda não tenha sido.

        Returns
        -------
        float
            O preço da alta diária mais recente da ação para a data de análise. (Igual a 0, para ações cujo download falhou)
        """
        try:
            return self.__current_high_price
        except:
            self.download_history()
            return self.__current_high_price



    def get_current_low_price(self):
        """
        Getter do atributo 'current_low_price', que armazena a baixa diária mais recente da ação para a data de análise.
        O atributo é declarado pelo getter, caso ainda não tenha sido.

        Returns
        -------
        float
            O preço da baixa diária mais recente da ação para a data de análise. (Igual a 0, para ações cujo download falhou)
        """
        try:
            return self.__current_low_price
        except:
            self.download_history()
            return self.__current_low_price



    def download_fundamental_data(self, extra_tries=4):
        """
        Faz o download dos dados fundamentalistas da ação, através do site Fundamentus.
        Caso o download falhe, o método tentará recursivamente outras vezes, até que o limite de tentativas se exceda.
        Se o download falhar, os atributos numéricos serão 0 e o restante, 'undefined'.

        Dados fundamentalistas: Patrimônio Líquido (equity), Lucro Líquido (earnings), Número de Ações em Circulação (shares outstanding), LPA (eps), VPA (bvps), ROE

        OBS: LIMITA O USO DO CÓDIGO PARA AÇÕES BRASILEIRAS.
        OBS: Não acerta os atributos numéricos com base na data de análise e sim na data atual (não encontrei série histórica para isso).

        Parameters
        ----------
        extra_tries : int
            O número de tentativas restantes, para caso o download falhe. (default é 4 tentativas)

        Raises
        ------
        TypeError
            Se o parâmetro 'extra_tries' não for do tipo int.

        Returns
        -------
        bool
            Verdadeiro se o download dos dados fundamentalistas foi um sucesso.
        """
        #validando os tipos dos parâmetros
        if not isinstance(extra_tries, int):
            raise TypeError("Argument 'extra_tries' must be an integer.")

        success = True #assume inicialmente que o método conseguiu realizar o download com sucesso
        try:
            if self.__type != "BDR":
                requested_data = requests.get(FUNDAMENTUS_URL + self.__ticker, headers=REQUESTS_HEADER) #chamada GET ao site da Fundamentus
                html_tables_list = pd.read_html(requested_data.text) #captura as tabelas do html em uma lista de dataframes

                #se as informações que identificam a companhia não tiverem sido setadas
                if self.__company == "undefined":
                    self.__company = html_tables_list[0][1][2] #nome da companhia
                if self.__sub_sector == "undefined":
                    self.__sub_sector = html_tables_list[0][1][3] #sub setor da companhia
                if self.__segment == "undefined":
                    self.__segment = html_tables_list[0][1][4] #segmento da companhia
                if self.__type == "undefined":
                    self.__type = html_tables_list[0][1][1].split()[0] #tipo da ação (ordinária, preferencial, unit, etc)

                self.__equity = float(list(html_tables_list[3][3])[-1].replace(".", "")) #Patrimônio Líquido
                self.__earnings = float(list(html_tables_list[4][1])[-1].replace(".", "")) #Lucro Líquido (últimos 12 meses)

                #seta o número de ações em circulação
                if self.__type == "UNT": #se a ação for uma Unit
                    #calcula o número de ações em circulação com base no Valor Patrimonial por Ação (bvps) e no Patrimônio Líquido (equity)
                    bvps = float(html_tables_list[2][5][2][:-2] + "." + html_tables_list[2][5][2][-2:]) #Book Value per Share
                    if bvps != 0:
                        self.__shares_outstanding = int(1 / (bvps * (1 / self.__equity)))
                    else:
                        success = False
                else:
                    self.__shares_outstanding = int(html_tables_list[1][3][1].replace(".", ""))

                try:
                    self.__eps = self.__earnings / self.__shares_outstanding #LPA = Lucro por Ação = Earnings per Share
                    self.__bvps = self.__equity / self.__shares_outstanding #VPA = Valor Patrimonial por Ação = Book Value per Share
                    self.__roe = self.__earnings / self.__equity #Return on Equity
                except:
                    success = False

        except Exception as e:
            if str(e) == "HTTP Error 503: Service Unavailable" and extra_tries > 0: #se o erro foi de conexão
                extra_tries -= 1
                success = self.download_fundamental_data(extra_tries) #tenta recursivamente, caso ainda restem tentativas
            else:
                success = False #se o download falhou e não restam mais tentativas, o método falhou

        #se o download falhou
        if success == False:
            #print("Não conseguiu baixar os dados fund.: " + self.__ticker) #teste
            #seta os atributos númericos como 0
            self.__equity = 0
            self.__earnings = 0
            self.__shares_outstanding = 0
            self.__eps = 0
            self.__bvps = 0
            self.__roe = 0
        return success



    def get_shares_outstanding(self):
        """
        Getter do atributo 'shares_outstanding', que armazena o número atual de ações em circulação.
        O atributo é declarado pelo getter, caso ainda não tenha sido.

        OBS: Não é referente a data de análise, mas sim a data atual. (não encontrei série histórica para isso)

        Returns
        -------
        int
            O número atual de ações em circulação. (Igual a 0, para ações cujo download falhou)
        """
        try:
            return self.__shares_outstanding
        except:
            self.download_fundamental_data()
            return self.__shares_outstanding



    def get_equity(self):
        """
        Getter do atributo 'equity', que armazena o Patrimônio Líquido atual da companhia.
        O atributo é declarado pelo getter, caso ainda não tenha sido.

        OBS: Não é referente a data de análise, mas sim a data atual. (não encontrei série histórica para isso)

        Returns
        -------
        float
            O Patrimônio Líquido atual da companhia. (Igual a 0, para ações cujo download falhou)
        """
        try:
            return self.__equity
        except:
            self.download_fundamental_data()
            return self.__equity



    def get_earnings(self):
        """
        Getter do atributo 'earnings', que armazena o Lucro Líquido atual da companhia.
        O atributo é declarado pelo getter, caso ainda não tenha sido.

        OBS: Não é referente a data de análise, mas sim a data atual. (não encontrei série histórica para isso)
        OBS: Lucro Líquido referente aos últimos 12 meses.

        Returns
        -------
        float
            O Lucro Líquido atual da companhia. (Igual a 0, para ações cujo download falhou)
        """
        try:
            return self.__earnings
        except:
            self.download_fundamental_data()
            return self.__earnings



    def get_eps(self):
        """
        Getter do atributo 'eps', que armazena o Lucro Líquido atual da companhia dividido pelo número atual de ações em circulação.
        EPS = Earnings Per Share = LPA = Lucro por Ação
        O atributo é declarado pelo getter, caso ainda não tenha sido.

        OBS: Não é referente a data de análise, mas sim a data atual. (não encontrei série histórica para isso)
        OBS: Lucro Líquido referente aos últimos 12 meses.

        Returns
        -------
        float
            O EPS atual da companhia. (Igual a 0, para ações cujo download falhou)
        """
        try:
            return self.__eps
        except:
            self.download_fundamental_data()
            return self.__eps



    def get_bvps(self):
        """
        Getter do atributo 'bvps', que armazena o Patrimônio Líquido atual da companhia dividido pelo número atual de ações em circulação.
        BVPS = Book Value Per Share = VPA = Valor Patrimonial por Ação
        O atributo é declarado pelo getter, caso ainda não tenha sido.

        OBS: Não é referente a data de análise, mas sim a data atual. (não encontrei série histórica para isso)

        Returns
        -------
        float
            O BVPS atual da companhia. (Igual a 0, para ações cujo download falhou)
        """
        try:
            return self.__bvps
        except:
            self.download_fundamental_data()
            return self.__bvps



    def get_roe(self):
        """
        Getter do atributo 'roe', que armazena o Lucro Líquido atual dividido pelo Patrimônio Líquido atual da companhia.
        É uma porcentagem na forma: 0 <= roe <= 1
        O atributo é declarado pelo getter, caso ainda não tenha sido.

        OBS: Não é referente a data de análise, mas sim a data atual. (não encontrei série histórica para isso)

        Returns
        -------
        float
            O ROE atual da companhia. (Igual a 0, para ações cujo download falhou)
        """
        try:
            return self.__roe
        except:
            self.download_fundamental_data()
            return self.__roe



    def get_market_cap(self):
        """
        Calcula o valor de mercado da ação para a data de análise.

        OBS: O shares_outstanding não é referente a data de análise, mas sim a data atual (não encontrei série histórica para isso)

        Returns
        -------
        float
            O valor de mercado da ação para a data de análise. (Igual a 0, para ações cujo download de 'current_price' ou de 'shares_outstanding' falhou)
        """
        return self.current_price * self.shares_outstanding #valor de mercado é a quantidade atual de ações em circulação vezes o preço atual da ação



    def get_price_to_book(self):
        """
        calcula o Price to Book, que é o preço atual da ação dividido pelo BVPS (Valor Patrimonial por Ação).

        OBS: O BVPS não é referente a data de análise, mas sim a data atual (não encontrei série histórica para isso)

        Returns
        -------
        float
            A razão entre preço atual e valor patrimonial por ação. (Igual a 0, para ações cujo download de 'current_price' ou de 'bvps' falhou)
        """
        if self.bvps != 0:
            price_to_book = self.current_price / self.bvps #valor de mercado é a quantidade atual de ações em circulação vezes o preço atual da ação
        else:
            price_to_book = 0
        return price_to_book



    def get_price_to_earnings(self):
        """
        Calcula o Price to Earnings, que é o preço atual da ação dividido pelo EPS (Lucro por Ação).

        OBS: O EPS não é referente a data de análise, mas sim a data atual (não encontrei série histórica para isso)
        OBS: Lucro Líquido referente aos últimos 12 meses.

        Returns
        -------
        float
            A razão entre preço atual e lucro por ação. (Igual a 0, para ações cujo download de 'current_price' ou de 'eps' falhou)
        """
        if self.eps != 0:
            price_to_earnings = self.current_price / self.eps #valor de mercado é a quantidade atual de ações em circulação vezes o preço atual da ação
        else:
            price_to_earnings = 0
        return price_to_earnings
