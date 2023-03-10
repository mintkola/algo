"""The other indicators combined with NATR (trade in High Volatility) strategy/algorithm."""

# Author: Dylan Vassallo <dylan.vassallo.18@um.edu.mt>

###### importing dependencies #############################################
import numpy as np
import lucrum.algo.pyta as ta 
import matplotlib.pyplot as plt
import lucrum.dataconst as dcons
import lucrum.algo.finstats as fs
from .controller import _Controller

###### RSI NATR strategy class #############################################
# NOTE: This was not used in the experiment 
class RsiNatrAlgo(_Controller):
    """A simple algo trading strategy which uses RSI overbought/oversold as signals.
       This is different from the SimpleRsiAlgo as it uses a measure of volatility (NATR).  
    """

    def gen_features(self, data, natr_window, rsi_window, price=dcons.CLOSE):
        """Generates features for NATR RSI.

        Parameters 
        ----------
        data: pandas dataframe 
            Holds data/prices for a specific asset, expected to have OHLC.
        natr_window: integer
            The time window used for the NATR.
        rsi_window: integer
            The time window used for the RSI.
        price: str, optional(defaulf='close')
            The column name used to apply the lead and lag moving average on. 
            By default this will be applied to the closing price ('close') 
            but this can be applied to any column with numeric values.  
        """

        # set config for ta-lib
        ta_config = {
            "natr":[("natr", {"timeperiod":natr_window})], 
            "rsi":[("rsi", {"timeperiod":rsi_window, "price":price})]
        }

        # apply NATR and RSI to dataframe
        ta.apply_ta(data, ta_config)

    def gen_positions(self, data, volatility, upper, lower):
        """Generates postions based on the RSI overbough/oversold and volatility.
           This generates both short and long positions. 

        Parameters 
        ----------
        data: pandas dataframe 
            Holds data/prices/features for a specific asset.
        volatility: float
            The threshold used by NATR to give a signal.
        upper: int
            The upper bound which indicates an overbought (> 1 and < 100).
        lower: int
            The lower bound which indicates an oversold (> 1 and < 100) must be smaller than upper.
        """

        # generates signals 
        # long signal (oversold so go long) and (volatility > threshold)
        data["long_signal"] = ((data["rsi"] < lower) & (data["natr"] > volatility))   
        # short signal (overbought so short) and (volatility > threshold)
        data["short_signal"] = ((data["rsi"] > upper) & (data["natr"] > volatility)) 

        # generate positions 
        data["long_position"] = 0  # initially set to 0 
        data["short_position"] = 0 # initially set to 0
        data.loc[data.long_signal, "long_position"] = 1    # set position to go long
        data.loc[data.short_signal, "short_position"] = -1 # set position to short 

        # set position at time t 
        data["position"] = data.long_position + data.short_position

        # basically we check for any changes between positions 
        # except when we are not in a trade at all (position is equal to 0)
        data["apply_fee"] = 0
        data["apply_fee"] = ((data.position != data.position.shift(-1)) | (data.position != data.position.shift(1))).astype(int)
        data.loc[data.position == 0, "apply_fee"] = 0  
        
        # if a you take a position and you close it immediately apply 
        # the fee *2 which means you entered and exit at the same candle 
        # eg. 0 1 0 or -1 1 -1 or 1 -1 1
        data.loc[(data.position != 0) & (data.position.shift(1) != data.position ) & (data.position.shift(-1) != data.position) , "apply_fee"] = 2 

    def evaluate(self, data, trading_fee):
        """Evaluates/calculates performance from the positions generated.  

        Parameters 
        ----------
        data: pandas dataframe 
            Holds positions generated when apply the gen_positions function.
        trading_fee: float
            The trading fee applied which each trade. 
        """

        # firstly calculate log returns
        data["logprices"] = np.log(data[dcons.CLOSE])
        data["log_returns"] = data.logprices - data.logprices.shift(1)
                
        # calculate profit and loss + tx cost 
        data["pl"] = (data["position"].shift(1) * data["log_returns"]) - ((data.apply_fee.shift(1) * trading_fee) * np.abs(data["log_returns"]))

        # cumulative profit and loss 
        data["cum_pl"] = data["pl"].cumsum()

    def plot_pos(self, data):
        
        # figure size
        fig = plt.figure(figsize=(15,9))
        
        # closing price plot 
        ax = fig.add_subplot(3,1,1)
        ax.plot(data["close"], label="Close Price")
        ax.set_ylabel("USDT")
        ax.legend(loc="best")
        ax.grid()

        # RSI plot 
        ax = fig.add_subplot(3,1,2)
        ax.plot(data["rsi"], label="RSI")
        ax.set_ylabel("RSI")
        ax.set_ylim([0, 100])
        ax.grid()

        # positions plot 
        ax = fig.add_subplot(3,1,3)
        ax.plot(data["position"], label="Trading position")
        ax.set_ylabel("Trading Position")
        ax.set_ylim([-1.5, 1.5])

        # show plot 
        plt.show()

    def plot_perf(self, data):

        # equity curve plot
        data["cum_pl"].plot(label="Equity Curve", figsize=(15,8))
        plt.xlabel("Date")
        plt.ylabel("Cumulative Returns")
        plt.legend()
        plt.show()

    def stats_perf(self, data):
        
        # print date from and to 
        days_difference = data.tail(1)["close_time"].values[0] - data.head(1)["open_time"].values[0]
        days_difference = int(round(days_difference / np.timedelta64(1, 'D')))

        time_from = data.head(1)["open_time"].astype(str).values[0]
        time_to = data.tail(1)["close_time"].astype(str).values[0]
        print("From {} to {} ({} days)\n".format(time_from, time_to, days_difference))
        
        # we can sum up every time a fee was applied to get total trades 
        total_trades = data.apply_fee.sum()
        print("Total number of trades: {}".format(total_trades))

        # print avg. trades per date
        print("Avg. trades per day: {}".format(round(total_trades / days_difference, 2)))

        # print profit/loss (log returns)
        cum_return = round(data["cum_pl"].iloc[-1] * 100, 2)
        print("Profit/Loss [Log Return]: {0}%".format(cum_return))  

        # # print profit/loss (simple return)
        # simple_return = (np.exp(data.iloc[-1].cum_pl) - 1) * 100
        # print("Profit/Loss [Simple Return]: {0}%".format(round(simple_return, 2)))  

        # print maximum gains (log returns)
        max_cum_pl = round(data["cum_pl"].max() * 100, 2)
        print("Maximum Gain: {0}%".format(max_cum_pl))

        #print maximum loss (log returns) 
        min_cum_pl = round(data["cum_pl"].min() * 100, 2)
        print("Maximum Drawdown: {0}%".format(min_cum_pl))

        # print sharpe ratio 
        # 96 (15 minutes in a day) and 365 days for the crypto market 
        # we compute the sharpe ratio based on profit and loss 
        sharpe_ratio = fs.sharpe_ratio(96*365, data.pl)
        print("Annualised Sharpe Ratio: {0}".format(round(sharpe_ratio, 6)))
