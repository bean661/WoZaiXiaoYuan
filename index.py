# -*- encoding:utf-8 -*-
import datetime
import random
import time
import requests
import json
import utils
from urllib.parse import urlencode
import leancloud


class leanCloud:
    # 初始化 leanCloud 对象
    def __init__(self,appId,masterKey,class_name):
        leancloud.init(appId,master_key = masterKey)
        self.obj = leancloud.Query(class_name).first()
    # 获取 jwsession        
    def getJwsession(self):
        return self.obj.get('jwsession')
    # 设置 jwsession        
    def setJwsession(self,value):
        self.obj.set('jwsession',value)
        self.obj.save()
    # 判断之前是否保存过地址信息
    def hasAddress(self):
        if self.obj.get('hasAddress') == False or self.obj.get('hasAddress') is None:
            return False
        else:
            return True
    # 请求地址信息
    def requestAddress(self,location):
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
        # mark 打卡用户昵称
        self.mark = item['mark']
        # 初始化 leanCloud 对象
        self.leanCloud_obj = leanCloud(self.leanCloud_data['appId'],self.leanCloud_data['masterKey'],self.leanCloud_data['class_name'])
        # 学校打卡时段
        self.seqs = []
        # 打卡结果
        self.status_code = 0
        # 请求头
        self.header = {
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36 MicroMessenger/7.0.9.501 NetType/WIFI MiniProgramEnv/Windows WindowsWechat",
            "content-type": "application/json;charset=UTF-8",
            "Content-Length": "360",
            "Host": "gw.wozaixiaoyuan.com",
            "Accept-Language": "en-us,en",
            "Accept": "application/json, text/plain, */*"
        }
        # signdata  要保存的信息
        self.sign_data =""
        # 请求体（必须有）
        self.body = "{}"       
        

    # 登录
    def login(self):
        # 登录接口
        loginUrl = "https://gw.wozaixiaoyuan.com/basicinfo/mobile/login/username"
        username,password = str(self.data['username']),str(self.data['password'])
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
            print("登录失败，请检查账号信息"+str(res))
            self.status_code = 5
            return False
    # 获取打卡列表，判断当前打卡时间段与打卡情况，符合条件则自动进行打卡
    def PunchIn(self):
        print("查询是否打卡")
        url = "https://student.wozaixiaoyuan.com/heat/getTodayHeatList.json"
        self.header['Host'] = "student.wozaixiaoyuan.com"
        self.header['JWSESSION'] = self.leanCloud_obj.getJwsession()
        self.session = requests.session()
        response = self.session.post(url=url, data=self.body, headers=self.header)
        res = json.loads(response.text)
        # 如果 jwsession 无效，则重新 登录 + 打卡
        if res['code'] == -10:
            print('jwsession 无效，将尝试使用账号信息重新登录')
            self.status_code = 4
            loginStatus = self.login()
            if loginStatus:
                self.PunchIn()
            else:
                print(res)
                print("重新登录失败，请检查账号信息")
                self.sendNotification()
        elif res['code'] == 0:
            self.doPunchIn(str(self.get_seq()))

    #打卡
    def doPunchIn(self, seq):
        print(datetime.datetime.now())
        print("正在进行：" + str(self.get_seq()) + "...")
        headers = {
            "Host": "student.wozaixiaoyuan.com",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36 MicroMessenger/7.0.9.501 NetType/WIFI MiniProgramEnv/Windows WindowsWechat",  # 修改5：User-Agent
            "Referer": "https://servicewechat.com/wxce6d08f781975d91/183/page-frame.html",  # 修改：Referer
            "Content-Length": "360",
            "JWSESSION": "",
        }
        headers["JWSESSION"] = self.leanCloud_obj.getJwsession()
        url = "https://student.wozaixiaoyuan.com/heat/save.json"
        sign_data = self.leanCloud_obj.requestAddress(self.data['location'])
        sign_data['seq'] = str(seq)
        sign_data['temperature'] = self.get_random_temprature()
        self.sign_data = sign_data
        # 如果存在全局变量WZXY_ANSWERS，处理传入的Answer
        # data = urlencode(sign_data)
        response = requests.post(url, headers=headers,data=sign_data,).json()
        # response = json.loads(response.text)
        # 打卡情况
        if response["code"] == 0:
            self.status_code = 1
            print("打卡成功")
            if self.pushPlus_data['onlyWrongNotify'] == "false":
                self.sendNotification()
        else:
            print(response)
            print("打卡失败")
            self.sendNotification()
    # 获取打卡时段
    # seq的1,2,3代表早，中，晚
    def get_seq(self):
        current_hour = datetime.datetime.now()
        current_hour = current_hour.hour + 8
        if 6 <= current_hour <= 9:
            return "1"
        elif 12 <= current_hour < 18:
            return "2"
        elif 19 <= current_hour < 22:
            return "3"
        else:
            return 1

    # 获取随机体温
    def get_random_temprature(self):
        random.seed(time.ctime())
        return "{:.1f}".format(random.uniform(36.2, 36.7))
    # 获取打卡结果
    def getResult(self):
        res = self.status_code
        if res == 1:
            return "✅ 打卡成功"
        elif res == 2:
            return "✅ 你已经打过卡了，无需重复打卡"
        elif res == 3:
            return "❌ 打卡失败，当前不在打卡时间段内"
        elif res == 4:
            return "❌ 打卡失败，jwsession 无效"            
        elif res == 5:
            return "❌ 打卡失败，登录错误，请检查账号信息"
        else:
            return "❌ 打卡失败，发生未知错误"
    
    # 推送打卡结果
    def sendNotification(self):
        notifyResult = self.getResult()
        # pushplus 推送
        url = 'http://www.pushplus.plus/send'
        notifyToken = self.pushPlus_data['notifyToken']
        content = json.dumps({
            "打卡用户": self.mark,
            "打卡项目": "日检日报",
            "打卡情况": notifyResult,
            "打卡信息": self.sign_data,
            "打卡时间": (datetime.datetime.now() + datetime.timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S'),
        }, ensure_ascii=False)
        msg = {
            "token": notifyToken,
            "title": "⏰ 我在校园打卡结果通知",
            "content": content,
            "template": "json"
        }
        body = json.dumps(msg).encode(encoding='utf-8')
        headers = {'Content-Type': 'application/json'}
        r = requests.post(url, data=body, headers=headers).json()
        if r["code"] == 200:
            print("消息经 pushplus 推送成功")
        else:
            print("pushplus: " + r['code'] + ": " + r['msg'])
            print("消息经 pushplus 推送失败，请检查错误信息")
def startdk():
    # 读取配置文件
    configs = utils.processJson("config.json").read()
    # 遍历每个用户的账户数据，进行打卡
    for config in configs:
        wzxy = WoZaiXiaoYuanPuncher(config)
        # 如果没有 jwsession，则 登录 + 打卡
        jwsession = wzxy.leanCloud_obj.getJwsession()
        if jwsession == "" or jwsession is None:
            print("使用账号密码登录")
            loginStatus = wzxy.login()
            if loginStatus:
                print("登录成功,开始打卡")
                wzxy.PunchIn()
            else:
                print("登录失败")
        else:
            print("检测到jwsession存在，使用jwsession打卡")
            wzxy.PunchIn()

if __name__ == '__main__':
    startdk()

def handler(event, context):
    startdk()

def main_handler(event, context):
    startdk()
