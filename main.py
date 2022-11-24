import bitget
import datetime
import auth

auth.authenticate()

class Trader():
    def __init__(self):
        with open('./api_keys.txt', 'r') as f:
            lines = f.readlines()
            api_key = lines[0].strip()
            sec_key = lines[1].strip()
            password = lines[2].strip()

        self.bitget = bitget.Bitget(api_key, sec_key, password)
        self.coin_info = []

        """
        self.coin_info[0][0] => 첫 번째 코인 이름
        self.coin_info[0][1] => 첫 번째 코인 진입 USDT
        self.coin_info[0][2] => 첫 번째 코인 레버리지
        self.coin_info[0][3] => 첫 번째 코인 포지션 수량
        self.coin_info[0][4] => 첫 번째 코인 시장가로 매수 가능한 가격
        self.coin_info[0][5] => 첫 번째 코인 시장가로 매도 가능한 가격
        self.coin_info[0][6] => 첫 번째 코인 손절가
        self.coin_info[0][7] => 첫 번째 코인 지정가 주문 낸 시간
        self.coin_info[0][8] => 첫 번째 코인 진입가격
        self.coin_info[0][9] => 첫 번째 코인 1차 익절가격
        self.coin_info[0][10] => 첫 번째 코인 2차 익절가격
        self.coin_info[0][11] => 첫 번째 코인 마진모드(교차, 격리)
        self.coin_info[0][12] => 첫 번째 코인 주문 ID
        """
        with open('./coin_info.txt', 'r') as f:
            lines = f.readlines()

            for line in lines:
                info = line.strip().split(',')
                coin = info[0]
                enter_usdt = float(info[1])
                leverage = int(info[2])
                margin_mode = info[3]
                order_ids = []

                self.coin_info.append([coin, enter_usdt, leverage, 0, 0, 0, 0, 0, 0, 0, 0, margin_mode, order_ids])

        print(self.coin_info)

    def refresh_cur_data(self):
        for i in range(len(self.coin_info)):
            try:
                """ 포지션 수량 갱신 """
                vol = self.bitget.get_position(self.coin_info[i][0])
                self.coin_info[i][3] = vol

                """ 매수/매도 호가 갱신 """
                price = self.bitget.get_bid_ask_price(self.coin_info[i][0])
                self.coin_info[i][4] = price[0]
                self.coin_info[i][5] = price[1]

                """ 포지션이 없으면 손절가 0으로 세팅 """
                if vol == 0:
                    self.coin_info[i][6] = 0
            except Exception as e:
                print(e)

    def enter_position(self):
        for i in range(len(self.coin_info)):
            try:
                signal = self.bitget.get_signal(self.coin_info[i][0], timeframe='4h')

                """ 시그널이 뜨면 포지션 진입 """
                if not signal:
                    continue

                """ 포지션이 없을 경우에만 진입 """
                if self.coin_info[i][3] != 0:
                    continue

                """ 대기중인 주문이 없을 경우에만 limit order 주문냄 """
                waiting_orders = self.bitget.fetch_open_orders(self.coin_info[i][0])
                if len(waiting_orders) > 0:
                    continue

                """ 위 조건들을 다 만족할 경우, 지정가 주문 """
                self.bitget.cancel_order(self.coin_info[i][0], self.coin_info[i][12])
                self.coin_info[i][12] = []
                vol = self.coin_info[i][1] / signal[1]
                res = self.bitget.limit_order(coin=self.coin_info[i][0],
                                         side=signal[0],
                                         vol=vol,
                                         price=signal[1],
                                         leverage=self.coin_info[i][2],
                                         mode=self.coin_info[i][11])
                self.coin_info[i][12].append(res)

                """ 
                정상적으로 주문 접수가 되었다면, 접수한 시간을 저장
                1분 안에 체결되는지 확인하기 위함 
                """
                if res:
                    self.coin_info[i][7] = datetime.datetime.now()
                    """ 진입 가격 설정 """
                    self.coin_info[i][8] = signal[1]
                    """ 1차, 2차 익절 가격 설정 """
                    self.coin_info[i][9] = self.coin_info[i][8] + (self.coin_info[i][8] - signal[2])
                    self.coin_info[i][10] = self.coin_info[i][8] + 2 * (self.coin_info[i][8] - signal[2])
            except Exception as e:
                print(e)

    def check_open_orders(self):
        for i in range(len(self.coin_info)):
            try:
                """ 체결되었는지 확인할 것이 없으면 continue """
                if self.coin_info[i][7] == 0:
                    continue

                """ 주문 접수한지 몇 초 지났는지 """
                cur_time = datetime.datetime.now()
                time_delta = (cur_time - self.coin_info[i][7]).seconds

                """ 포지션이 있는 경우 """
                if self.coin_info[i][3] != 0:
                    """ 주문취소 """
                    self.bitget.cancel_order(self.coin_info[i][0], self.coin_info[i][12])
                    self.coin_info[i][12] = []

                    """ 익절 주문 걸기"""

                    side = "buy"
                    """ 익절가 > 진입가면 롱클로즈(short) """
                    if self.coin_info[i][9] > self.coin_info[i][8]:
                        side = "sell"

                    """ 손절가 설정 """
                    self.coin_info[i][6] = self.coin_info[i][8] + (self.coin_info[i][8] - self.coin_info[i][9])
                    self.bitget.set_stop_loss(coin=self.coin_info[i][0], stoploss=self.coin_info[i][6])

                    print(self.coin_info[i][0], self.coin_info[i][3], side)
                    """ 1차 익절 주문 """
                    res = self.bitget.limit_order(coin=self.coin_info[i][0],
                                             side=side,
                                             vol=self.coin_info[i][3] * 0.75,
                                             price=self.coin_info[i][9],
                                             leverage=self.coin_info[i][2],
                                             mode=self.coin_info[i][11],
                                             reduceOnly=True)
                    self.coin_info[i][12].append(res)

                    """ 2차 익절 주문 """
                    res = self.bitget.limit_order(coin=self.coin_info[i][0],
                                             side=side,
                                             vol=self.coin_info[i][3] * 0.75,
                                             price=self.coin_info[i][10],
                                             leverage=self.coin_info[i][2],
                                             mode=self.coin_info[i][11],
                                             reduceOnly=True)
                    self.coin_info[i][12].append(res)

                    """ 주문접수시간 초기화 """
                    self.coin_info[i][7] = 0
                elif time_delta >= 60:
                    """ 60초가 지났으면 주문 취소 """
                    self.bitget.cancel_order(self.coin_info[i][0], self.coin_info[i][12])
                    self.coin_info[i][12] = []
                    """ 주문접수시간 초기화 """
                    self.coin_info[i][7] = 0
            except Exception as e:
                print(e)

if __name__ == "__main__":
    trader = Trader()
    cnt = 0

    while True:
        try:
            trader.refresh_cur_data()
            trader.check_open_orders()
            trader.enter_position()

            cnt += 1
            if cnt > 10:
                cnt = 0
                print(trader.coin_info)
        except Exception as e:
            print(e)
