import RPi.GPIO as GPIO
import spidev
from time import sleep
import os
import Adafruit_DHT as dht
import paho.mqtt.client as mqtt
import json
from csv import writer
from datetime import datetime
import random

#deklarasi variabel
dt = datetime.today()
seconds = dt.timestamp()

detik_lalu = seconds
counter = 0

action1 = "Tidak Disiram"
action2 = "Tidak Disiram"

write1 = False
write2 = False

statePompa1 = False
statePompa2 = False

#setup mqtt
client = mqtt.Client()
client.connect("192.168.0.100")
client.loop_start()

#dict untuk json mqtt
label = ["date", "tanah1", "tanah2", "suhu", "hujan", "z1", "z2", "action1", "action2"]


#setup gpio
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

#setup pin spi
spi = spidev.SpiDev()
spi.open(0,0)
spi.max_speed_hz=1000000

#fungsi baca data adc
def readChannel(channel):
    val = spi.xfer2([1,(8+channel)<<4,0])
    data = ((val[1]&3) << 8) + val[2]
    return data

#inisiasi pin
DHT = 4
valve1=18
valve2=15
pompa=14

#setup pin relay
#initial high soalnya relay active low
GPIO.setup(valve1, GPIO.OUT, initial=GPIO.HIGH)
GPIO.setup(valve2, GPIO.OUT, initial=GPIO.HIGH)
GPIO.setup(pompa, GPIO.OUT, initial=GPIO.HIGH)

try:
    while True:
        #baca data
        tanah1 = readChannel(0)
        tanah2 = readChannel(1)
        hujan = readChannel(2)
        
        if (tanah1 != 0):
            print("tanah 1 = ",tanah1)
        if (tanah2 != 0):
            print("tanah 2 = ",tanah2)
        if (hujan != 0):
            print("hujan = ",hujan)
        hump,temp = dht.read_retry(dht.DHT22, DHT)
        
        if temp is not None:
            print("suhu = ", temp)
        else:
            temp = 28 + 2 * random.random()
            print("Failed to retrieve data from humidity sensor")
            print("suhu = ", temp)
                
                     
        # Fuzzy
        sensor_suhu = round (temp,2)
        sensor_tanah1 = round (( 100 - ( (tanah1/1023.00) * 100 ) ),2)
        sensor_tanah2 = round (( 100 - ( (tanah2/1023.00) * 100 ) ),2)
        sensor_hujan = round (( 100 - ( (hujan/1023.00) * 100 ) ),2)
        
        print ("nilai sensor suhu = ",sensor_suhu)
        print ("nilai sensor tanah 1 = ",sensor_tanah1)
        print ("nilai sensor tanah 2 = ",sensor_tanah2)
        print ("nilai sensor hujan = ",sensor_hujan)
        
        #realtime data sensor ke dashboard
        data_realtime = {"tanah1": sensor_tanah1, "tanah2":sensor_tanah2, "suhu":sensor_suhu, "hujan":sensor_hujan}
        client.publish('SistemPenyiramTanaman/Realtime', json.dumps(data_realtime), 1)
        
        suhu = [0, 0, 0]
        tanah1 = [0, 0]
        tanah2 = [0, 0]
        hujan = [0, 0]

        rule1 = [[[0, 0], [0, 0]], [[0, 0], [0, 0]], [[0, 0], [0, 0]]]
        rule2 = [[[0, 0], [0, 0]], [[0, 0], [0, 0]], [[0, 0], [0, 0]]]

        #fuzzyfikasi
        #sensor suhu
        #suhu dingin
        if sensor_suhu < 20:
            suhu[0] = 1
        elif sensor_suhu < 25:
            suhu[0] = (25 - sensor_suhu)/(25 - 20)
        else:
            suhu[0] = 0

        #suhu ruangan
        if sensor_suhu < 20:
            suhu[1] = 0
        elif sensor_suhu < 25:
            suhu[1] = (sensor_suhu - 20)/(25 - 20)
        elif sensor_suhu < 30:
            suhu[1] = 1
        elif sensor_suhu < 35:
            suhu[1] = (35 - sensor_suhu)/(35 - 30)
        else :
            suhu[1] = 0
            
        #suhu panas
        if sensor_suhu < 30:
            suhu[2] = 0
        elif sensor_suhu < 35:
            suhu[2] = (sensor_suhu - 30)/(35 - 30)
        else :
            suhu[2] = 1


        #sensor tanah 1
        #tanah basah
        if sensor_tanah1 < 33:
            tanah1[0] = 0
        elif sensor_tanah1 < 67:
            tanah1[0] = (sensor_tanah1 - 33)/(67 - 33)
        else :
            tanah1[0] = 1

        #tanah kering
        if sensor_tanah1 < 33:
            tanah1[1] = 1
        elif sensor_tanah1 < 67:
            tanah1[1] = (67 - sensor_tanah1)/(67 - 33)
        else :
            tanah1[1] = 0
            
        #sensor tanah 2
        #tanah basah
        if sensor_tanah2 < 33:
            tanah2[0] = 0
        elif sensor_tanah2 < 67:
            tanah2[0] = (sensor_tanah2 - 33)/(67 - 33)
        else :
            tanah2[0] = 1

        #tanah kering
        if sensor_tanah2 < 33:
            tanah2[1] = 1
        elif sensor_tanah2 < 67:
            tanah2[1] = (67 - sensor_tanah2)/(67 - 33)
        else :
            tanah2[1] = 0

        #sensor hujan
        #sedang hujan
        if sensor_hujan < 33:
            hujan[0] = 0
        elif sensor_hujan < 67:
            hujan[0] = (sensor_hujan - 33)/(67 - 33)
        else :
            hujan[0] = 1

        #tidak hujan
        if sensor_hujan < 33:
            hujan[1] = 1
        elif sensor_hujan < 67:
            hujan[1] = (67 - sensor_hujan)/(67 - 33)
        else :
            hujan[1] = 0

        #inferensi
        #rule[0][0][0] = dingin, basah, hujan = tidak disiram
        #rule[0][0][1] = dingin, basah, tidak hujan = tidak disiram
        #rule[0][1][0] = dingin, kering, hujan = tidak disiram
        #rule[0][1][1] = dingin, kering, tidak hujan = tidak disiram
        #rule[1][0][0] = sedang, basah, hujan = tidak disiram
        #rule[1][0][1] = sedang, basah, tidak hujan = tidak disiram
        #rule[1][1][0] = sedang, kering, hujan = tidak disiram
        #rule[1][1][1] = sedang, kering, tidak hujan = DISIRAM
        #rule[2][0][0] = panas, basah, hujan = tidak disiram
        #rule[2][0][1] = panas, basah, tidak hujan = tidak disiram
        #rule[2][1][0] = panas, kering, hujan = tidak disiram
        #rule[2][1][1] = panas, kering, tidak hujan = DISIRAM
            
        defuzzyfication1 = 0
        defuzzyfication2 = 0

        for i in range(3):
            for j in range(2):
                for k in range(2):
                    rule1[i][j][k] = min(suhu[i], tanah1[j], hujan[k])
                    rule2[i][j][k] = min(suhu[i], tanah2[j], hujan[k])

                    defuzzyfication1 += rule1[i][j][k]
                    defuzzyfication2 += rule2[i][j][k]
                    

        z1 = ((rule1[0][0][0] * (1 - rule1[0][0][0])) + (rule1[0][0][1] * (1 - rule1[0][0][1])) + (rule1[0][1][0] * (1 - rule1[0][1][0])) + (rule1[0][1][1] * (1 - rule1[0][1][1])) + (rule1[1][0][0] * (1 - rule1[1][0][0])) + (rule1[1][0][1] * (1 - rule1[1][0][1])) + (rule1[1][1][0] * (1 - rule1[1][1][0])) + (rule1[1][1][1] * rule1[1][1][1]) + (rule1[2][0][0] * (1 - rule1[2][0][0])) + (rule1[2][0][1] * (1 - rule1[2][0][1])) + (rule1[2][1][0] * (1 - rule1[2][1][0])) + (rule1[2][1][1] * rule1[2][1][1]))/defuzzyfication1
        z2 = ((rule2[0][0][0] * (1 - rule2[0][0][0])) + (rule2[0][0][1] * (1 - rule2[0][0][1])) + (rule2[0][1][0] * (1 - rule2[0][1][0])) + (rule2[0][1][1] * (1 - rule2[0][1][1])) + (rule2[1][0][0] * (1 - rule2[1][0][0])) + (rule2[1][0][1] * (1 - rule2[1][0][1])) + (rule2[1][1][0] * (1 - rule2[1][1][0])) + (rule2[1][1][1] * rule2[1][1][1]) + (rule2[2][0][0] * (1 - rule2[2][0][0])) + (rule2[2][0][1] * (1 - rule2[2][0][1])) + (rule2[2][1][0] * (1 - rule2[2][1][0])) + (rule2[2][1][1] * rule2[2][1][1]))/defuzzyfication2
        print("nilai fuzzy lahan 1 : ",z1)
        print("nilai fuzzy lahan 2 : ",z2)
        
        #z1 untuk valve pertama
        if z1 <= 0.5:
            #tidak disiram
            GPIO.output(valve1,1)
            statePompa1 = False
            if statePompa1 == True or statePompa2 == True:
                GPIO.output(pompa,0)
            else:
                GPIO.output(pompa,1)
            print("valve 1 ditutup")
            action1 = "Tidak disiram"
            
            if write1 == True:
                now = datetime.now()
                tgl = now.strftime("%m/%d/%Y %H:%M:%S")
                List = [tgl, sensor_tanah1, sensor_tanah2, sensor_suhu, sensor_hujan, z1, z2, action1, action2]
                with open('data.csv', 'a') as data:
                    writer_object = writer(data)
                    writer_object.writerow(List)
                    data.close()
                write1 = False
                
                #mqtt
                data_siram = dict(zip(label,List))
                client.publish('SistemPenyiramTanaman/Data', json.dumps(data_siram), 1)
                
        else :
            #disiram
            GPIO.output(valve1,0)
            statePompa1 = True
            GPIO.output(pompa,0)
            print("valve 1 dibuka")
            action1 = "Disiram"
            
            if write1 == False:
                now = datetime.now()
                tgl = now.strftime("%m/%d/%Y %H:%M:%S")
                List = [tgl, sensor_tanah1, sensor_tanah2, sensor_suhu, sensor_hujan, z1, z2, action1, action2]
                with open('data.csv', 'a') as data:
                    writer_object = writer(data)
                    writer_object.writerow(List)
                    data.close()
                write1 = True
                
                #mqtt
                data_siram = dict(zip(label,List))
                client.publish('SistemPenyiramTanaman/Data', json.dumps(data_siram), 1)
                            
        #z2 untuk valve kedua
        if z2 <= 0.5:
            #tidak disiram
            GPIO.output(valve2,1)
            statePompa2 = False
            if statePompa1 == True or statePompa2 == True:
                GPIO.output(pompa,0)
                print("pompa nyala (if z2)")
            else:
                GPIO.output(pompa,1)
            
            print("valve 2 ditutup")
            action2 = "Tidak disiram"
            
            if write2 == True:
                now = datetime.now()
                tgl = now.strftime("%m/%d/%Y %H:%M:%S")
                List = [tgl, sensor_tanah1, sensor_tanah2, sensor_suhu, sensor_hujan, z1, z2, action1, action2]
                with open('data.csv', 'a') as data:
                    writer_object = writer(data)
                    writer_object.writerow(List)
                    data.close()
                write2 = False
                
                #mqtt
                data_siram = dict(zip(label,List))
                client.publish('SistemPenyiramTanaman/Data', json.dumps(data_siram), 1)
        else :
            #disiram
            GPIO.output(valve2,0)
            statePompa2 = True
            GPIO.output(pompa,0)
            print("valve 2 dibuka")
            action2 = "Disiram"
            
            if write2 == False:
                now = datetime.now()
                tgl = now.strftime("%m/%d/%Y %H:%M:%S")
                List = [tgl, sensor_tanah1, sensor_tanah2, sensor_suhu, sensor_hujan, z1, z2, action1, action2]
                with open('data.csv', 'a') as data:
                    writer_object = writer(data)
                    writer_object.writerow(List)
                    data.close()
                write2 = True
                
                #mqtt
                data_siram = dict(zip(label,List))
                client.publish('SistemPenyiramTanaman/Data', json.dumps(data_siram), 1)
                       
        print("status pompa 1 = ", statePompa1)
        print("status pompa 2 = ", statePompa2)
        
        #write data setiap 5 menit
        dt = datetime.today()  # Get timezone naive now
        seconds = dt.timestamp()
        if counter >= 300:
            now = datetime.now()
            tgl = now.strftime("%m/%d/%Y %H:%M:%S")
            List = [tgl, sensor_tanah1, sensor_tanah2, sensor_suhu, sensor_hujan, z1, z2, action1, action2]
            with open('data1.csv', 'a') as data:
                writer_object = writer(data)
                writer_object.writerow(List)
                data.close()
            counter -= 300
            
            #mqtt
            #data_siram = dict(zip(label,List))
            #client.publish('SistemPenyiramTanaman/Data', json.dumps(data_siram), 1)
            
        counter += seconds - detik_lalu
        detik_lalu = seconds
        


except KeyboardInterrupt:
    GPIO.cleanup()
    print ("end of program.")
