import numpy as np
import ccxt
import time
import requests
import json
import time


class Hedge:
    def __init__(self, api_id, api_secret, symbol, threshold, strike, price_change_percent, hedged_once=False):
        """
        Initializing Hedge class.
        Parameters
        ----------
        api_id: string
            The `api_id` can be found under API management under account settings.
        api_secret: string
            The `api_secret` can be found under API management under account settings.
        symbol: string (default "BTC")
            The asset you wish to delta-hedge. Currently only "BTC" and "ETH" are supported.
        threshold: float (default 0.10)
            The maximum absolute value of delta exposure to have at any given time. The default
            value is currently 0.10 which means the portfolio delta will fluctuate between -0.10 to 0.10 
            of whichever asset you are trading. Any breach beyond this level will result in the portfolio 
            being delta-hedged.

        Example
        ---------
        >>> import delta_hedge
        >>> id = "..." # replace your `api_id` in the quotes
        >>> secret = "..." # replace your `api_secret` in the quotes
        >>> dh = delta_hedge.Hedge(api_id=id, api_secret=secret, symbol="BTC", threshold=0.10)
        """
        self.load = ccxt.deribit({'apiKey': api_id, 'secret': api_secret})
        self.symbol = symbol
        self.threshold = abs(float(threshold))
        self.strike = strike
        self.price_change_percent = price_change_percent

        self.hedged_once = hedged_once  # Initialized to False to keep track of whether an initial hedge has been executed.

        if ((self.symbol != 'BTC') and (self.symbol != 'ETH')):
            raise ValueError(
                "Incorrect symbol - please choose between 'BTC' or 'ETH'")

    def current_index_price(self):
        instrument_name = f'{self.symbol.lower()}_usd'
        url = f'https://www.deribit.com/api/v2/public/get_index_price?index_name={instrument_name}'
        response = requests.get(url)
        index_price = response.json()['result']['index_price']
        return index_price

    def current_delta(self):
        """
        Retrives the current portfolio delta.

        Example
        ---------
        >>> dh.current_delta()
        0.065
        """
        return float(self.load.fetch_balance({'currency': str(self.symbol)})['info']['delta_total'])

    def delta_hedge(self):
        """
        Rebalances entire portfolio to be delta-neutral based on current delta exposure.
        """
        current_delta = self.current_delta()
        print(f'Current delta is {current_delta}.')
        # if delta is negative, we must BUY futures to hedge our negative exposure
        if current_delta < 0:
            sign = 'buy'
        # if delta is positive, we must SELL futures to hedge our positive exposure
        if current_delta > 0:
            sign = 'sell'
        # retrieve the average price of the perpetual future contract for the asset
        # average of the open, high, low, close prices in last 1min interval.
        avg_price = np.mean(self.load.fetch_ohlcv(
            str(self.symbol)+"-PERPETUAL", limit=10)[-1][1:5])
        # if the absolute delta exposure is greater than our threshold then we place a hedging trade
        if abs(current_delta) >= self.threshold:
            asset = str(self.symbol) + "-PERPETUAL"
            order_size = abs(current_delta*avg_price)
            self.load.create_market_order(asset, sign, order_size)
            self.hedged_once = True  # Update the hedged_once status after executing a hedge
            print("Rebalancing trade to achieve delta-neutral portfolio:",
                  str(sign), str(order_size/avg_price), str(self.symbol))
        else:
            pass
            print("No need to hedge. Current portfolio delta:", current_delta)

    def run_loop(self):
        """
        Runs the delta-hedge script every hr to check the delta.

        Initially, checks the current index price every minute. 
        After an initial hedge is executed and perps_size is not 0, it will delta hedge every hourly.
        
        """
        while True:
            try:
                current_index = self.current_index_price() 

                # Get Perps position size
                positions = self.load.fetchPositions(
                    symbols=[f'{self.symbol}-PERPETUAL'], params={})
                if positions:
                    perps_size = positions[0]['info'].get('size', 0)
                else:
                    perps_size = 0
                perps_size = float(perps_size)
                print(f"\nPerps Size = {perps_size}\n")

                
                # Hedging logic
                
                # Calculate upper strike price levels
                upper_level_strike = self.strike + \
                    (self.strike * self.price_change_percent)

                if current_index > upper_level_strike:
                    print("Delta hedge function running...")
                    self.delta_hedge()

                # Calculate lower strike price levels
                lower_level_strike = self.strike - \
                    (self.strike * self.price_change_percent)

                if current_index < lower_level_strike:
                    print("Delta hedge function running....")
                    self.delta_hedge()

                # To cater for scenario when mkt turns around after hedging (unhedge)
                if perps_size != 0:
                # if perps_size < 0 and self.strike < current_index > lower_level_strike:
                    self.delta_hedge()
                

                # Print levels
                print(f"Upper Level: {upper_level_strike}")
                print(f"Lower Level: {lower_level_strike}")
                
                current_time = time.strftime('%H:%M:%S', time.localtime())
                print(current_time)
                
                print(f"Hedged Once Flag = {self.hedged_once}")
                print("\n")
                
                # Update the sleep interval
                if self.hedged_once and perps_size != 0:
                    sleep_interval = 3600  # 1 hr
                else:
                    sleep_interval = 60  # 1 minute

                time.sleep(sleep_interval)

            except Exception as e:
                print(
                    "Script is broken - trying again in 30 seconds. Current portfolio delta:", self.current_delta())
                print("Error:", str(e))
                time.sleep(30)
                pass
