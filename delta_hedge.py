import numpy as np
import ccxt
import time
import requests
import json
import time


class Hedge:
    def __init__(self, api_id, api_secret, symbol, threshold, strike, price_change_percent, hedged_once=False, telegram_token=None, telegram_chat_id=None):
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
        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id

        self.hedged_once = hedged_once  # Initialized to False to keep track of whether an initial hedge has been executed.

        if ((self.symbol != 'BTC') and (self.symbol != 'ETH')):
            raise ValueError(
                "Incorrect symbol - please choose between 'BTC' or 'ETH'")
        
    def send_telegram_message(self, message):
        """
        Sends a message to the specified Telegram chat.
        Parameters:
        - message: str, message to send.
        """
        if not self.telegram_token or not self.telegram_chat_id:
            print("Telegram token or chat ID not provided. Can't send the message.")
            return
        send_message_url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload = {
            "chat_id": self.telegram_chat_id,
            "text": message
        }
        try:
            response = requests.post(send_message_url, data=payload)
            if response.status_code != 200:
                print("Failed to send Telegram message:", response.content)
        except Exception as e:
            print("Error sending Telegram message:", str(e))

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
    
    def cancel_all_orders(self):
        """
        Cancels all open orders for the asset.
        """
        open_orders = self.load.fetch_open_orders(symbol=f'{self.symbol}-PERPETUAL')
        for order in open_orders:
            self.load.cancel_order(order['id'])
        print("All orders cancelled.")

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
        elif current_delta > 0:
            sign = 'sell'
        else:
            print("No need to hedge. Current portfolio delta:", current_delta)
            return

        # retrieve the average price of the perpetual future contract for the asset
        # average of the open, high, low, close prices in last 1min interval.
        avg_price = np.mean(self.load.fetch_ohlcv(
            str(self.symbol)+"-PERPETUAL", limit=10)[-1][1:5])
        
        # if the absolute delta exposure is greater than our threshold then we place a hedging trade
        if abs(current_delta) >= self.threshold:
            asset = str(self.symbol) + "-PERPETUAL"
            order_size = abs(current_delta*avg_price)

            start_time = time.time()  # Store the start time for the chaser feature

            while order_size > 0:
                order_book = self.load.fetch_order_book(asset)
                if sign == 'buy':
                    price = order_book['bids'][0][0] # best bid
                else:
                    price = order_book['asks'][0][0] # best offer
                
                # create the limit order
                print(f"Submitting order size of {order_size} USD at ${price}")
                order = self.load.create_limit_order(asset, sign, order_size, price, {'postOnly': True})
                
                print("Waiting for 5s...")
                time.sleep(5)  # wait for 5 seconds
                
                # check if order was filled
                updated_order = self.load.fetch_order(order['id'])
                remaining = updated_order['remaining']
                
                if remaining == 0:  # fully filled
                    print("Limit order fully filled.")
                    break

                elapsed_time = time.time() - start_time
                if elapsed_time >= 60:  # 1 minute
                    # Cancel the unfilled order and go to market if not filled after 1 minute.
                    self.load.cancel_order(order['id'])
                    self.load.create_market_order(asset, sign, remaining)
                    print("Chaser feature activated. Created market order for remaining qty.")
                    break
                
                # if not fully filled, cancel the order and repeat
                self.load.cancel_order(order['id'])
                order_size = remaining  # adjust the order size based on the unfilled quantity

            self.hedged_once = True
            print("Rebalancing trade to achieve delta-neutral portfolio:", sign, str(order_size / avg_price), str(self.symbol))
        else:
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

            # Exception to cancel all orders in the event of killing program
            except KeyboardInterrupt:
                print("Interrupt detected. Cancelling all orders...")
                self.cancel_all_orders()
                print("Exiting program.")
                exit(0)

            except ccxt.RequestTimeout as e:
                error_message = f"API Request Timeout Error: {str(e)}"
                print(error_message)
                self.send_telegram_message(error_message)
                time.sleep(60)

            except Exception as e:
                error_message = f"Script is broken - trying again in 30 seconds. Current portfolio delta: {self.current_delta()}. Error: {str(e)}"
                print(error_message)
                self.send_telegram_message(error_message)
                time.sleep(30)
                pass
