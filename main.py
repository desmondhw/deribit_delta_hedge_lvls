import delta_hedge
from decouple import config

# replace your `api_id` and `api_secret` in the quotes
id = config("id")
secret = config("secret")

# replace your `telegram_token` and `telegram_chat_id` in the quotes
telegram_token = config("telegram_token")
telegram_chat_id = config("telegram_chat_id")

dh = delta_hedge.Hedge(api_id=id, api_secret=secret,
                       symbol="BTC", threshold=0.001, strike=27000, price_change_percent=0.025, hedged_once=False,
                       telegram_token=telegram_token, telegram_chat_id=telegram_chat_id) # Default is False. Set hedged_once to True if algo has already done the first round of hedging. (Usually the case when u pause the algo and need to resume it after first hedge has been done.)

# Get current total portfolio delta exposure for the chosen asset
dh.current_delta()

# Run continuous delta-hedging. Terminal log example shown below:
dh.run_loop()

config("chat_id")
