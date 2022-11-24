import requests
import time
import sys

def authenticate():
    while True:
        URL = 'http://localhost:8000/apikey/'
        response = requests.get(URL)
        if response.status_code != 200:
            time.sleep(10)
            continue

        with open('./api_keys.txt', 'r') as f:
            lines = f.readlines()
            api_key = lines[0].strip()

        if api_key not in response.text:
            print('인증되지 않은 API KEY 입니다')
            sys.exit(0)

        print("API KEY 인증 완료")
        return

