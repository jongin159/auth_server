import ccxt
import pandas as pd
import numpy as np
import datetime
from PyQt5.QtTest import *

class Binance():
    def __init__(self, api_key, sec_key):
        # binance 객체 생성
        self.binance = ccxt.binance(config={
            'apiKey': api_key,
            'secret': sec_key,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future'
            }
        })

    """ 캔들 정보 반환 """
    def get_ohlcv(self, coin, timeframe):
        QTest.qWait(10)
        ticker = coin + "USDT"
        ohlcv = self.binance.fetch_ohlcv(ticker, timeframe=timeframe)
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

            for i in range(-52, -2):
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
                print('{} 숏 시그널, 이전 50 최고가 : {}, 신고가 : {}, 이전 50 최고가 캔들 RSI : {}, 신고가 RSI : {}'.format(coin, high50, high0, high50_rsi, rsi0))
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
    def limit_order(self, coin, side, vol, price, leverage, reduceOnly=False, stop_price=0):
        QTest.qWait(200)

        if not reduceOnly:
            self.set_leverage(coin, leverage)

        # 심볼, 수량, 가격, 파라미터
        coin += "USDT"
        order = None

        vol = abs(vol)

        if side == "long":
            if stop_price == 0:
                order = self.binance.create_limit_buy_order(coin, vol, price,
                                                         params={'reduceOnly': reduceOnly})
            else:
                order = self.binance.create_limit_buy_order(coin, vol, None,
                                                            params={'reduceOnly': reduceOnly,
                                                                    'stopPrice':stop_price})
        elif side == "short":
            if stop_price == 0:
                order = self.binance.create_limit_sell_order(coin, vol, price,
                                                             params={'reduceOnly': reduceOnly})
            else:
                order = self.binance.create_limit_sell_order(coin, vol, None,
                                                             params={'reduceOnly': reduceOnly,
                                                                     'stopPrice':stop_price})
        return order

    """ 레버리지 설정 """
    def set_leverage(self, coin, leverage):
        coin += 'USDT'
        QTest.qWait(200)
        markets = self.binance.load_markets()
        market = self.binance.market(coin)
        resp = self.binance.fapiPrivate_post_leverage({
            'symbol': market['id'],
            'leverage': leverage
        })

    """ 포지션 정보 """
    """ 롱일 경우, 양수 / 숏일 경우, 음수 """
    def get_position(self, coin):
        coin += "USDT"

        QTest.qWait(200)
        balance = self.binance.fetch_balance()
        positions = balance['info']['positions']

        for position in positions:
            if position["symbol"] == coin:
                return float(position['positionAmt'])
        return None

    """ 주문 취소 """
    def cancel_order(self, coin):
        QTest.qWait(200)
        coin += "USDT"
        res = self.binance.cancel_all_orders(coin)
        return res

    def set_stop_loss(self, coin, stoploss):
        vol = self.get_position(coin)
        QTest.qWait(200)
        coin += "USDT"
        if vol > 0:
            res = self.binance.create_order(coin, 'market', 'sell', vol, None, {'reduceOnly':True, 'stopPrice': stoploss})
        else:
            vol = abs(vol)
            res = self.binance.create_order(coin, 'market', 'buy', vol, None, {'reduceOnly':True, 'stopPrice': stoploss})
        return res

    # 특정 코인의 포지션 청산
    def finish_position(self, coin, position):
        try:
            # 코인의 현재 진입 포지션 수량을 받아옴
            positionAmt = self.get_position(coin)
            if positionAmt < 0:
                positionAmt = positionAmt * -1

            coin += "USDT"

            # 포지션 수량만큼 매도 주문
            if positionAmt > 0:
                if position == "long":
                    order = self.binance.create_market_sell_order(
                        symbol=coin,
                        amount=positionAmt,
                        params={'reduceOnly': True}
                    )
                else:
                    order = self.binance.create_market_buy_order(
                        symbol=coin,
                        amount=positionAmt,
                        params={'reduceOnly': True}
                    )
                QTest.qWait(200)
                return order
            QTest.qWait(200)
            return True
        except Exception as e:
            print(e)
            QTest.qWait(200)
            return None

    """ 매수/매도 호가 """
    """ 시장가로 매수 가능한 가격, 시장가로 매도 가능한 가격 """
    def get_bid_ask_price(self, coin):
        try:
            coin += "USDT"

            QTest.qWait(10)
            orderbook = self.binance.fetch_order_book(coin)
            return orderbook['asks'][0][0], orderbook['bids'][0][0]
        except Exception as e:
            print(e)
            return None

    def fetch_order(self, coin, id):
        try:
            QTest.qWait(200)
            coin += "USDT"
            res = self.binance.fetch_order(id, coin)
            return res
        except Exception as e:
            print(e)
            return None

    def fetch_open_orders(self, coin):
        try:
            QTest.qWait(200)
            coin += "USDT"
            res = self.binance.fetch_open_orders(coin)
            return res
        except:
            return None
