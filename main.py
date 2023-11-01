import hmac
import json
import os
import random
import time
from hashlib import md5

import requests
from requests.adapters import HTTPAdapter

# 引入时间模块
import time

from utils import AES, UTC as pytz, MessagePush

requests.adapters.DEFAULT_RETRIES = 10
pwd = os.path.dirname(os.path.abspath(__file__)) + os.sep

s = requests.session()
s.mount('http://', HTTPAdapter(max_retries=10))
s.mount('https://', HTTPAdapter(max_retries=10))
s.keep_alive = False
# 代理配置
proxies = {
    "http": "http://192.168.1.2:8888",
    "https": "http://192.168.1.2:8888",
}
# 更新你的 headers 中的代理信息，包括添加时间戳
headers ={
    "Timestamp": str(int(time.time() * 1000)),
    "os": "android",
    "phone": "HUAWEI|TAS-AL00|7.1.2",
    "appVersion": "56",
    "Sign": "Sign",
    'accept-encoding': 'gzip',
    "cl_ip": "192.168.1.3",
    "token": "",
    "User-Agent": "okhttp/3.14.9",
    "Content-Type": "application/json;charset=utf-8"
}
# 使用代理配置
s.proxies = proxies
token = None  # 添加一个全局变量来存储 token

def hash_hmac(code, sha_type="sha256"):
    hmac_code = hmac.new('Anything_2023'.encode(), code.encode(), sha_type)
    return hmac_code.hexdigest()

def getMd5(text: str):
    return md5(text.encode('utf-8')).hexdigest()

def parseUserInfo():
    allUser = ''
    if os.path.exists(pwd + "user.json"):
        print('找到配置文件，将从配置文件加载信息！')
        with open(pwd + "user.json", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines:
                allUser = allUser + line + '\n'
    else:
        return json.loads(os.environ.get("USERS", ""))
    return json.loads(allUser)

def save(user, uid, token):
    url = 'http://sxbaapp.zcj.jyt.henan.gov.cn/api/clockindaily20220827.ashx'

    longitude = user["longitude"]
    latitude = user["latitude"]
    if user["randomLocation"]:
        longitude = longitude[0:len(longitude) - 1] + str(random.randint(0, 10))
        latitude = latitude[0:len(latitude) - 1] + str(random.randint(0, 10))

    data = {
        "dtype": 1,
        "uid": uid,
        "address": user["address"],
        "phonetype": user["deviceType"],
        "probability": 2,
        "longitude": longitude,
        "latitude": latitude
    }



    sign = hash_hmac(json.dumps(data) + token)
    headers["Sign"] = sign
    res = requests.post(url, headers=headers, data=json.dumps(data))

    if res.json()["code"] == 1001:
        return True, res.json()["msg"]
    return False, res.json()["msg"]


def getToken():
    url = 'http://sxbaapp.zcj.jyt.henan.gov.cn/api/getApitoken.ashx'

    res = requests.post(url, headers=headers)
    if res.json()["code"] == 1001:
        global token
        token = res.json()["data"]["apitoken"]
        headers["token"] = token  # 设置请求头中的 token
        return True, token
    return False, res.json()["msg"]


def login(user, token):
    password = getMd5(user["password"])
    deviceId = user["deviceId"]

    data = {
        "phone": user["phone"],
        "password": password,
        "dtype": 6,
        "dToken": deviceId
    }

    sign = hash_hmac(json.dumps(data) + token)
    headers["Sign"] = sign
    url = 'http://sxbaapp.zcj.jyt.henan.gov.cn/api/relog.ashx'
    res = requests.post(url, headers=headers, data=json.dumps(data))
    if res.status_code == 200:
        login_response = res.json()
        if login_response["code"] == 1001:
            usertoken = login_response["data"]["Usertoken"]
            headers["token"] = usertoken
    else:
        print("登录请求失败:", res.status_code)

    return login_response

def prepareSign(user):
    global token  # 使用全局的 token 变量
    if not user["enable"]:
        print(user['alias'], '未启用打卡，即将跳过')
        return

    print('已加载用户', user['alias'], '即将开始打卡')

    headers["phone"] = user["deviceType"]

    res, token = getToken()  # 更新全局的 token 变量
    print("token", token)
    if not res:
        print('用户', user['alias'], '获取Token失败')
        MessagePush.pushMessage('职校家园打卡失败！', '职校家园打卡获取Token失败，错误原因：' + token, user["pushKey"])
        return

    loginResp = login(user, token)  # 调用 login 函数

    if loginResp["code"] != 1001:
        print('用户', user['alias'], '登录账号失败, 错误原因：', loginResp["msg"])
        MessagePush.pushMessage('职校家园登录失败！', '职校家园登录失败，错误原因：' + loginResp["msg"], user["pushKey"])
        return

    uid = loginResp["data"]["uid"]
    resp, msg = save(user, uid, token)

    if resp:
        print(user["alias"], '打卡成功！')
        MessagePush.pushMessage('职校家园打卡成功！', '用户：' + user["phone"] + '职校家园打卡成功!', user["pushKey"])
        return
    print(user["alias"], "打卡失败, 原因:" + msg)
    MessagePush.pushMessage('职校家园打卡失败！', '用户：' + user["phone"] + '职校家园打卡失败!原因:' + msg,
                            user["pushKey"])
    if "繁忙" in msg:
        while True:
            print(user["alias"], "打卡失败，原因：" + msg)
            time.sleep(5.5)
            resp, msg = save(user, uid, token)
            if "已打卡" in msg:
                print(user["alias"], "打卡成功")
                break
            elif "系统繁忙" not in msg:
                print(user["alias"], "打卡失败，原因：" + msg)
                MessagePush.pushMessage('职校家园打卡失败！', '用户：' + user["phone"] + '职校家园打卡失败!原因:' + msg,
                                        user["pushKey"])

# 在用户列表外定义一个随机等待的函数
def random_wait(min_minutes, max_minutes):
    wait_time = random.randint(min_minutes * 60, max_minutes * 60)  # 生成5到20分钟之间的随机等待时间（转换为秒）
    print(f"等待 {wait_time / 60} 分钟后开始运行脚本...")
    time.sleep(wait_time)

if __name__ == '__main__':
    # 添加在每次定时任务运行前随机延迟5到20分钟的等待
    random_wait(0, 0)  # 随机等待5到20分钟

    users = parseUserInfo()

    for user in users:
        try:
            prepareSign(user)
            wait_time = random.randint(0, 60)  # 生成0到60秒之间的随机等待时间
            print(f"等待 {wait_time} 秒后继续下一个用户...")
            time.sleep(wait_time)
        except Exception as e:
            print('职校家园打卡失败，错误原因：' + str(e))
            MessagePush.pushMessage('职校家园打卡失败',
                                    '职校家园打卡失败,' +
                                    '具体错误信息：' + str(e)
                                    , user["pushKey"])
