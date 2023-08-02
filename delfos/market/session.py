from delfos.market.stock import Stock
from delfos.common.configs import Configs
import delfos.common.utils as utils
from multiprocessing.pool import ThreadPool #package para paralelizar as operações nas ações do pregão
from pypfopt.black_litterman import BlackLittermanModel
from pypfopt import risk_models, expected_returns
from pypfopt import black_litterman #package com os modelos estatísticos de otimização de portfolios
from functools import reduce, partial #package nativo do python com funções gerais úteis
from datetime import datetime, timedelta
from datetime import date as dt
import pandas as pd
import time #testes


CONFIGS = Configs()

TICKERS_DICT = CONFIGS.TICKERS_DICT #dicionário com os símbolos das ações e suas respectivas infos
SESSION_FREQ_PER_YEAR = CONFIGS.DEFAULTS["SESSION_FREQ_PER_YEAR"] #número de dias no ano em que o mercado funciona
BACEN_URL = CONFIGS.URLS["BACEN"] #url para a api do bacen
BACEN_SELIC_CODE = CONFIGS.CONSTANTS["BACEN_SELIC_CODE"] #código da Selic na api do bacen
BACEN_SELIC_CUM_CODE = CONFIGS.CONSTANTS["BACEN_SELIC_CUM_CODE"] #código da Selic acumulada na api do bacen
N_THREADS = CONFIGS.DEFAULTS["N_THREADS"] #número de threads para serem utilizadas

NOW = datetime.now()


class Session():
    """
    Classe que representa um pregão. Possui ações, uma data e um período de análise em anos. A data é o id.
    """

    def __init__(self, date=NOW, period=6, tickers=TICKERS_DICT, index_ticker="^BVSP", risk_free_rate="selic"):
        """
        OBS: Permite que seja passado, ao invés de uma lista, um dicionário com as infos dos tickers, no formato:
                {
                    '<ticker>': {
                        'Nome de pregão': '<exchange_company_name>',
                        'CNPJ': '<company_registered_number>',
                        'Nome': '<company_name>',
                        'Setor': '<company_sector>',
                        'Sub Setor': '<company_sub_sector>',
                        'Segmento': '<company_segment>'
                    },
                    ...
                }

        Parameters
        ----------
        date : datetime
            A data do pregão. (default é a data atual)
        period : int
            O período em anos para a análise das ações do pregão. (default é 6 anos)
        tickers : list ou dict
            Os tickers das ações do pregão. (default é o dicionário de ações da B3)
        index_ticker : str
            O ticker do índice de mercado, que deve ser igual a como está no yahoo finance. (default é o ibovespa)
        risk_free_rate : str ou float
            A taxa livre de risco do mercado (default é a selic)

        Raises
        ------
        TypeError
            Se os parâmetros não baterem com seus respectivos tipos.
        """
        #checando se os tipos dos parâmetros estão corretos
        if not isinstance(date, datetime):
            raise TypeError("Argument 'date' must be a datetime object.")
        if not isinstance(period, int):
            raise TypeError("Argument 'period' must be an integer.")
        if not isinstance(tickers, (list, dict)):
            raise TypeError("Argument 'tickers' must be a dictionary or a list.")

        self.__date = date
        self.__period = period
        self.set_market_index(index_ticker)
        self.set_risk_free_rate(risk_free_rate)
        self.__stocks = {} #dict com todas as ações do pregão
        self.__active_stocks = {} #dict com as ações ativas durante o pregão (otimiza updates enquanto mantém as inativas para portfolios que as tenham)
        self.__set_stocks(tickers) #popula os dicionários de ações com os tickers e os respectivos objtos Stock
        #self.set_price_streamer()

#--------------------------------------- GETTERS ---------------------------------------------------------#

    @property
    def date(self):
        return self.__date

    @property
    def period(self):
        return self.__period

    @property
    def tickers(self):
        return list(self.__stocks.keys())

    @property
    def yahoo_tickers(self):
        return list(map(lambda x: x+".SA", self.tickers))

    @property
    def active_tickers(self):
        return list(self.__active_stocks.keys())

    @property
    def inactive_tickers(self):
        return list(set(self.__stocks.keys()) - set(self.__active_stocks.keys()))

    @property
    def stocks_num(self):
        return len(self.__stocks)

    @property
    def market_index(self):
        return self.__market_index

    @property
    def risk_free_rate(self):
        return self.__risk_free_rate

    @property
    def risk_free_rate_series(self):
        return self.__risk_free_rate_series

    @property
    def stocks(self):
        return self.get_stocks()

    @property
    def active_stocks(self):
        return self.get_active_stocks()

    @property
    def closing_prices_table(self):
        return self.get_closing_prices_table()

    @property
    def covariances_table(self):
        return self.get_covariances_table()

    @property
    def buy_weights(self):
        return self.get_buy_weights()

    @property
    def market_implied_rets(self):
        return self.get_market_implied_rets()

#---------------------------------------------------------------------------------------------------------#


    def set_market_index(self, index_ticker):
        """
        Guarda a ação do ticker passado por parâmetro como o índice do mercado.

        Parameters
        ----------
        index_ticker : str
            O ticker da ação que deve ser usada como índice do mercado.

        Raises
        ------
        TypeError
            Se o parâmetro 'index_ticker' não for uma string.
        ValueError
            Se o parâmetro 'index_ticker' não representar uma ação válida (com histórico na api do yahoo finance).
        """
        if not isinstance(index_ticker, str):
            raise TypeError("Argument 'index_ticker' must be a string.")

        self.__market_index = Stock(index_ticker, analysis_date=self.__date) #seta a ação como índice do mercado
        try:
            success = self.__market_index.download_history(self.__period)
            if success == False:
                self.__market_index = None
        except:
            raise ValueError("Invalid index ticker.")



    def set_risk_free_rate(self, risk_free_rate):
        """
        Se a taxa livre de risco indicada for a SELIC, faz o download da série temporal da SELIC através da API do BACEN e atribui a taxa como a do dia do pregão.
        Caso contrário, atribui a taxa como a indicada por parâmetro. Não faz download de nenhuma série temporal.

        Parameters
        ----------
        risk_free_rate : str ou float
            Se string, indica qual é a taxa que deve ser usada, se não, indica a taxa em float.

        Raises
        ------
        TypeError
            Se o parâmetro 'risk_free_rate' não for uma string ou um float.
        ValueError
            Se o parâmetro 'risk_free_rate' não for uma string válida ou não for um float entre 0 e 1.
        """
        #se o parametro inicial for uma string
        if isinstance(risk_free_rate, str):
            if risk_free_rate == "selic":
                try:
                    selic_time_series = pd.read_json(BACEN_URL.format(BACEN_SELIC_CUM_CODE)) #faz o download da série temporal da selic pela api do bacen (1986 - hoje)
                    current_selic = pd.read_json(BACEN_URL.format(BACEN_SELIC_CODE))

                    selic_time_series.index = selic_time_series["data"] #transforma a coluna com a data no index do dataframe
                    selic_time_series.index = pd.to_datetime(selic_time_series.index) #converte o index para datetime

                    selic_time_series = selic_time_series.drop("data", axis=1) #remove a coluna com a data (que agora é o index)
                    selic_time_series = selic_time_series[((selic_time_series.index.year >= self.__date.year - self.__period) & (selic_time_series.index <= self.__date))] #limita a série temporal entre o ano da sessão e o período de análise
                    selic_time_series["valor"] = selic_time_series["valor"]/100 #transformando 5% em 0,05 (exemplo)
                    self.__risk_free_rate_series = selic_time_series
                    self.__risk_free_rate_series = self.__risk_free_rate_series.sort_index()

                    self.__risk_free_rate = current_selic["valor"].iloc[-1] /100
                except Exception as e:
                    print(e)
                    self.__risk_free_rate_series = pd.Series()
                    self.__risk_free_rate = 0.1375 #colocar em um doc a última selic registrada para caso a API do bacen não estiver no ar
            #if risk_free_rate == "s&p500": #exemplo para futuras adições de possíveis taxas livre de risco (para análises fora do brasil)
            else:
                raise ValueError("Argument 'risk_free_rate' can only be a string if it's equal to 'selic'.")
        else:
            if not isinstance(risk_free_rate, float):
                raise TypeError("Argument 'risk_free_rate' must be a float or a string.")
            else:
                if risk_free_rate <= 0 or risk_free_rate >= 1:
                    raise ValueError("Argument 'risk_free_rate' must be a float between 0 and 1.")
                else:
                    self.__risk_free_rate_series = pd.Series() #dataframe vazio, pois não há serie temporal
                    self.__risk_free_rate = risk_free_rate



    def __set_stocks_aux(self, stock):
        """
        Método auxiliar para paralelizar o método 'set_stocks'.
        Atualiza os dicts com as ações do pregão (atributos 'stocks' e 'active_stocks'). (formato é {ticker: Stock})

        Parameters
        ----------
        stock : Stock
            O objeto Stock cujo o histórico e os dados fundamentalistas devem ser setados.

        Returns
        -------
        str ou None
            O ticker da ação, se esta não estiver ativa no pregão ou None, caso esteja.
        """
        success = stock.download_history(self.__period)

        if success == True:
            stock.download_fundamental_data() #tenta baixar os dados fundamentalistas
            if stock.is_active:
                self.__active_stocks[stock.ticker] = stock #atualiza o dicionário de ações ativas do pregão
            self.__stocks[stock.ticker] = stock #atualiza o dicionário de ações do pregão
        else:
            return stock.ticker #retorna o ticker como inválido



    def __set_stocks(self, tickers):
        """
        Atualiza os dicts com as ações do pregão (atributos 'stocks' e 'active_stocks'). (formato é {ticker: Stock})

        Parameters
        ----------
        tickers : list ou dict
            Os tickers das ações que devem ser setadas e adicionadas ao pregão.
        """
        #utils.block_print() #bloqueia prints (para não printar indesejadamente mensagens do package yfinance)

        #se tickers for um dicionário ao invés de lista
        if isinstance(tickers, dict):
            tickers_data = tickers
            tickers = list(tickers.keys())

        for ticker in tickers:
            if ticker not in self.__stocks:
                #tenta acessar os dados da ação no um dicionário com as infos
                try:
                    self.__stocks.update({ticker:Stock(ticker, self.__date, tickers_data[ticker]["Nome"], tickers_data[ticker]["Setor"], tickers_data[ticker]["Sub Setor"], tickers_data[ticker]["Segmento"], tickers_data[ticker]["CNPJ"])})
                except:
                    self.__stocks.update({ticker:Stock(ticker, self.__date)})

        #para cada ticker e objeto stock no dicionario de ações, baixar seu histórico e descobrir se a ação estava ativa no pregão
        pool = ThreadPool(processes=N_THREADS) #alocando 12 processos para setar os históricos das ações
        invalid_tickers = pool.map(self.__set_stocks_aux, self.select_stocks(tickers)) #parallel for para cada ação da sessão
        pool.close()
        pool.join()

        invalid_tickers = list(filter(None, invalid_tickers)) #filtra os Nones correspondentes aos tickers que não falharam
        self.remove_stocks(invalid_tickers) #remove da sessão as ações que falaharam no sucesso da operação
        #utils.enable_print()



    def get_stocks(self):
        """
        Getter do atributo 'stocks', que armazena um dict com os tickers das ações e seus objetos Stock.

        Returns
        -------
        dict
            O dicionário com os tickers das ações do pregão e seus respectivos objetos Stock.
        """
        return self.__stocks



    def get_active_stocks(self):
        """
        Getter do atributo 'active_stocks', que armazena um dict com os tickers das ações ativas e seus objetos Stock.

        Returns
        -------
        dict
            O dicionário com os tickers das ações ativas do pregão e seus respectivos objetos Stock.
        """
        return self.__active_stocks



    def select_stocks(self, tickers="all"):
        """
        Cria uma lista com os objetos Stock da sessão, cujo os tickers forem passados por parâmetro.
        Se apenas um ticker for passado como parâmetro na forma de string, retorna o objeto Stock equivalente.
        Se nenhum ticker passado estiver na sessão, retorna uma lista vazia.
        Se tickers for 'all' retorna todas as ações da sessão.
        Se tickers for 'active' retorna as ações ativas da sessão.

        Parameters
        ----------
        tickers : list ou str
            A lista de tickers cujo os objeto stocks devem ser selecionados. (default é todos os tickers do pregão)

        Raises
        ------
        TypeError
            Se o parâmetro 'tickers' não for uma lista ou uma string.

        Returns
        -------
        list ou Stock
            lista com os objetos Stock selecionados ou o objeto Stock selecionado.
        """
        #checando se os tipos dos parâmetros estão corretos
        if not isinstance(tickers, (str, list)):
            raise TypeError("Argument 'tickers' must be a list or a string.")

        if tickers == "all":
            return list(self.__stocks.values()) #se tickers for 'all', retorna todas as ações da sessão
        elif tickers == "active":
            return list(self.__active_stocks.values()) #se tickers for 'active', retorna todas as ações ativas da sessão
        else:
            #se tickers for uma string
            if isinstance(tickers, str):
                if tickers in self.__stocks:
                    return self.__stocks[tickers] #retorna apenas o objeto stock do ticker
                else:
                    return []
            else:
                selected_stocks = []
                for ticker in tickers:
                    if ticker in self.__stocks:
                        selected_stocks.append(self.__stocks[ticker]) #adiciona a lista de ações selecionadas o objeto Stock correspondente ao ticker
                return selected_stocks



    def add_stocks(self, tickers):
        """
        Adiciona às ações da sessão as ações cujo os tickers forem passadas por passados por parâmetro em uma lista.
        Permite que somente uma ticker seja passado na forma de string.
        Também seta o histórico das ações passadas.

        OBS: Permite que seja passado, ao invés de uma lista, um dicionário com as infos das ações no formato:
                {
                    '<ticker>': {
                        'Nome': '<company_name>',
                        'CNPJ': '<company_registered_number>',
                        'Setor': '<company_sector>',
                        'Sub Setor': '<company_sub_sector>',
                        'Segmento': '<company_segment>'
                    },
                    ...
                }

        Parameters
        ----------
        tickers : list, dict ou str
            A lista de tickers cujo os objetos Stock devem ser adicionados.

        Raises
        ------
        TypeError
            Se o parâmetro 'tickers' não for uma lista, dicionário ou uma string.
        """
        #checando se os tipos dos parâmetros estão corretos
        if not isinstance(tickers, (str, list, dict)):
            raise TypeError("Argument 'tickers' must be a list, dictionary or a string.")
        #se tickers for uma string
        if isinstance(tickers, str):
            tickers = [tickers]
        self.__set_stocks(tickers) #adiciona a ação às ações da sessão



    def remove_stocks(self, tickers):
        """
        Exclui das ações da sessão todas as ações cujo os tickers forem passados por parâmetro.
        Permite que somente uma ticker seja passado na forma de string.
        Caso nenhum ticker seja passado por parâmetro, não exclui nenhum ticker.

        Parameters
        ----------
        tickers : list ou str
            A lista de tickers cujo os objeto Stock devem ser excluídos.

        Raises
        ------
        TypeError
            Se o parâmetro 'tickers' não for uma lista ou uma string.
        """
        #checando se os tipos dos parâmetros estão corretos
        if not isinstance(tickers, (list, str)):
            raise TypeError("Argument 'tickers' must be a list or a string.")

        #se tickers for uma string
        if isinstance(tickers, str):
            tickers = [tickers]
        for ticker in tickers:
            if ticker in self.__stocks:
                if ticker in self.__active_stocks:
                    self.__active_stocks.pop(ticker)
                self.__stocks.pop(ticker)



    def __set_closing_prices_table(self):
        """
        Cria um dataframe com os preços de fechamento das ações do pregão, durante o período de análise. Index = data e Coluna = Ticker.
        """
        closing_prices_series = []
        for ticker, stock in self.__stocks.items():
            closing_prices_series.append(stock.history["Close"].rename(ticker)) #colocando o pd.Series da ação na lista, renomeando a série de 'Close' para o ticker
        self.__closing_prices_table = reduce(lambda x, y: pd.merge(x, y, left_index=True, right_index=True, how='outer'), closing_prices_series) #concatenando todas as pd.Series (colunas) em um único dataframe
        self.__closing_prices_table = self.__closing_prices_table[~self.__closing_prices_table.index.duplicated(keep="first")] #retira todas as ocorrências repetidas no index, deixando apenas a primeira
        self.__closing_prices_table = self.__closing_prices_table.fillna(method='ffill') #substui os NaNs do dataframe com o último preço válido (se não existir, continua NaN)



    def get_closing_prices_table(self):
        """
        Getter do atributo 'closing_prices_table', que armazena uma tabela com os preços de fechamento das ações do pregão.
        O atributo é declarado pelo getter, caso ainda não tenha sido.

        Returns
        -------
        DataFrame
            O dataframe com os preços de fechamento das ações do pregão.
        """
        try:
            return self.__closing_prices_table
        except:
            self.__set_closing_prices_table()
            return self.__closing_prices_table



    def __set_covariances_table(self):
        """
        Cria, a partir dos preços de fechamento, um dataframe com a matriz de covariância Ledoit-Wolf reduzida, referente as ações do pregão.

        OBS: A covariância é anualizada (referente aos retornos anualizados).
        """
        #utilizao o módulo risk_models da lib PyPortfolioOpt para calcular a matriz de covariância
        covariance_calculator = risk_models.CovarianceShrinkage(prices=self.closing_prices_table, frequency=SESSION_FREQ_PER_YEAR)
        self.__covariances_table = covariance_calculator.ledoit_wolf()



    def get_covariances_table(self):
        """
        Cria, a partir dos preços de fechamento, um dataframe com a matriz de covariância Ledoit-Wolf reduzida, referente as ações do pregão.
        O atributo é declarado pelo getter, caso ainda não tenha sido.

        OBS: A covariância é anualizada (referente aos retornos anualizados).

        Returns
        -------
        DataFrame
            O dataframe com as covariâncias entre as ações do pregão.
        """
        try:
            return self.__covariances_table
        except:
            self.__set_covariances_table()
            return self.__covariances_table



    def update_allocation_model(self, tickers="all"):
        """
        Cria um dicionário ordenado onde cada ticker de entrada é uma key e o valor é o seu peso de compra no mercado. Armazena no atributo 'buy_weights'.
        Cria uma série (pd.Series) onde cada ticker de entrada é uma linha e o valor é o retorno esperado pelo modelo. Armazena no atributo 'market_implied_rets'.

        O peso e o retorno esperado são calculados de acordo com o Modelo Black Litterman, que utiliza uma abordagem bayesiana para alocar os ativos.
        O retorno esperado para cada ação (sem inputs de previsões) é o risco com o qual a ação contribui para o mercado multiplicado pelo premium do risco (delta).
        É possível utilizar previsões futuras de cada ação para compor a alocação.

        OBS: O modelo não prevê resultados individuais das ações, apenas combina dados gerais do mercado e previsões já realizadas das ações para alocar ativos.
        OBS: Todos os retornos esperados, de input e output, são anualizados

        Parameters
        ----------
        tickers : list ou str
            A lista com todos os tickers que devem ser considerados pelo modelo de alocação de ativos. (default são todos os tickers do pregão)

        Raises
        ------
        TypeError
            Caso 'tickers' não seja uma lista.
        ValueError
            Caso 'tickers' seja uma string e não seja igual a 'all' ou 'active'.
        """
        #valida o tipo do parâmetro
        if not isinstance(tickers, (list, str)):
            raise TypeError("Argument 'tickers' must be a list or a string.")

        self.__set_covariances_table() #atualiza a tabela de covariância das ações

        #se tickers for uma string
        if isinstance(tickers, str):
            if tickers == "all":
                tickers = self.tickers
            elif tickers == "active":
                tickers = self.active_tickers
            else:
                raise ValueError("Argument tickers must be equal to 'all', 'active' or be a list of tickers.")

        covariances_table = self.__covariances_table.filter(items=tickers, axis=1) #filtra as colunas da tabela de covariancias para os tickers passados
        covariances_table = covariances_table.filter(items=tickers, axis=0) #filtra as linhas da tabela de covariancias para os tickers passados

        mcaps = {ticker:self.__stocks[ticker].market_cap for ticker in tickers} #dicionario com os market caps das ações do pregão
        #kurtosis = {ticker:self.__stocks[ticker].history["Close"].pct_change().dropna(how="all").kurtosis() for ticker in tickers}
        #views = expected_returns.mean_historical_return(self.__closing_prices_table.filter(items=tickers, axis=1), frequency=SESSION_FREQ_PER_YEAR) #teste

        #calcula o preço de risco do mercado, com base nos preços de fechamento do índice de mercado (iBovespa) e na taxa livre de risco (selic)
        delta = black_litterman.market_implied_risk_aversion(self.__market_index.history["Close"], frequency=SESSION_FREQ_PER_YEAR) #o preço de risco do mercado é utilizado para estimar os retornos de cada ação, com base em seus históricos

        """
        #------TESTES------
        market_prior = black_litterman.market_implied_prior_returns(
                mcaps, delta, covariances_table, self.__risk_free_rate
            )
        print(market_prior)
        print()
        #------------------
        """

        #utiliza a classe BlackLittermanModel da lib PyPortfolioOpt para criar o modelo
        bl_model = BlackLittermanModel(covariances_table, risk_aversion=delta, absolute_views={}, pi="market", market_caps=mcaps, risk_free_rate=self.__risk_free_rate) #é possível passar um dicionário com a previsão futura das ações pelo parâmetro 'absolute_views'

        bl_model.bl_weights() #calcula os pesos de cada ação com base no modelo Black Litterman
        self.__buy_weights = bl_model.clean_weights(cutoff=8e-3) #limpa os pesos arredondando os valores e cortando os valores perto de zero
        self.__market_implied_rets = bl_model.posterior_rets #retorno esperado com base no mercado para cada ação alocada
        bl_model.portfolio_performance(verbose=True) #teste



    def get_buy_weights(self):
        """
        Getter do atributo 'buy_weights', que armazena um dicionário ordenado com os pesos dos tickers passados no último update do modelo de alocação de ativos.
        O atributo é declarado pelo getter com os parâmetros de default, caso ainda não tenha sido declarado.

        Returns
        -------
        dict
            O dicionário com os pesos de compra do mercado para os tickers passados no último update do modelo de alocação de ativos.
        """
        try:
            return self.__buy_weights
        except:
            self.update_allocation_model()
            return self.__buy_weights



    def get_market_implied_rets(self):
        """
        Getter do atributo 'market_implied_rets', que armazena uma série onde cada ticker, passado no último update do modelo de alocação, é uma linha e o valor é o retorno previsto, implicado pelo mercado.
        O atributo é declarado pelo getter com os parâmetros de default, caso ainda não tenha sido declarado.

        OBS: Todos os retornos esperados são anualizados

        Returns
        -------
        Series
            Objeto Series com os retornos implicados pelo mercado, para cada ticker passado no último update do modelo de alocação de ativos.
        """
        try:
            return self.__market_implied_rets
        except:
            self.update_allocation_model()
            return self.__market_implied_rets
