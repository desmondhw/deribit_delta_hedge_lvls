import delta_hedge
from decouple import config

# replace your `api_id` and `api_secret` in the quotes
id = config("id")
secret = config("secret")

dh = delta_hedge.Hedge(api_id=id, api_secret=secret,
                       symbol="BTC", threshold=0.01, strike=31000, price_change_percent=0.025, num_lvls=10)

# Get current total portfolio delta exposure for the chosen asset
dh.current_delta()

# Run continuous delta-hedging. Terminal log example shown below:
dh.run_loop()

config("chat_id")
