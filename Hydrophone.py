# -*- coding: utf-8 -*-
"""
Created on Wed Jan 25 17:13:21 2023

@author: aovbui
"""


import psycopg2
import pandas as pd
from onc.onc import ONC
from datetime import datetime
from datetime import timedelta

import os
#os.chdir(r'\\ONC-FILESERVER\redirect4\aovbui\Documents\PythonScripts')


token='***REMOVED***'
onc = ONC(token)
Days=14
PlotHeight=400
DeviceType='Hydrophones'
datefrom='2025-04-07T00:00:00.000Z'

Hier=datetime.today()- timedelta(days = 1)
Yesterday=datetime.strftime(Hier, '%d-%b-%Y')


deviceCategoryCode=['HYDROPHONE']

MyDevices=pd.DataFrame(columns=['locationCode', 'locationName', 'begin', 'deviceCode', 'deviceCategoryCode', 'deviceCategoryID', 'DSURL', 'Depth', 'deviceID', 'deviceName',
                                'siteDeviceID','searchTreeNodeID','dataProductFormatID'])


for i in range(len(deviceCategoryCode)):   
    result = onc.getDeployments({'deviceCategoryCode':deviceCategoryCode[i], 'dateFrom': datefrom})     
    for j in range(len(result)):
        if not result[j]['end']:
            myloc=onc.getLocations({'locationCode':result[j]['locationCode']})
            
            oneDevice=pd.DataFrame(data=[[result[j]['locationCode'],myloc[0]['locationName'], result[j]['begin'], result[j]['deviceCode'],result[j]['deviceCategoryCode'], 
                                          myloc[0]['dataSearchURL'],result[j]['depth']]],
                                   columns=['locationCode','locationName', 'begin', 'deviceCode', 'deviceCategoryCode', 'DSURL',  'Depth'])
            MyDevices=pd.concat([MyDevices, oneDevice])
                       
MyDevices=MyDevices.sort_values(by=['locationCode'])
MyDevices=MyDevices.reset_index(drop=True)
        

for k in range(len(MyDevices)):
    result=onc.getDevices({'deviceCode':MyDevices.deviceCode[k]})
    MyDevices.loc[k, "deviceID"]=result[0]['deviceId']
    MyDevices.loc[k, "deviceName"]=result[0]['deviceName']
   
    
MyDevices['deviceCategoryID']=""
try:
    conn = psycopg2.connect("dbname='dmas' user='www' host='***REMOVED***' password='***REMOVED***'")
except:
    print ("I am unable to connect to the database")
cur = conn.cursor()
for l in range(len(MyDevices.deviceID)):
    cur.execute("""SELECT devicecategoryid from device where deviceid ="""+str(MyDevices.deviceID[l]))

    MyDevices.loc[l, 'deviceCategoryID']=str(cur.fetchall()[0][0])
    
    
MyDevices['siteDeviceID']=""
try:
    conn = psycopg2.connect("dbname='dmas' user='www' host='***REMOVED***' password='***REMOVED***'")
except:
    print ("I am unable to connect to the database")
cur = conn.cursor()
for l in range(len(MyDevices.deviceID)):
    cur.execute("""SELECT sitedeviceid from sitedevice where deviceid = (%s) and datefrom = (%s)""", (str(MyDevices.deviceID[l]), str(MyDevices.begin[l])))
    MyDevices.loc[l, 'siteDeviceID']=cur.fetchall()[0][0] 

MyDevices['searchTreeNodeID']=""
try:
    conn = psycopg2.connect("dbname='dmas' user='www' host='***REMOVED***' password='***REMOVED***'")
except:
    print ("I am unable to connect to the database")
cur = conn.cursor()
for l in range(len(MyDevices)):
    cur.execute("""SELECT searchtreenodeid from searchtreenodesitedevice where sitedeviceid ="""+str(MyDevices.siteDeviceID[l]))
    MyDevices.loc[l, 'searchTreeNodeID']=cur.fetchall()[0][0] 

 
MyDevices['dataProductFormatID']=[[176,53] for l in MyDevices.index]
    
    
with open ("/Users/herminio/Library/CloudStorage/OneDrive-UniversityofVictoria/Desktop/Hydrophone Daily Checks Dashboard/Hydrophone.html", 'w') as file:
    file.write('<!DOCTYPE html>'+'\n')
    file.write('<html>'+'\n')
    file.write('<head>'+'\n')
    file.write('\t'+'<meta charset="UTF-8">'+'\n')
    file.write('\t'+'<title>'+DeviceType+'</title>'+'\n')
    file.write('\t'+'<script src="assets/uPlot.iife.min.js"></script>'+'\n')
    file.write('\t'+'<script src="assets/oncdw.min.js"></script>'+'\n')
    file.write('\t'+'<link rel="stylesheet" href="assets/uPlot.min.css" />'+'\n')
    file.write('\t'+'<link rel="stylesheet" href="assets/oncdw.min.css" />'+'\n')
    file.write('\t'+'<link rel="stylesheet" href="assets/instaboard.css" />'+'\n')
    file.write('\t'+'<style>'+'\n')
    file.write('\t'+'.oncWidgetGroup.gifs { text-align: justify; }'+'\n')
    file.write('\t'+'.oncWidgetGroup.gifs .widgetWrap { display: inline-block; width: auto;  clear: none; margin-right: 5px; }'+'\n')
    file.write('\t'+'.oncWidgetGroup.gifs .contents {  }'+'\n')
    file.write('\t'+'</style>'+'\n')
    file.write('</head>'+'\n')
    file.write('<body>'+'\n')
    file.write('\t'+'<data id="oncdw" data-token="'+ token+'"></data>'+'\n')
    file.write('\t'+'<h1>'+DeviceType+'</h1>'+'\n')
    file.write('\t'+'<div class="sidenav">'+'\n')
    file.write('\t'+'<ul class="nav">'+'\n')
    file.write('\t'+'<li>'+'\n')
    nb=0
    for i in range(len(MyDevices.locationCode)):
         file.write('\t'+'<a href="#wf_'+str(nb)+'"><span class="device"><span>Site</span>'+MyDevices.locationCode[i]+'</span></a>'+'\n')
         file.write('\t'+'<ul>'+'\n')
         DF=MyDevices[MyDevices.locationCode==MyDevices.locationCode[i]]
         DF=DF.reset_index(drop=True)
         for h in range(len(DF)):
             file.write('\t'+'\t'+'<li><a href="#w_'+str(nb)+'"><span class="sensor"><span>'+str(DF.deviceID[h])+'</span>'+DF.deviceName[h]+'</span></a></li>'+'\n')
             nb=nb+1
         file.write('\t'+'</ul>'+'\n')    
         file.write('\t'+'</li>'+'\n')
    file.write('\t'+'</div>'+'\n')
    file.write('\n')
    nb=0     
    file.write('\t'+'<div class="main">'+'\n')
    for i in range(len(MyDevices.locationCode)): 
            file.write('\n')
            file.write('\t'+'<div class="section" id="wf_'+str(nb)+'">'+'\n')
            file.write('\t'+'<h2>'+MyDevices.locationCode[i]+ " - "+MyDevices.locationName[i]+'. Depth: '+str(MyDevices.Depth[i])+' m</h2>'+'\n')            
            file.write('\t'+'<section class="oncWidgetGroup" id="w_'+str(nb)+'">'+'\n')
            #file.write('\t'+'<h3>'+MyDevices.deviceName[i]+" - DI "+str(MyDevices.deviceID[i])+'. Depth: '+str(MyDevices.Depth[i])+' m </h3>'+'\n')
            file.write('\t'+'\t'+'<p><a href="http://data.oceannetworks.ca/DeviceListing?DeviceId='+str(MyDevices.deviceID[i])+'" target="_blank">Device Details </a>'+ '</a>and </a>' 
                       +'<a href="'+MyDevices.DSURL[i]+'" target="_blank">Data Search </a>'+ '</a>and </a>' +
                       '<a href="https://data.oceannetworks.ca/SearchHydrophoneData?LOCATION='+str(MyDevices.searchTreeNodeID[i])+'&DEVICE='+str(MyDevices.deviceID[i])+'&DATE='+Yesterday+'" target="_blank">Search Hydrophone </a></p>'+'\n')
            file.write('\t'+'\t'+'<div class="widgetWrap wgArchiveMap">'+'\n')
            file.write('\t'+'\t'+'\t'+'<div class="device"><span>'+str(MyDevices.deviceID[i])+'</span>'+MyDevices.deviceName[i]+'</div>'+'\n')
            file.write('\t'+'\t'+'\t'+'<div class="clear"></div>'+'\n')
            file.write('\t'+'\t'+'\t'+'<section class="oncWidget"'+'\n')
            file.write('\t'+'\t'+'\t'+'\t'+'data-widget="archiveMap"'+'\n')
            file.write('\t'+'\t'+'\t'+'\t'+'dateFrom="minus'+str(Days)+'d"'+'\n')
            file.write('\t'+'\t'+'\t'+'\t'+'dateTo="midnight"'+'\n')
            file.write('\t'+'\t'+'\t'+'\t'+'deviceCode="'+MyDevices.deviceCode[i]+'"'+'\n')  
            file.write('\t'+'\t'+'\t'+'\t'+'options="height: '+str(PlotHeight)+'"'+'\n')
            file.write('\t'+'\t'+'\t'+'\t'+'extension="wav, fft, mp3, flac, mat"'+'\n')
            file.write('\t'+'\t'+'\t'+'></section>'+'\n')
            file.write('\t'+'\t'+'</div>'+'\n')
            file.write('\t'+'\t'+'</section>'+'\n')
            for z in range(len(MyDevices.dataProductFormatID[i])):
                file.write('\t'+'\t'+'<figure class="oncWidget" data-widget="image" data-source="dataPreview"'+'\n')
                file.write('\t'+'\t'+'\t'+'url="https://data.oceannetworks.ca/DataPreviewService?operation=5&searchTreeNodeId='+str(MyDevices.searchTreeNodeID[i])+'&deviceCategoryId='+str(MyDevices.deviceCategoryID[i])+'&timeConfigId=2&dataProductFormatId='+str(MyDevices.dataProductFormatID[i][z])+'&plotNumber=1"'+'\n')
                file.write('\t'+'\t'+'\t'+'options="theme: gallery"'+'\n')
                file.write('\t'+'\t'+'></figure>'+'\n')       
            file.write('\t'+'</div>'+'\n')
            nb=nb+1        
            file.write('\t'+'<section class="oncWidgetGroup" source="plottingUtility" engine="name: dygraphs">'+'\n')
            file.write('\t'+'<div class="widgetWrap wgSensor" id="w_'+str(nb)+'">'+'\n')
            file.write('\t'+'\t'+'<div class="device"><span>'+str(MyDevices.deviceID[i])+'</span>'+MyDevices.deviceName[i]+'</div>'+'\n')
            file.write('\t'+'\t'+'<div class="clear"></div>'+'\n')
            file.write('\t'+'\t'+'<section class="oncWidget" data-widget="archiveFiles" dateFrom="yesterday" dateTo="yesterday+1h" extension="flac" deviceCode="'+str(MyDevices.deviceCode[i])+'"></section>'+'\n') 
            file.write('\t'+'</div>'+'\n') 
    file.write('\t'+'\t'+'</div>'+'\n')                 
    file.write('</body>'+'\n')   
    file.write('</html>'+'\n')  
    file.close                
    	    
