# -*- encoding:utf-8 -*-
import datetime

import requests
import json
import utils
from urllib.parse import urlencode
import leancloud
import time


class leanCloud:
    # 初始化 leanCloud 对象
    def __init__(self, appId, masterKey, class_name):
        leancloud.init(appId, master_key=masterKey)
        self.obj = leancloud.Query(class_name).first()

    # 获取 jwsession
    def getJwsession(self):
        return self.obj.get('jwsession')

    # 设置 jwsession
    def setJwsession(self, value):
        self.obj.set('jwsession', value)
        self.obj.save()

    # 判断之前是否保存过地址信息
    def hasAddress(self):
        if self.obj.get('hasAddress') == False or self.obj.get('hasAddress') is None:
            return False
        else:
            return True

    # 请求地址信息
    def requestAddress(self, location, sign_message):
        # 根据经纬度求具体地址
        url = 'https://apis.map.qq.com/ws/geocoder/v1/'
        location = location.split(',')
        res = utils.geoCode(url, {
            "location": location[1] + "," + location[0]
        })
        _res = res['result']
        # location = location.split(',')
        sign_data = {
            "answers": '["0"]',
            "latitude": location[1],
            "longitude": location[0],
            "country": '中国',
            "city": _res['address_component']['city'],
            "district": _res['address_component']['district'],
            "province": _res['address_component']['province'],
            "township": _res['address_reference']['town']['title'],
            "street": _res['address_component']['street_number'],
            "towncode": _res['address_reference']['town']['id'],
            "citycode": _res['ad_info']['city_code'],
            "areacode": _res['ad_info']['adcode'],
            "timestampHeader": round(time.time())
        }
        return sign_data


class WoZaiXiaoYuanPuncher:
    def __init__(self, item):
        # 我在校园账号数据
        self.data = item['wozaixiaoyaun_data']
        # pushPlus 账号数据
        self.pushPlus_data = item['pushPlus_data']
        # leanCloud 账号数据
        self.leanCloud_data = item['leanCloud_data']
        # mark 晚签用户昵称
        self.mark = item['mark']
        # 初始化 leanCloud 对象
        self.leanCloud_obj = leanCloud(self.leanCloud_data['appId'], self.leanCloud_data['masterKey'],
                                       self.leanCloud_data['class_name'])
        # 学校晚签时段
        self.seqs = []
        # 晚签结果
        self.status_code = 0
        # id 和signid 等self.sign_message
        self.sign_message = ""
        # 请求头
        self.header = {
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36 MicroMessenger/7.0.9.501 NetType/WIFI MiniProgramEnv/Windows WindowsWechat",
            "content-type": "application/json;charset=UTF-8",
            "Content-Length": "2",
            "Host": "gw.wozaixiaoyuan.com",
            "Accept-Language": "en-us,en",
            "Accept": "application/json, text/plain, */*"
        }
        # signdata  要保存的信息
        self.sign_data = ""
        # 请求体（必须有）
        self.body = "{}"

        # 登录

    def login(self):
        # 登录接口
        loginUrl = "https://gw.wozaixiaoyuan.com/basicinfo/mobile/login/username"
        username, password = str(self.data['username']), str(self.data['password'])
        url = f'{loginUrl}?username={username}&password={password}'
        self.session = requests.session()
        # 登录
        response = self.session.post(url=url, data=self.body, headers=self.header)
        res = json.loads(response.text)
        if res["code"] == 0:
            jwsession = response.headers['JWSESSION']
            self.leanCloud_obj.setJwsession(jwsession)
            return True
        else:
            print("登录失败，请检查账号信息" + str(res))
            self.status_code = 5
            return False

    # 判断当前时间段是否可以晚签
    def timeTF(self):
        # 检测当前时间段
        time_now = time.strftime("%H:%M:%S", time.localtime())
        time_list = time_now.split(":")
        if time_list[0] != '22':
            print("不在晚签时间段,请换时间晚签")
            self.status_code = 3
            return True
        else:
            print("在晚签时间段 开始晚签")
            return True

    # 获取晚签列表，符合条件则自动进行晚签
    def PunchIn(self):
        # 先判断 再晚签
        if self.timeTF():
            headers = {
                "jwsession": self.leanCloud_obj.getJwsession()
            }
            post_data = {
                "page": 1,
                "size": 5
            }
            url = "https://student.wozaixiaoyuan.com/sign/getSignMessage.json"
            s = requests.session()
            r = s.post(url, data=post_data, headers=headers)
            res = json.loads(r.text)
            print(res)
            if res['code'] == -10:
                print('jwsession 无效，尝试账号密码晚签')
                self.status_code = 4
                loginStatus = self.login()
                if loginStatus:
                    print("登录成功")
                    self.PunchIn()
                else:
                    print("登录失败")
                    self.sendNotification()
            elif res['code'] == 0:
                self.sign_message = res['data'][0]
                print("开始晚签")
                self.doPunchIn()

    # 晚签
    def doPunchIn(self):
        headers = {
            "jwsession": self.leanCloud_obj.getJwsession()
        }
        post_data = self.leanCloud_obj.requestAddress(self.data['location'], self.sign_message)

        url = "https://student.wozaixiaoyuan.com/sign/doSign.json"
        s = requests.session()
        self.sign_data = post_data
        r = s.post(url, data=json.dumps(post_data), headers=headers)
        r_json = json.loads(r.text)
        if r_json['code'] == 0:
            self.status_code = 1
            print("签到提醒", "签到成功")
            if self.pushPlus_data['onlyWrongNotify'] == "false":
                self.sendNotification()
        else:
            self.status_code = 5
            print("签到提醒", "签到失败,返回信息为:" + str(r_json))
            self.sendNotification()

    # 获取晚签结果
    def getResult(self):
        res = self.status_code
        if res == 1:
            return "✅ 晚签成功"
        elif res == 2:
            return "✅ 你已经晚签了，无需重复晚签"
        elif res == 3:
            return "❌ 晚签失败，当前不在晚签时间段内"
        elif res == 4:
            return "❌ 晚签失败，jwsession 无效"
        elif res == 5:
            return "❌ 晚签失败，登录错误，请检查账号信息"
        else:
            return "❌ 晚签失败，发生未知错误"

    # 推送晚签结果
    def sendNotification(self):
        notifyResult = self.getResult()
        # pushplus 推送
        url = 'http://www.pushplus.plus/send'
        notifyToken = self.pushPlus_data['notifyToken']
        content = json.dumps({
            "晚签用户": self.mark,
            "晚签项目": "晚签",
            "晚签情况": notifyResult,
            "晚签信息": self.sign_data,
            "晚签时间": (datetime.datetime.now() + datetime.timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S'),
        }, ensure_ascii=False)
        msg = {
            "token": notifyToken,
            "title": "⏰ 我在校园晚签结果通知",
            "content": content,
            "template": "json"
        }
        body = json.dumps(msg).encode(encoding='utf-8')
        headers = {'Content-Type': 'application/json'}
        r = requests.post(url, data=body, headers=headers).json()
        if r["code"] == 200:
            print("消息经 pushplus 推送成功")
        else:
            print("pushplus: " + r)
            print("消息经 pushplus 推送失败，请检查错误信息")
def startdk():
    # 读取配置文件
    configs = utils.processJson("config.json").read()
    # 遍历每个用户的账户数据，进行晚签
    for config in configs:
        wzxy = WoZaiXiaoYuanPuncher(config)
        # 如果没有 jwsession，则 登录 + 晚签
        jwsession = wzxy.leanCloud_obj.getJwsession()
        if jwsession == "" or jwsession is None:
            print("使用账号密码登录")
            loginStatus = wzxy.login()
            if loginStatus:
                print("登录成功,开始晚签")
                wzxy.PunchIn()
            else:
                print("登录失败")
        else:
            print("检测到jwsession存在，使用jwsession晚签")
            wzxy.PunchIn()

if __name__ == '__main__':
    startdk()
def handler(event, context):
    startdk()
def main_handler(event, context):
    startdk()