# Deribit Straddle Hedger

## Description

This project is a Python-based script that will check a user's portfolio delta on Deribit Exchange every hour, and attempt to automatically rebalance in the case a delta threshold level is breached. It will hedge at every +/-2.5% price interval from the Straddle's strike.
The portfolio is delta-hedged using the chosen asset’s perpetual futures contract on Deribit.

## Function parameters

- `id` (string): The ID can be found under API management under account settings on the Deribit website.
- `secret` (string): The secret can be found under API management under account settings on the Deribit website.
- `symbol` (string): The asset you wish to delta-hedge. Currently only "BTC" and "ETH" are supported with the default value set to "BTC".
- `threshold` (float): The maximum absolute value of delta exposure to have at any given time. The default value is currently 0.01 which means the portfolio delta will fluctuate between -0.01 to 0.01 of whichever asset you are trading. Any breach beyond this level will result in the portfolio being delta-hedged.
- `strike` (float): The strike price of your straddle position.
- `price_change_percent` (float): The % price change interval which you want to define for hedging. 0.025 means that the bot will hedge your portfolio delta at every +/-2.5% price interval.
- `num_levels` (float): The number of price intervals you'd like the bot to hedge. If your strike is 30,000 and num_levels is 5, the prices that the bot will do delta hedging are:
  30,750, 31,500, 322,500, 33,000 and 33,750 and
  29,250, 28,500, 27,750, 27,000 and 26,250.

### Installation

1. Clone the repo
   ```
   git clone https://github.com/desmondhw/deribit_delta_hedge_lvls.git
   ```
2. Go to the project directory
   ```
   cd project
   ```
3. Install the required dependencies
   ```
   pip install -r requirements.txt
   ```