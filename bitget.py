import ccxt
import pandas as pd
import numpy as np
import datetime
from PyQt5.QtTest import *

class Bitget():
    def __init__(self, api_key, sec_key, password):
        # bitget 객체 생성
        self.bitget = ccxt.bitget(config={
            'apiKey': api_key,
            'secret': sec_key,
            'password': password,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap'
            }
        })

    """ 캔들 정보 반환 """
    def get_ohlcv(self, coin, timeframe):
        QTest.qWait(10)
        ticker = coin + "USDT_UMCBL"
        ohlcv = self.bitget.fetch_ohlcv(ticker, timeframe=timeframe)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'vol'])
        return df

    """ df에 RSI 정보 추가 """
    def rsi(self, df):
        df['변화량'] = df['close'] - df['close'].shift(1)
        df['상승폭'] = np.where(df['변화량'] >= 0, df['변화량'], 0)
        df['하락폭'] = np.where(df['변화량'] < 0, df['변화량'].abs(), 0)

        df['AU'] = df['상승폭'].ewm(alpha=1 / 14, min_periods=14).mean()
        df['AD'] = df['하락폭'].ewm(alpha=1 / 14, min_periods=14).mean()

        df['RSI'] = df['AU'] / (df['AU'] + df['AD']) * 100

        return df

    """ 시그널 판단 """

    def get_signal(self, coin, timeframe):
        df = self.get_ohlcv(coin, timeframe)
        df = self.rsi(df)
        """ 마지막캔들 타임스탬프 """
        last_candle_timestamp = int(df.iloc[-1]['timestamp'] / 1000)
        """ 현재시간 타임스탬프 """
        cur_timestamp = int(datetime.datetime.now().timestamp())

        """ 정각 """
        if last_candle_timestamp <= cur_timestamp <= last_candle_timestamp + 10:
            high50 = 0
            low50 = 1234567890
            high50_rsi = 0
            low50_rsi = 0

            for i in range(-82, -2):
                high = df.iloc[i]['high']
                low = df.iloc[i]['low']
                rsi = df.iloc[i]['RSI']

                if high > high50:
                    high50 = high
                    high50_rsi = rsi

                if low < low50:
                    low50 = low
                    low50_rsi = rsi

            low0 = df.iloc[-2]['low']
            high0 = df.iloc[-2]['high']
            rsi0 = df.iloc[-2]['RSI']
            close0 = df.iloc[-2]['close']

            """ 시그널 """
            if high0 > high50 and rsi0 < high50_rsi:
                print('{} 숏 시그널, 이전 50 최고가 : {}, 신고가 : {}, 이전 50 최고가 캔들 RSI : {}, 신고가 RSI : {}'.format(coin, high50,
                                                                                                       high0,
                                                                                                       high50_rsi,
                                                                                                       rsi0))
                return "short", close0, high0
            elif low0 < low50 and rsi0 > low50_rsi:
                print('{} 롱 시그널, 이전 50 최저가 : {}, 신저가 : {}, 이전 50 최저가 캔들 RSI : {}, 신저가 RSI : {}'.format(coin, low50,
                                                                                                       low0,
                                                                                                       low50_rsi,
                                                                                                       rsi0))
                # print('{} 롱 시그널'.format(coin))
                return "long", close0, low0

        return None

    """ 지정가 주문 """
    def limit_order(self, coin, side, vol, price, leverage, mode, reduceOnly=False):
        QTest.qWait(200)

        if side == 'long':
            side = 'buy'
        elif side == 'short':
            side = 'sell'

        if not reduceOnly:
            self.set_leverage(coin, leverage, mode)

        # 심볼, 수량, 가격, 파라미터
        coin += "USDT_UMCBL"
        order = None

        vol = abs(vol)
        order = self.bitget.create_limit_order(symbol=coin, side=side, amount=vol, price=price,
                                               params={'reduceOnly': reduceOnly})

        return order['id']

    """ 레버리지 설정 """
    def set_leverage(self, coin, leverage, mode):
        coin += 'USDT_UMCBL'
        mode = mode.lower()
        if mode == "cross":
            mode = "crossed"
        elif mode == "isolated":
            mode = 'fixed'

        self.set_margin_mode(coin, mode)
        QTest.qWait(200)
        if mode == 'crossed':
            self.bitget.set_leverage(leverage=leverage, symbol=coin, params={"marginCoin":"USDT"})
        else:
            self.bitget.set_leverage(leverage=leverage, symbol=coin, params={"marginCoin": "USDT", "holdSide":"long"})
            self.bitget.set_leverage(leverage=leverage, symbol=coin, params={"marginCoin": "USDT", "holdSide": "short"})

    """ 마진 모드 설정 (교차, 격리) """
    def set_margin_mode(self, coin, mode):
        QTest.qWait(200)
        self.bitget.set_margin_mode(marginMode=mode, symbol=coin)

    """ 포지션 정보 """
    """ 롱일 경우, 양수 / 숏일 경우, 음수 """
    def get_position(self, coin):
        QTest.qWait(200)
        positions = self.bitget.fetch_positions()
        for position in positions:
            symbol = position['info']['symbol'].replace('_UMCBL', "")
            side = position['info']['holdSide']
            vol = float(position['info']['total'])

            if symbol == "{}USDT".format(coin):
                if side == "long" and vol > 0:
                    return vol
                elif side == "short" and vol > 0:
                    return -vol

        return 0

    """ 주문 취소 """
    def cancel_order(self, coin, ids):
        QTest.qWait(200)
        coin += 'USDT_UMCBL'
        for id in ids:
            res = self.bitget.cancel_order(id, coin, params={"marginCoin": "USDT"})
        return

    """ 손절 트리거 주문 """
    def set_stop_loss(self, coin, stoploss):
        vol = self.get_position(coin)
        QTest.qWait(200)
        coin += 'USDT_UMCBL'
        if vol > 0:
            res = self.bitget.create_market_order(symbol=coin, side='buy', amount=vol,
                                                    params={"reduceOnly": True, "stopLossPrice":stoploss})
        else:
            vol = abs(vol)
            res = self.bitget.create_market_order(symbol=coin, side='sell', amount=vol,
                                                  params={"reduceOnly": True, "stopLossPrice": stoploss})
        return res

    """ 시장가 주문 """
    def market_order(self, coin, side, vol, leverage, marginMode, reduceOnly=False):
        side = side.lower()
        if side == 'long':
            side = 'buy'
        elif side == 'short':
            side = 'sell'

        if not reduceOnly:
            self.set_leverage(coin, leverage, marginMode)

        coin += 'USDT_UMCBL'
        order = self.bitget.create_market_order(symbol=coin, side=side, amount=vol, params={"reduceOnly":reduceOnly})
        
        return order

    """ 매수/매도 호가 """
    """ 시장가로 매수 가능한 가격, 시장가로 매도 가능한 가격 """
    def get_bid_ask_price(self, coin):
        coin += 'USDT_UMCBL'
        res = self.bitget.fetch_order_book(symbol=coin)
        return res['asks'][0][0], res['bids'][0][0],

    def fetch_open_orders(self, coin):
        try:
            QTest.qWait(200)
            coin += 'USDT_UMCBL'
            res = self.bitget.fetch_open_orders(coin)
            return res
        except:
            return None

# api_key = 'bg_880d78d307c79b5a09d20d06cf52d32b'
# sec_key = '96babee3895c24bdd35e4a126d1a146efce9cc184e312e8c25c5127d53672113'
# password = 'sa9260745'
# bitget = Bitget(api_key, sec_key, password)
# res = bitget.fetch_open_orders('ETH')
# print(len(res), res)
# print(bitget.set_stop_loss('BTC', 15800))
# bitget.cancel_order(coin='BTC', id='978921185108180993')

# res = bitget.limit_order('ADA', 'long', 94, 0.3, 10, 'cross', reduceOnly=True)
# print(res)
# print(res)
# print(bitget.cancel_order('ETH'))
# print(bitget.get_position('BTC'))
# bitget.finish_position('XRP')
# while True:
#     print(bitget.get_market_price('BTC'))
# print(20/16598)
# res = bitget.market_order('BTC', 'short', 20/16598, 10, 'cross', reduceOnly=False)
# print(res)
# res = bitget.market_order('BTC', 'buy', 0.001, 10, 'cross', reduceOnly=False)
# print(res)
# while True:
#     bitget.macd_signal('BTC', '1m', 12, 26, 9)
# bitget.set_margin_mode('BTC', 'fixed')
# bitget.set_leverage('BTC', 5, 'isolated')
# res = bitget.get_ohlcv('BTC', '1d')
# print(res)
# bitget.set_leverage('BTC', 20)
# markets = bitget.bitget.load_markets()
# print(markets)
# coin, side, vol, price, leverage, reduceOnly=False, stop_price=0):
# res = bitget.limit_order('BTC', 'buy', 0.001, 16000, 10, reduceOnly=True)
# print(res)