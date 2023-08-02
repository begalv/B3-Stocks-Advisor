from delfos.market.stock import Stock
import pandas as pd



class Position():
    """
    Classe que representa uma posição. Possui uma ação, a quantidade atual de ações mantidas e o preço médio pago por unidade. O id é a ação.
    Também possui um total gasto, referente a quantidade total de ações compradas (não só a quantidade atual) e um total ganho, para todas as vendas realizadas.
    """

    def __init__(self, stock, quantity, price_per_share, total_cost=0, total_income=0, total_selled=0):
        """
        Parameters
        ----------
        stock : Stock
            O objeto Stock que representa a ação da posição.
        quantity : int
            O quantidade de ações da posição
        price_per_share : float
            O preço médio pago por ação
        total_cost : float
            O custo total da posição (contando o custo das ações que já foram vendidas)
        total_income : float
            O valor total realizado pela posição (contando as vendas e os dividendos)
        total_selled : float
            O valor total vendido pela posição

        Raises
        ------
        TypeError
            Se os parâmetros não baterem com seus respectivos tipos.
        ValueError
            Se a quantidade de ações, preço por ação, custo total, receita total ou total vendido for menor que 0.
        """
        #checando se os tipos dos parâmetros estão corretos
        if not isinstance(stock, Stock):
            raise TypeError("Argument 'stock' must be a Stock object.")
        if not isinstance(price_per_share, (int, float)):
            raise TypeError("Argument 'price_per_share' must be an integer or a float.")
        if not isinstance(quantity, (int, float)):
            raise TypeError("Argument 'quantity' must be an integer or a float.")
        if not isinstance(total_cost, (int, float)):
            raise TypeError("Argument 'total_cost' must be an integer or a float.")
        if not isinstance(total_income, (int, float)):
            raise TypeError("Argument 'total_income' must be an integer or a float.")
        if not isinstance(total_selled, (int, float)):
            raise TypeError("Argument 'total_selled' must be an integer or a float.")

        if quantity < 0:
            raise ValueError("Argument 'quantity' must be greater or equal 0.")
        if price_per_share <= 0:
            raise ValueError("Argument 'price_per_share' must be greater than 0.")
        if total_cost < 0:
            raise ValueError("Argument 'total_cost' must be greater or equal 0.")
        if total_income < 0:
            raise ValueError("Argument 'total_income' must be greater or equal 0.")
        if total_selled < 0:
            raise ValueError("Argument 'total_selled' must be greater or equal 0.")

        self.__stock = stock
        self.__quantity = quantity
        self.__is_active = self.is_active()
        self.__price_per_share = price_per_share
        self.__held_shares_cost = self.__price_per_share * self.__quantity

        if total_cost == 0:
            self.__total_cost = self.__held_shares_cost
        else:
            self.__total_cost = total_cost

        self.__total_income = total_income
        self.__total_selled = total_selled
        self.__total_dividends = total_income - total_selled
        self.__selled_quantity = (self.__total_cost / self.__price_per_share) - self.__quantity

        if self.__selled_quantity > 0 and self.__total_selled > 0:
            self.__price_per_sold_share = self.total_selled / int(self.__selled_quantity)
        else:
            self.__price_per_sold_share = 0



#--------------------------------------- GETTERS ---------------------------------------------------------#

    @property
    def stock(self):
        return self.__stock #objeto Stock que representa a ação da posição

    @property
    def quantity(self):
        return int(self.__quantity) #quantidade de ações da posição

    @property
    def is_active(self):
        return self.__is_active #se a posição está ativa (se existem ações mantidas ou todas foram vendidas)

    @property
    def total_cost(self):
        return self.__total_cost #custo total da posição (contando o custo das ações vendidas)

    @property
    def total_income(self):
        return self.__total_income #valor total realizado pela posição (contando vendas e dividendos)

    @property
    def total_selled(self):
        return self.__total_selled #valor total vendido pela posição

    @property
    def selled_quantity(self):
        return self.__selled_quantity #quantidade total de ações vendidas pela posição

    @property
    def price_per_sold_share(self):
        return self.__price_per_sold_share #preço médio obtido pela venda de cada ação da posição

    @property
    def total_dividends(self):
        return self.__total_dividends #total em dividendos recebido pela posição

    @property
    def price_per_share(self):
        return self.__price_per_share #custo médio pago por cada ação da posição

    @property
    def held_shares_cost(self):
        return self.get_held_shares_cost() #custo das ações mantidas da posição (não conta os custos das ações vendidas)

    @property
    def held_shares_value(self):
        return self.get_held_shares_value() #valor das ações mantidas pela posição (não contam vendas e dividendos)

    @property
    def total_change(self):
        return self.get_total_change() #diferença total da posição (valor total - custo total)

    @property
    def held_shares_change(self):
        return self.get_held_shares_change() #diferença entre o valor das ações mantidas e seus custos (não contam as vendidas e nem os dividendos)

    @property
    def total_return(self):
        return self.get_total_return()  #rentabilidade total da posição (contando vendas e dividendos)

    @property
    def total_value(self):
        return self.get_total_value() #valor total que a posição já obteve (ações mantidas + dividendos + ações vendidas - custo total)

    @property
    def held_shares_return(self):
        return self.get_held_shares_return() #rentabilidade das ações mantidas (não contam as vendidas e nem os dividendos)

    @property
    def history(self):
        return self.get_history()  #dataframe com a série histórica de preços da posição

#---------------------------------------------------------------------------------------------------------#



    def is_active(self):
        """
        Checa se a posição ainda está ativa. (Ainda possui ações mantidas)

        Returns
        -------
        Bool
            Se a posição ainda possui ações ativas (não vendidas)
        """
        if self.__quantity == 0:
            return False
        else:
            return True



    def get_held_shares_cost(self):
        """
        Cálcula o custo das ações atuais (não conta as vendidas/realizadas)

        Returns
        -------
        Float
            Custo das ações mantidas
        """
        return self.__held_shares_cost



    def get_held_shares_value(self):
        """
        Cálcula o valor das ações atuais (não conta as vendidas/realizadas)

        Returns
        -------
        Float
            Valor das ações mantidas
        """
        return self.__stock.current_price * self.__quantity



    def get_held_shares_change(self):
        """
        Cálcula a diferença entre as ações atuais e seus custos (não conta as vendidas/realizadas)

        Returns
        -------
        Float
            Diferença entre o valor das ações atuais e seus custos
        """
        return self.held_shares_value - self.__held_shares_cost



    def get_held_shares_return(self):
        """
        Cálcula a rentabilidade entre as ações atuais (não conta as vendidas/realizadas)

        Returns
        -------
        Float
            Rentabilidade das ações atuais e seus custos
        """
        return self.held_shares_change / self.__held_shares_cost



    def get_total_change(self):
        """
        Cálcula a diferença total que a posição já obteve (ações mantidas + dividendos + ações vendidas - custo total)

        Returns
        -------
        Float
            Diferença total da posição
        """
        return self.total_income + self.held_shares_value - self.__total_cost



    def get_total_return(self):
        """
        Cálcula a rentabilidade total da posição (ações mantidas + dividendos + vendas)

        Returns
        -------
        Float
            Rentabilidade total da posição
        """
        return self.total_change / self.__total_cost



    def get_total_value(self):
        """
        Cálcula o valor total que a posição já obteve (ações mantidas + dividendos + ações vendidas)

        Returns
        -------
        Float
            Valor total que a posição já obteve
        """
        return self.total_income + self.held_shares_value



    def set_history(self, history):
        """
        Cria o histórico (Série histórica) de preços da posição, a partir dos movimentos extraídos pela classe Portfolio.
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

        Parameters
        ----------
         Dataframe
            dataframe com as movimentações da posição, extraídas pela classe Portfolio. Também é possível passar o histórico manualmente por argumento.
        """
        self.__history = history

        hist = self.__stock.history["Close"]
        hist = hist[hist.index >= self.__history.index[0]]

        self.__history = self.__history.merge(hist, left_index=True, right_index=True, how="outer")
        self.__history = self.__history.fillna(method='ffill') #substui os NaNs do dataframe com o último preço válido (se não existir, continua NaN)
        self.__history = self.__history.rename(columns={"ticker": "Ticker", "quantity": "Quantity", "selled": "Selled", "bought_quantity": "Bought Quantity", "cost": "Cost", "income": "Income", "Close": "Stock Close"})

        self.__history["Close"] = self.__history["Stock Close"] * self.__history["Quantity"] + self.__history["Income"]
        self.__history["Close (no income)"] = self.__history["Stock Close"] * self.__history["Quantity"]
        self.__history["Cash Flow"] = self.__history["Cost"].diff()
        self.__history["Cash Flow"].iloc[0] = self.__history["Cost"].iloc[0]
        self.__history["Daily Change w/ CF"] = self.__history["Close"].diff()
        self.__history["Daily Change"] = self.__history["Daily Change w/ CF"] - self.__history["Cash Flow"]
        self.__history["Total change"] = (self.__history["Close"].sub(self.__history["Cost"], fill_value=0))
        self.__history["Pct Change w/ CF"] = self.__history["Close"].pct_change()
        self.__history["Daily ret"] = ( self.__history["Close"].diff() - self.__history["Cost"].diff() ) / (self.__history["Cost"].diff() +  self.__history["Close"].shift(1))
        self.__history["Total Ret"] = ((self.__history["Close"].sub(self.__history["Cost"], fill_value=0)) / self.__history["Cost"])



    def get_history(self):
        """
        Getter do histórico da posição.

        Returns
        -------
        Dataframe
            Histórico da posição.
        """
        return self.__history
