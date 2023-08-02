from delfos.market.session import Session
from delfos.broker.position import Position
from delfos.common.configs import Configs
import delfos.common.utils as utils
import json
from datetime import datetime
import pandas as pd
import time #apenas para testes
import os
import math

CONFIGS = Configs()


CASH = CONFIGS.CASH[-1]["available_cash"] #dinheiro disponível para a última data registrada (último registro do patrimonio)
MOVEMENTS_PATH = CONFIGS.PATHS["movements_folder"] #caminho para a pasta com os arquivos de movimentação (compras e vendas). 1 arquivo xlsx por ano (baixado do CEI área logada).
CASH_FILE_PATH = CONFIGS.PATHS["cash"] #caminho para a pasta com o arquivo que contém as informações da parte do portfolio que não está alocada à ações.
NOW = datetime.now() #data do dia



def get_movements_list_from_b3_exports():
    """
    Analisa os documentos de movimentação baixados da B3 (área logada). É necessário 1 arquivo xlsx por ano, filtrados e baixados pelo próprio site.
    Os arquivos devem ser colocados na pasta: "./delfos/data/broker/movements/".
    Retorna as movientações extraídas dos documentos, já com a estrutura correta para a análise feita pelo script.

    URL: https://www.investidor.b3.com.br/login

    Returns
    -------
    list
        Lista de dicionários que representam a movimentação das ações (compras, vendas e dividendos). Cada movimentação possui: data, símbolo, tipo de movimentação, quantidade de ações, preço por ação e valor da operação.
    """

    movements_dfs = []

    for movement_file in os.listdir(MOVEMENTS_PATH):
        movements = pd.read_excel(MOVEMENTS_PATH / movement_file)
        movements_dfs.append(movements)

    if len(movements_dfs) == 0:
        return []

    movements = pd.concat(movements_dfs)
    movements = movements[movements["Movimentação"].isin(["Transferência - Liquidação", "Dividendo", "Juros Sobre Capital Próprio", "Rendimento"])]

    tickers = movements["Produto"].str.split("-").tolist()
    movements["Símbolo"] = list(map(lambda x: x[0].strip(), tickers))

    movements["Data"] = pd.to_datetime(movements["Data"], format="%d/%m/%Y")
    movements = movements.sort_values("Data")

    movements_list = []

    for i, row in movements.iterrows():
        movement = {}

        if (row["Movimentação"] == "Transferência - Liquidação" or row["Movimentação"] == "Bonificação em Ativos") and row["Entrada/Saída"] == "Credito":
            typ = "buy"
        elif row["Movimentação"] == "Transferência - Liquidação" and row["Entrada/Saída"] == "Débito":
            typ = "sell"
        elif (row["Movimentação"] == "Dividendo" or row["Movimentação"] == "Juros Sobre Capital Próprio" or row["Movimentação"] == "Rendimento") and row["Entrada/Saída"] == "Credito":
            typ = "dividends"
        else:
            continue

        if row["Preço unitário"] == "-":
            row["Preço unitário"] = 0

        if row["Valor da Operação"] == "-":
            row["Valor da Operação"] = 0

        movement["ticker"] = row["Símbolo"]
        movement["type"] = typ
        movement["price_per_share"] = float(row["Preço unitário"])
        try:
            movement["quantity"] = float(row["Quantidade"].replace(",", "."))

        except:
            movement["quantity"] = row["Quantidade"]
        movement["quantity"] = math.floor(movement["quantity"])
        movement["amount"] = float(row["Valor da Operação"])
        movement["date"] = row["Data"].strftime("%d-%m-%Y")

        movements_list.append(movement)

    return movements_list




class Portfolio():
    """
    Classe que representa um portfolio de ações. Possui uma sessão (pregão) de acordo com a data em que o portfolio será analisado.
    Também possui a variável 'cash', que representa o capital disponível para a realização de movimentações de compra de ações.
    Também deve ser passado por parâmetro a lista de movimentações já realizadas no portfolio. A lista vem da função 'get_movements_list_from_b3_exports()'.
    """

    def __init__(self, session, cash=CASH, movements=[]):
        """
        Parameters
        ----------
        session : Session
            O objeto Session que representa o pregão para a análise.
        cash : int ou float
            O valor em reais disponível para compra de ações.
        movements : lista de dicionários
            Lista com todas as movimentações do portfolio.

        Raises
        ------
        TypeError
            Se os parâmetros não baterem com seus respectivos tipos.
        ValueError
            Se o valor disponível para a compra de ações for menor que 0.
        """
        #checando se os tipos dos parâmetros estão corretos
        if not isinstance(session, Session):
            raise TypeError("Argument 'session' must be a Session object.")
        if not isinstance(cash, (int, float)):
            raise TypeError("Argument 'cash' must be an integer or a float.")
        if not isinstance(movements, list):
            raise TypeError("Argument 'movements' must be a list of dicts.")

        if cash < 0:
            raise ValueError("The portfolio's cash can't be lesser than 0.")

        self.__session = session
        self.__cash = cash
        self.__date = self.__session.date.date()
        self.__first_date = None
        if len(movements) == 0:
            self.__movements = get_movements_list_from_b3_exports()
        else:
            self.__movements = movements
        self.__parse_movements()



#--------------------------------------- GETTERS ---------------------------------------------------------#

    @property
    def session(self):
        return self.__session #pregão em que a carteira está sendo analisada

    @property
    def date(self):
        return self.__date #data em que a carteira está sendo analisada

    @property
    def first_date(self):
        return self.__first_date #data da primeira movimentação da carteira

    @property
    def cash(self):
        return self.__cash #dinheiro do portfolio disponível para compras

    @property
    def movements(self):
        return self.__movements #lista de movimentações do portfolio (compras, vendas e dividendos)

    @property
    def positions(self):
        return self.__positions #dicionário de posições do portfolio ({ticker: Position})

    @property
    def failed_positions(self):
        return self.__failed_positions #tickers que por algum motivo falharam durante o processo de criação das posições

    @property
    def total_cost(self):
        return self.__total_cost #custo total do portfolio

    @property
    def total_income(self):
        return self.__total_income #total realizado pelo portfolio (vendas + dividendos)

    @property
    def total_selled(self):
        return self.__total_selled #total em vendas realizadas pelo portfolio

    @property
    def total_dividends(self):
        return self.__total_dividends #total recebido em dividendos pelo portfolio

    @property
    def portfolio_history(self):
        return self.get_portfolio_history() #dataframe com a série histórica de preços do portfolio

    @property
    def held_shares_cost(self):
        return self.get_held_shares_cost() #custo das ações mantidas (não contam as que foram vendidas)

    @property
    def held_shares_value(self):
        return self.get_held_shares_value() #valor das ações mantidas (não contam as vendidas e nem os dividendos)

    @property
    def held_shares_change(self):
        return self.get_held_shares_change() #diferença entre o valor das ações mantidas e seus custos (não contam as vendidas e nem os dividendos)

    @property
    def held_shares_return(self):
        return self.get_held_shares_return() #rentabilidade das ações mantidas (não contam as vendidas e nem os dividendos)

    @property
    def total_value(self):
        return self.get_total_value() #valor total que o portfolio já obteve (ações mantidas + dividendos + ações vendidas - custo total)

    @property
    def total_change(self):
        return self.get_total_change() #diferença total do portfolio (contando vendas e dividendos)

    @property
    def total_return(self):
        return self.get_total_return() #rentabilidade total do portfolio (contando vendas e dividendos)

#---------------------------------------------------------------------------------------------------------#



    def is_current_session(self):
        """
        Checa se o pregão de análise é o pregão atual.
        """
        now = datetime.now()
        if self.__date == now.date() and utils.is_market_hours():
            return True
        else:
            return False



    def __parse_movements(self):
        """
        Lê as movimentações e estrutura as posições da carteira para a data de análise.
        Além disto, também soma os valores totais da carteira, extraídos de todas as movimentações.

        Raises
        ------
        TypeError
            Se os parâmetros extraídos dos documentos de movimentação não baterem com seus respectivos tipos.
        ValueError
            Se a quantidade de ações ou o preço por ação de alguma movimentação for menor que 0.
            Se a data das movimentações não estiver no formato '%d-%m-%Y'.
            Se o tipo das movimentações não for "buy", "sell" ou "dividends"
        """
        self.__parsed_movements = {"total": {}}
        self.__failed_positions = [] #lista com as posições cuja as ações não estejam na sessão
        #para cada movimento na carteira
        for i, movement in enumerate(self.__movements):

            if not isinstance(movement["ticker"], str):
                raise TypeError("All movement's ticker on movements json must be a string.")
            if not isinstance(movement["type"], str):
                raise TypeError("All movement's type on movements json must be a string.")
            if not isinstance(movement["price_per_share"], (int, float)):
                raise TypeError("All movement's price_per_share on movements json must be a integer or a float.")
            if not isinstance(movement["quantity"], (int, float)):
                raise TypeError("All movement's quantity on movements json must be a integer or a float.")
            if not isinstance(movement["date"], str):
                raise TypeError("All movement's date on movements json must be a string.")

            if movement["price_per_share"] < 0:
                raise ValueError("All movement's price_per_share on movements json must be greater than 0.")
            if movement["quantity"] < 0:
                raise ValueError("All movement's quantity on movements json must be greater than 0.")

            try:
                movement_date = datetime.strptime(movement["date"], '%d-%m-%Y').date()
            except:
                raise ValueError("All movement's date on movements json must have the '%d-%m-%Y' format.")

            #se o movimento tiver sido realizado até a data do pregão em que a carteira está inserida
            if movement_date <= self.__date:

                #corrigindo a quantidade e o preço por ação para os stocks splits do periodo
                stock = self.__session.select_stocks(movement["ticker"])
                if isinstance(stock, list) and len(stock) == 0:
                    if movement["ticker"] not in self.__failed_positions:
                        self.__failed_positions.append(movement["ticker"])
                    continue

                if i == 0:
                    self.__first_date = movement_date

                for i, row in stock.history[(stock.history["Stock Splits"] > 0) & (stock.history.index.date > movement_date)].iterrows():
                    movement["quantity"] = int(math.floor(movement["quantity"] * row["Stock Splits"]))
                    movement["price_per_share"] = movement["price_per_share"] / row["Stock Splits"]

                if movement["date"] not in self.__parsed_movements:
                    if movement["ticker"] not in self.__parsed_movements["total"]:
                        self.__parsed_movements["total"].update({movement["ticker"]: {"quantity": 0, "selled": 0, "bought_quantity": 0, "cost": 0, "income": 0}})

                    self.__parsed_movements.update({movement["date"]: {}})
                    self.__parsed_movements[movement["date"]].update({movement["ticker"]: dict(self.__parsed_movements["total"][movement["ticker"]])})

                else:
                    if movement["ticker"] not in self.__parsed_movements["total"]:
                        self.__parsed_movements["total"].update({movement["ticker"]: {"quantity": 0, "selled": 0, "bought_quantity": 0, "cost": 0, "income": 0}})

                    if movement["ticker"] not in self.__parsed_movements[movement["date"]]:
                        self.__parsed_movements[movement["date"]].update({movement["ticker"]: dict(self.__parsed_movements["total"][movement["ticker"]])})

                if movement["type"] == "buy":
                    self.__parsed_movements[movement["date"]][movement["ticker"]]["quantity"] += movement["quantity"]
                    self.__parsed_movements[movement["date"]][movement["ticker"]]["bought_quantity"] += movement["quantity"]
                    self.__parsed_movements[movement["date"]][movement["ticker"]]["cost"] += movement["price_per_share"] * movement["quantity"]

                    self.__parsed_movements["total"][movement["ticker"]]["quantity"] += movement["quantity"]
                    self.__parsed_movements["total"][movement["ticker"]]["bought_quantity"] += movement["quantity"]
                    self.__parsed_movements["total"][movement["ticker"]]["cost"] += movement["price_per_share"] * movement["quantity"]

                elif movement["type"] == "sell":
                    self.__parsed_movements[movement["date"]][movement["ticker"]]["quantity"] -= movement["quantity"]
                    self.__parsed_movements[movement["date"]][movement["ticker"]]["selled"] += movement["price_per_share"] * movement["quantity"]
                    self.__parsed_movements[movement["date"]][movement["ticker"]]["income"] += movement["price_per_share"] * movement["quantity"]

                    self.__parsed_movements["total"][movement["ticker"]]["quantity"] -= movement["quantity"]
                    self.__parsed_movements["total"][movement["ticker"]]["selled"] += movement["price_per_share"] * movement["quantity"]
                    self.__parsed_movements["total"][movement["ticker"]]["income"] += movement["price_per_share"] * movement["quantity"]

                elif movement["type"] == "dividends":
                    self.__parsed_movements[movement["date"]][movement["ticker"]]["income"] += movement["amount"]
                    self.__parsed_movements["total"][movement["ticker"]]["income"] += movement["amount"]

                else:
                    raise ValueError("All movement's type on movements json must be equal to 'sell', 'buy' or 'dividends'.")

        self.__positions = {} #dicionário com as posições atuais da carteira {ticker: position}

        self.__total_cost = 0 #total gasto em ações (em $)
        self.__total_income = 0 #total vendido em ações + proventos (em $)
        self.__total_selled = 0 #total vendido em ações (em $)
        self.__total_dividends = 0 #total ganho em proventos (em $)

        #para cada ação parseada nos movimentos da carteira
        for ticker in self.__parsed_movements["total"]:

            #descobrindo informações para a adição das posições atuais da carteira
            cost = self.__parsed_movements["total"][ticker]["cost"]
            income = self.__parsed_movements["total"][ticker]["income"]
            selled = self.__parsed_movements["total"][ticker]["selled"]
            dividends = income - selled

            if int(self.__parsed_movements["total"][ticker]["bought_quantity"]) > 0:
                price_per_share = cost / int(self.__parsed_movements["total"][ticker]["bought_quantity"])
            else:
                price_per_share = 0

            quantity = int(self.__parsed_movements["total"][ticker]["quantity"])

            self.__add_position(ticker, quantity, price_per_share, cost, income, selled)

            self.__total_cost += cost
            self.__total_income += income
            self.__total_selled += selled
            self.__total_dividends += dividends

        self.__set_history()



    def __add_position(self, ticker, quantity, price_per_share, cost, income, selled):
        """
        Adiciona uma posição ao portfolio. cada posição é representada por um objeto 'Position'.
        Não levanta nenhum tipo de erro pois o método é utilizado apenas internamente pelo programa.

        Parameters
        ----------
        ticker : str
            Símbolo da ação da nova posição.
        quantity : int
            Quantidade de ações da nova posição.
        price_per_share : float
            O preço pago por cada ação individual da posição.
        cost : float
            O custo total da posição.
        income : float
            Todo a receita de fato realizada pela posição (por vendas ou por dividendos).
        selled :
            Todo valor obtido através de vendas das ações da posição.
        """
        stock = self.__session.select_stocks(ticker)
        #se a ação não está ativa no pregão em que a carteira está operando
        if isinstance(stock, list) and len(stock) == 0:
            if ticker not in self.__failed_positions:
                self.__failed_positions.append(ticker)
        else:
            self.__positions[ticker] = Position(stock, quantity, price_per_share, cost, income, selled)



    def add_movement(self, ticker, quantity, price_per_share, type="buy", date=NOW):
        """
        Permite ao próprio usuário adicionar uma movimentação ao portfolio.
        Método utilizado durante o pregão, quando a movimentação feita ainda não foi para os documentos da B3.
        Só é possível adicionar a movimentação se o pregão for o atual e a data da movimentação for a mesma do pregão.

        Parameters
        ----------
        ticker : str
            Símbolo da ação da movimentação.
        quantity : int
            Quantidade de ações da movimentação.
        price_per_share : float
            O preço pago por cada ação individual da movimentação.
        type : str
            O tipo da movimentação. (Compra ou Venda)
        date : datetime
            A data da movimentação. (default é a data atual)

        Raises
        ------
        TypeError
            Se os parâmetros não baterem com seus respectivos tipos.
        ValueError
            Se a quantidade de ações ou o preço por ação da movimentação for menor que 0.
            Se o tipo da movimentação não for "buy", "sell" ou "dividends"

        Returns
        -------
        bool
            Retorna se a operação de movimentação foi um sucesso.
        str
            Caso a operação de movimentação tenha falhado, retorna uma mensagem de erro. Caso seja bem sucedida, retorna uma string vazia.
        """
        if not isinstance(ticker, str):
            raise TypeError("Argument 'ticker' must be a string.")
        if not isinstance(type, str):
            raise TypeError("Argument 'type' must be a string.")
        if not isinstance(price_per_share, (int, float)):
            raise TypeError("Argument 'price_per_share' must be an integer or a float.")
        if not isinstance(quantity, int):
            raise TypeError("Argument 'quantity' must be an integer.")
        if not isinstance(date, datetime):
            raise TypeError("Argument 'date' must be a datetime object.")

        if price_per_share < 0:
            raise ValueError("Argument 'price_per_share' must be greater than 0.")
        if quantity < 0:
            raise ValueError("Argument 'quantity' must be greater than 0.")
        if type != "buy" and type != "sell":
            raise ValueError("Argument 'type' must be equal to 'sell' or 'buy'.")

        date_string = date.strftime('%d-%m-%Y')
        success = False #assume inicialmente que a movimentação é inválida
        error_message = "" #mensagem explicando porque a movimentação não é válida
        #se a movimentação ocorreu na data do pregão em que a carteira está operando e o pregão é o atual em andamento
        if self.__date == date.date() and self.is_current_session():
            if type == "buy":
                #verifica se há caixa para realizar a compra
                if self.__cash - quantity * price_per_share >= 0:
                    self.__cash -= quantity * price_per_share #atualiza a quantidade em caixa da carteira
                    success = True
                else:
                    error_message = "Invalid movement. Not enough cash."
            else:
                #verifica se a carteira tem toda a quantia de ações para a venda
                if self.__positions[ticker].quantity >= quantity:
                    self.__cash += quantity * price_per_share #atualiza a quantidade em caixa da carteira
                    success = True
                else:
                    error_message = "Invalid movement. Not enough shares."
        #se a movimentação ocorreu antes do pregão em que a carteira está operando (cash já foi descontado)
        elif self.__date >= date.date():
            success = True
        #movimentação não pode ocorrer depois da data do pregão em que a carteira está operando
        else:
            error_message = "Invalid movement. The movement's date can't be after the portfolio's session date."

        if success == True:
            self.__movements.append({"ticker": ticker, "type": type, "price_per_share": price_per_share, "quantity": quantity, "amount":quantity*price_per_share , "date": date_string})
            self.__parse_movements() #atualiza os movimentos da carteira
            #self.update_cash_file()
        return success, error_message



    def add_cash(self, amount):
        """
        Permite ao próprio usuário adicionar dinheiro ao dinheiro disponível no portfolio para compras.

        Parameters
        ----------
        amount : float
            Valor em reais adicionados ao dinheiro disponível para movimentações do portfolio.

        Raises
        ------
        TypeError
            Se o valor adicionado não for float ou int.
        ValueError
            Se a quantidade adicionada for menor que 0.
        """
        if not isinstance(amount, (int, float)):
            raise TypeError("Argument 'amount' must be an integer or a float.")
        if amount < 0:
            raise ValueError("Argument 'amount' must be greater than 0.")

        if amount != 0:
            self.__cash += amount
            #self.update_cash_file()



    def withdraw_cash(self, amount):
        """
        Permite ao próprio usuário retirar dinheiro do dinheiro disponível no portfolio para compras.

        Parameters
        ----------
        amount : float
            Valor em reais retirados do dinheiro disponível para movimentações do portfolio.

        Raises
        ------
        TypeError
            Se o valor retirado não for float ou int.
        ValueError
            Se a quantidade retirada for menor que 0 ou maior que a quantidade disponível.
        """
        if not isinstance(amount, (int, float)):
            raise TypeError("Argument 'amount' must be an integer or a float.")
        if amount < 0:
            raise ValueError("Argument 'amount' must be greater than 0.")
        if amount > self.__cash: #talvez seja melhor um logging do que erro
            raise ValueError("Argument 'amount' must be lesser or equal to the portfolio's cash.")

        if amount != 0:
            self.__cash -= amount
            #self.update_cash_file()



    def __set_history(self):
        """
        Cria o histórico de preços do portfolio como um todo, a partir das posições. (Série histórica)
        O histórico é um dataframe (datetime index) e apresenta as seguintes colunas:
            - Close: Valor de fechamento do portfolio na data
            - Cost: Custo total do portfolio na data
            - Close (no income): Valor de fechamento do portfolio menos o valore realizado (dividendos e vendas)
            - Cash Flow: Valor adicionado ou retirado do portfolio na data
            - Daily Change (w/ CF): Diferença de valor do portfolio entre a data atual e a anterior (contando cash flow)
            - Daily Change:  Diferença de valor do portfolio entre a data atual e a anterior (sem contar cash flow)
            - Total Change: Diferença de valor total do portfolio. (Valor atual - Valor inicial)
            - Daily Ret: Rentabilidade do portfolio entre a data atual e a anterior
            - Total Ret: Rentabilidade total do portfolio
        """
        tickers_df = {}
        for date in self.__parsed_movements:
            if date != "total":
                for ticker in self.__parsed_movements[date]:
                    date_df = pd.DataFrame.from_dict({date: self.__parsed_movements[date][ticker]}, "index")
                    date_df.index = pd.to_datetime(date_df.index, format="%d-%m-%Y")
                    date_df["ticker"] = ticker

                    if ticker not in tickers_df:
                        tickers_df.update({ticker: [date_df]})
                    else:
                        tickers_df[ticker].append(date_df)

        self.__portfolio_history = pd.DataFrame(columns=["Close", "Cost"])

        for i, ticker in enumerate(tickers_df):
            ticker_df = pd.concat(tickers_df[ticker])
            position = self.__positions[ticker]
            position.set_history(ticker_df)

            if i == 0:
                self.__portfolio_history["Close"] = position.history["Close"]
                self.__portfolio_history["Close (no income)"] = position.history["Close (no income)"]
                self.__portfolio_history["Cost"] = position.history["Cost"]

            else:
                self.__portfolio_history["Close"] = self.__portfolio_history["Close"].add(position.history["Close"], fill_value=0)
                self.__portfolio_history["Close (no income)"] = self.__portfolio_history["Close (no income)"].add(position.history["Close (no income)"], fill_value=0)
                self.__portfolio_history["Cost"] = self.__portfolio_history["Cost"].add(position.history["Cost"], fill_value=0)

        self.__portfolio_history["Cash Flow"] = self.__portfolio_history["Cost"].diff()
        self.__portfolio_history["Cash Flow"].iloc[0] = self.__portfolio_history["Cost"].iloc[0]
        self.__portfolio_history["Daily Change w/ CF"] = self.__portfolio_history["Close"].diff()
        self.__portfolio_history["Daily Change"] = self.__portfolio_history["Daily Change w/ CF"] - self.__portfolio_history["Cash Flow"]
        self.__portfolio_history["Total change"] = (self.__portfolio_history["Close"].sub(self.__portfolio_history["Cost"], fill_value=0))
        self.__portfolio_history["Pct Change w/ CF"] = self.__portfolio_history["Close"].pct_change()
        self.__portfolio_history["Daily Ret"] = ( self.__portfolio_history["Close"].diff() - self.__portfolio_history["Cost"].diff() ) / (self.__portfolio_history["Cost"].diff() +  self.__portfolio_history["Close"].shift(1))
        self.__portfolio_history["Total Ret"] = ((self.__portfolio_history["Close"].sub(self.__portfolio_history["Cost"], fill_value=0)) / self.__portfolio_history["Cost"])



    def get_portfolio_history(self):
        """
        Getter do histórico do portfolio.

        Returns
        -------
        Dataframe
            Histórico do portfolio.
        """
        return self.__portfolio_history



    def get_held_shares_cost(self):
        """
        Cálcula através das posições da carteira o custo das ações atuais (não conta as vendidas/realizadas)

        Returns
        -------
        Float
            Custo das ações mantidas
        """
        self.__held_shares_cost = 0
        for ticker in self.__positions:
            self.__held_shares_cost += self.__positions[ticker].held_shares_cost
        return self.__held_shares_cost



    def get_held_shares_value(self):
        """
        Cálcula através das posições da carteira o valor das ações atuais (não conta as vendidas/realizadas)

        Returns
        -------
        Float
            Valor das ações mantidas
        """
        self.__held_shares_value = 0
        for ticker in self.__positions:
            self.__held_shares_value += self.__positions[ticker].held_shares_value
        return self.__held_shares_value



    def get_held_shares_change(self):
        """
        Cálcula a diferença entre as ações atuais e seus custos (não conta as vendidas/realizadas)

        Returns
        -------
        Float
            Diferença entre o valor das ações atuais e seus custos
        """
        return self.held_shares_value - self.held_shares_cost



    def get_held_shares_return(self):
        """
        Cálcula a rentabilidade entre as ações atuais (não conta as vendidas/realizadas)

        Returns
        -------
        Float
            Rentabilidade das ações atuais e seus custos
        """
        if self.held_shares_cost > 0:
            self.__held_shares_return = (self.held_shares_change / self.held_shares_cost )
        else:
            self.__held_shares_return = 0
        return self.__held_shares_return



    def get_total_value(self):
        """
        Cálcula o valor total que o portfolio já obteve (ações mantidas + dividendos + ações vendidas)

        Returns
        -------
        Float
            Valor total que o portfolio já obteve
        """
        return self.total_income + self.held_shares_value



    def get_total_change(self):
        """
        Cálcula a diferença total que o portfolio já obteve (ações mantidas + dividendos + ações vendidas - custo total)

        Returns
        -------
        Float
            Diferença total do portfolio
        """
        self.__total_change = 0
        for ticker in self.__positions:
            self.__total_change += self.__positions[ticker].total_change
        return self.__total_change



    def get_total_return(self):
        """
        Cálcula a rentabilidade total do portfolio (ações mantidas + dividendos + vendas)

        Returns
        -------
        Float
            Rentabilidade total do portfolio
        """
        if self.total_cost > 0:
            self.__total_return = (self.total_change / self.total_cost )
        else:
            self.__total_return = 0
        return self.__total_return




#cost = valor gasto com todas as compras que a carteira já teve                                                       ok
#income = valor ganho com todas as vendas que a carteira já teve + proventos                                          ok
#held_shares_cost = valor inicial da carteira (posições atuais)                                                       ok
#held_shares_value = valor atual da carteira (posições atuais)                                                        ok
#total_change = valor atual da carteira menos o valor gasto com as posições atuais                                    ok
#current_return = ((held_shares_value - held_shares_cost) / held_shares_cost ) * 100                                  ok

#profit = income - cost + held_shares_cost
#ROI =  ( ( income - cost) / (cost) ) * 100
#total_return = ( ( total_value - cost ) / cost ) * 100                                                               ok
