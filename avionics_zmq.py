#!/usr/bin/env python 
# -*- coding: utf-8 -*-
"""Script to gather get data either from X-Plane or from AID , parse it 
then send it (read main docstring)

Attributes:
    aid_set_dict (TYPE): Description
    t_end (int): Description
    t_start (int): Description
    xplane_custom_pos (TYPE): Description
    xplane_set_dict (TYPE): Description
"""
import sys
import os
import time
from optparse import OptionParser
from threading import Thread 
import socket
import struct
from pprint import pprint as pp
import math
import pmt
import zmq
import signal
import serial

t_start=0
t_end=0
v=0
class data_collect(object):
    """this class contains the defininition of data tracked 
    for now they are all listed as class variables. it's better to read
    from a config file
    
    Attributes:
        key_dict (TYPE): Description
        vdict (TYPE): Description
    """
    def __init__(self):
        """Summary
        """
        self.key_dict=dict() # var_name: var_key
        self.vdict=dict() # var_key:{xplane:xplane_var,aid:aid:aid_var}

    def add_var(self,var_name,var_key):
        """add label {name:ukey} to vdict
        
        args:
            var_name (string): name of variable just for debug
            var_key (int): reference key (must be unique)
        """
        # TODO: check var_key unique (raise)
        self.key_dict[var_name]=var_key
        self.vdict[var_key]={"xplane":dict(),"aid":dict(),"ublox":dict()}

    def get_var_key(self,var_name):
        """Summary
        
        Args:
            var_name (TYPE): Description
        
        Returns:
            TYPE: Description
        """
        return self.key_dict["var_name"]

    def set_xplane_var(self,var_name,data_set,data_pos,func=None,arg_list=None):
        """sets xplane info for var
        Args (string ):
        var_name (string): variable name
        data_set(int): data set number containing variable
        data_pos(int): position of data within set
        func(string): convertion funion name should be in globals (default = None)
                     /!\ warning: for CUSTOM data_set it's using the recv_dict keys
        arg_list(list): argument list for funtion (default = None)
        
        Args:
            var_name (TYPE): Description
            data_set (TYPE): Description
            data_pos (TYPE): Description
            func (None, optional): Description
            arg_list (None, optional): Description
        """
        x_dict={
        "data_set":data_set,
        "data_pos":data_pos,
        "func":func,
        "args":arg_list}
        self.vdict[self.key_dict[var_name]]["xplane"]=x_dict

    def set_aid_var(self,var_name,channel,label,func=None,arg_list=None):
        """sets xplane info for var
        Args (string ):
        var_name (string): variable name
        data_set(int): AID channel 
        data_pos(int): AID label
        func(string): convertion funion name should be in globals (default = None)
                     /!\ warning: for CUSTOM data_set it's using the recv_dict keys
        arg_list(list): argument list for funtion (default = None)
        
        Args:
            var_name (TYPE): Description
            channel (TYPE): Description
            label (TYPE): Description
            func (None, optional): Description
            arg_list (None, optional): Description
        """
        x_dict={
        "channel":channel,
        "label":label,
        "func":func,
        "args":arg_list}
        self.vdict[self.key_dict[var_name]]["aid"]=x_dict

    def set_ublox_var(self,var_name,nmea_sen,pos,func=None,arg_list=None):
        """Summary
        
        Args:
            var_name (string): variable name
            nmea_sen (string): NMEA sentence
            pos (TYPE): position
            func (None, optional): conversion fuction
            arg_list (None, optional): argument list
        """
        x_dict={
        "nmea_sen":nmea_sen,
        "pos":pos,
        "func":func,
        "args":arg_list}
        self.vdict[self.key_dict[var_name]]["ublox"]=x_dict

    def get_xplane_dict(self):
        """get all non empty xplane variables
        return {key:xplane_dict}
        xplane_dict 
        
        Returns:
            TYPE: Description
        """
        result = dict()
        for key in self.vdict:
            xplane_dict=self.vdict[key]["xplane"]
            if len(xplane_dict)!=0:
                #result[key]=self.vdict[key]["xplane"]
                data_set=xplane_dict["data_set"]
                data_pos=xplane_dict["data_pos"]
                data= (key,xplane_dict["func"],xplane_dict["args"])
                if data_set not in result:
                    result[data_set]={data_pos:data}
                else:
                    result[data_set][data_pos]=data
        return result

    def get_aid_dict(self):
        """get all non empty aid variables
        return {key:aid_dict}
        
        Returns:
            TYPE: Description
        """
        
        result = dict()
        for key in self.vdict:
            aid_dict=self.vdict[key]["aid"]
            if len(aid_dict)!=0:
                #result[key]=self.vdict[key]["xplane"]
                data_set=aid_dict["channel"]
                data_pos=aid_dict["label"]
                data= (key,aid_dict["func"],aid_dict["args"])
                if data_set not in result:
                    result[data_set]={data_pos:data}
                else:
                    result[data_set][data_pos]=data
        return result

    def get_ublox_dict(self):
        """get all non empty ublox variables
        return {key:ublox_dict}
        
        Returns:
            TYPE: Description
        """
        result = dict()
        for key in self.vdict:
            ublox_dict=self.vdict[key]["ublox"]
            if len(ublox_dict)!=0:
                nmea_sen=ublox_dict["nmea_sen"]
                pos=ublox_dict["pos"]
                data=(key,ublox_dict["func"],ublox_dict["args"])
                if nmea_sen not in result:
                    result[nmea_sen]={pos:data}
                else:
                    result[nmea_sen][pos]=data
        return result


class Xplane(object):
    """This class contains methodes to get and parse data from XPlane
    for polymorphism : check(), connect() update(dict) and start() must be 
    implemented
    
    Attributes:
        adr (TYPE): Description
        data_subs (TYPE): Description
        sock (TYPE): Description
    """

    def __init__(self, data_subs_dict,adr,nsew_vel=True):
        """constructor
        
        args:
            data_subs_dict (TYPE): Description
            adr (ip,port): xplane machine address 
                ip (string): ip address format xx.xx.xx.xx
                port(int): port
            nsew_vel (bool, optional): Description
        
        Deleted Parameters:
            data_subs_dict(dict): variable to track format:
                {data_set:{position:(var_key,func,arg_list}}
        """
        self.data_subs= data_subs_dict
        self.adr=adr
        self.sock=None


    
    def check(self):
        """check if connection is alive
        
        Returns:
            TYPE: Description
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect(self.adr)
        except Exception as e:
            print("unable to reach %s:%d. Exception is %s" % 
                (self.adr[0], self.adr[1], e))
            return False
        finally:
            sock.close()
        return True
    def connect(self):
        """Summary
        """
        if(self.check):
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.bind(self.adr)
            print "[info] xplane connected to "+ str(self.adr)
    def disconnect(self):
        """Summary
        """
        self.sock.close()
        print "[info] xplane disconnected from "+ str(self.adr)

    def recv(self):
        """receive data from xplane and upack them
        
        return:
            recv_dict(dict): {} 
        """
        header="DATA"
        #TODO implement gracefull handling of ctr-c for recv
        data, addr = self.sock.recvfrom(2048) # buffer size is 2048 bytes
        global t_start
        t_start=time.time()
        if header not in data: # check if header is present
            return
        payload = data[5:]
        unpacker = struct.Struct('I 8f')
        recv_dict=dict() # hold received value {data_set:data_list}
        for i in range(0,len(payload),36):
            set_list = unpacker.unpack(payload[i:i+36])
            recv_dict[set_list[0]]=set_list[1:]
        return recv_dict 

    def format_recv(self,recv_dict):
        """format recv
        
        Args:
            recv_dict (TYPE): Description
        
        Returns:
            TYPE: Description
        """
        result=dict()
        # prosses custum and remove it 
        # /!\ handle custum key
        custum_set=255
        if custum_set in self.data_subs:
            for pos_sub in self.data_subs[custum_set]:
                var_key=self.data_subs[custum_set][pos_sub][0]
                func=self.data_subs[custum_set][pos_sub][1]
                args=self.data_subs[custum_set][pos_sub][2]
                # func is alwase no None and callable
                val=func(*([recv_dict]+args))
                result[var_key]=val

        for data_set_sub in self.data_subs.keys():
            if data_set_sub in recv_dict:
                for pos_sub in self.data_subs[data_set_sub]:
                    var_key=self.data_subs[data_set_sub][pos_sub][0]
                    func=self.data_subs[data_set_sub][pos_sub][1]
                    args=self.data_subs[data_set_sub][pos_sub][2]
                    val=recv_dict[data_set_sub][pos_sub]
                    if callable(func):
                        if args:
                            val= func(*([val]+args))
                        else:
                            val= func(val)
                    result[var_key]=val
        return result



    #<END of class Xplane>
        
class AID(object):
    """docstring for ClassName
    
    Attributes:
        adr (TYPE): Description
        data_subs (TYPE): Description
        sock (TYPE): Description
    """
    def __init__(self, data_subs_dict,adr,nsew_vel=True):
        """Summary
        
        Args:
            data_subs_dict (TYPE): Description
            adr (TYPE): Description
            nsew_vel (bool, optional): Description
        """
        self.data_subs= data_subs_dict
        self.adr=adr
        self.sock=None
    def check(self):
        """Summary
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect(self.adr)
        except Exception as e:
            print("unable to reach %s:%d. Exception is %s" % 
                (self.adr[0], self.adr[1], e))
            return False
        finally:
            sock.close
    def connect(self):
        """Summary
        """
        if(self.check):
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect(self.adr)
            print "[info] AID connected to "+ str(self.adr)
            #ask for labels
            for channel in self.data_subs:
                for label in self.data_subs[channel]:
                    self.sock.send("add,%i,%i\n" % (channel,label))
                    print '[info] add,%i,%i\n' % (channel,label)
    def disconnect(self):
        """Summary
        """
        self.sock.close()
        print "[info] AID disconnected from "+ str(self.adr)
    def recv(self):
        """receive aid data
        
        Returns:
            [[float, int, int, int]...]: result a list of lists [[aid_time(sec),channel,label,data],...]
        """
        #TODO implement gracefull handling of ctr-c for recv
        #TODO replace with a generator
        data, addr = self.sock.recvfrom(2048) # buffer size is 2048 bytes
        data=data.split('\n')
        result=list()
        for elm in data:
            if 'data' in elm:
                temp=elm.split(',')
                result.append([float(temp[1]), #time_stamps
                                int(temp[2]),  #chanel
                                int(temp[3]),   #Label
                                int(temp[4],16)]) # data
        return result
    def format_recv(self,recv_list):
        """Summary
        
        Args:
            recv_list (TYPE): Description
        """
        for elm in recv_list:
            print 'raw: '+str(elm)
            if elm:
                channel=elm[1]
                label=elm[2]
                val=elm[3]
                var_key=self.data_subs[channel][label][0]
                func=self.data_subs[channel][label][1]
                args=self.data_subs[channel][label][2]
                val= func(*([val]+args))
                print 'decoded: '+str(val)



#<END of class AID>

class NMEA_ublox(object):
    """decode NMEA data from ublox
    
    Attributes:
        com (TYPE): Description
        data_subs (TYPE): Description
        sock (TYPE): Description
    """
    #TODO clean-up
    def __init__(self,data_subs_dict,com,baud=115200):
        """constructor
        
                Args:
                    data_subs_dict(dict): variable to track format:
                 {NMEA_sentence:{position:(var_key,func,arg_list}}
                    com (string): com port
        
        Args:
            data_subs_dict (TYPE): Description
            com (TYPE): Description
        """
        self.data_subs= data_subs_dict
        self.port=com
        self.baud=baud
        self.ser=None
        self.isock=None

    def check(self):
        """Summary
        """
        ser = serial.Serial(self.port, self.baud, timeout=1)
        if ser.isOpen() :print ser.name+' is available...'
        ser.close()
        return 0
    def connect(self):
        """Summary
        """
        self.ser = serial.Serial(self.port, self.baud, timeout=1)
        if self.ser.isOpen() :print self.ser.name+' is now open...'
        context = zmq.Context()
        self.isock = context.socket(zmq.PUB)
        self.isock.bind("ipc://my-endpoint")
    def disconnect(self):
        """Summary
        """
        self.ser.close()
        if not (self.ser.isOpen()) :print '[info] '+self.ser.name+' is now closed...'
    def recv(self):
        """Summary
        """
        if self.ser.isOpen() :
            data = self.ser.readline().rstrip()
            for key in self.data_subs.keys():
                if key in data:
                    self.isock.send(data)
                    return (key,data)
    def format_recv(self,recv_list):
        #get parse func
        nmea_sen= recv_list[0]
        recv_txt=recv_list[1]
        data_subs=self.data_subs
        key0=data_subs[nmea_sen].keys()[0]
        func=data_subs[nmea_sen][key0][1]
        parsed=func(recv_txt)
        result=dict()
        key0=data_subs[nmea_sen].keys()[0]
        for pos in data_subs[nmea_sen]:
            result[data_subs[nmea_sen][pos][0]]=parsed[pos]
        return result

#<end of ENMEA_ublox>

class Zmq_pmt(object):
    """class for managing zmq and pmt transfers"""
    def __init__(self, adr):
        """constructor
        args
        adr(tuple): adress of zmq (ip,port)
            ip(string): xx.xx.xx.xx
            port(int)
        
        Args:
            adr (TYPE): Description
        """
        self.adr = adr
        self.zmq_sock=None
    def connect(self):
        """create zmq sock
        """
        context = zmq.Context()
        adr="tcp://"+self.adr[0]+":"+str(self.adr[1])
        self.zmq_sock = context.socket(zmq.PUSH)
        self.zmq_sock.setsockopt(zmq.SNDTIMEO, 1000)
        self.zmq_sock.bind(adr)
        print "[info] zmq connected to "+ str(self.adr)
    
    def disconnect(self):
        """Summary
        """
        self.zmq_sock.close()
        print "[info] zmq disconnected from "+ str(self.adr)

    def send_dict(self,dict_to_send):
        """send data dict through zmq
        
        args:
            dict_to_send (TYPE): Description
        
        Deleted Parameters:
            dict_to_send(dict): {var_key:value}
        """
        pmt_dict=pmt.to_pmt(dict_to_send)
        pmt_ser=pmt.serialize_str(pmt_dict)
        global t_end
        t_end= time.time()
        self.zmq_sock.send(pmt_ser)
        
def main():
    """TODO: document this
    """
    #--------Define options--------------------
    usage = """ %prog [options] src 
                src == x ==> source is X-Plane
                src == a ==> source is AID
                src == u ==> source is Ublock"""
    version = 0.1
    parser = OptionParser(usage=usage,version=version)    
    parser.add_option("-s", "--src",
                  dest="src_adr",
                  type="string",
                  default="0.0.0.0:49000",
                  help="source ip address ip:port default=10.10.201.254:49000")
    parser.add_option("-d", "--dest",
                  dest="dest_adr",
                  type="string",
                  default="127.0.0.1:5556",
                  help="destination ip address ip:port default=127.0.0.1:5556")
    parser.add_option("-l", "--log",
                  dest="log_file_prefix",
                  type="string",
                  help="log data into a file")
    parser.add_option("-u", "--com",
                  dest="com",
                  type = "string",
                  default="/dev/ttyACM0",
                  help="u-Blox serial com.")
    parser.add_option("-t", "--tx_ms",
                  dest="tx_ms",
                  type = "int",
                  help="transmition min periode in ms")
    parser.add_option("-r", "--rx_ms",
                  dest="rx_ms",
                  type = "int",
                  help="transmition min periode in ms")

    #--------Parse options--------------------

    (options, args) = parser.parse_args()
    if (len(args) != 1) or ((args[0]!="a") and (args[0]!="x") and (args[0]!="u"))  :
        parser.error("argument must be x, a or u")
    print options
    print args
    mode =args[0]
    src_ip,src_port = parse_adr(options.src_adr)
    dest_ip,dest_port = parse_adr(options.dest_adr)
    file_prefix=options.log_file_prefix
    com_port=options.com
    #--------subscribe variables------------------
    #TODO: AID
    #TODO: document data pos
    dc= data_collect()
    
    dc.add_var("UTC_SEC",0)
    dc.set_xplane_var("UTC_SEC",xplane_set_dict["TIMES"],5,scale_to_int,[3600])
    dc.set_aid_var("UTC_SEC",aid_set_dict['GNSS'],150,bcd_decode,[[1,5,6,6],[0,3600,60,1]])
    #dc.set_aid_var("UTC_SEC",aid_set_dict['GNSS'],150,bcd_decode,[[1,5,6,6],[0,10000,100,1]]) # test
    dc.set_ublox_var("UTC_SEC","GGA",0,parse_GGA)
    
    dc.add_var("GPS_LAT",10)
    dc.set_xplane_var("GPS_LAT",xplane_set_dict["GPS"],0)
    dc.set_aid_var("GPS_LAT",aid_set_dict['GNSS'],110,bnr_decode,[20,180,0.000172]) #BUG: precesion 
    dc.set_ublox_var("GPS_LAT","GGA",1,parse_GGA)
    
    dc.add_var("GPS_LON",11)
    dc.set_xplane_var("GPS_LON",xplane_set_dict["GPS"],1) 
    dc.set_aid_var("GPS_LON",aid_set_dict['GNSS'],111,bnr_decode,[20,180,0.000172]) #BUG: precesion 
    dc.set_ublox_var("GPS_LON","GGA",2,parse_GGA)

    dc.add_var("BARO_ALT",21) 
    dc.set_xplane_var("BARO_ALT",xplane_set_dict["GPS"],2) #MSL alt
    dc.set_aid_var("BARO_ALT",aid_set_dict['ADC1'],203,bnr_decode,[17,131072,1]) 
    dc.set_ublox_var("BARO_ALT","GGA",3,parse_GGA)
    
    dc.add_var("GPS_ALT",22) 
    #picked indicated alt as gps alt to manualy add error
    dc.set_xplane_var("GPS_ALT",xplane_set_dict["GPS"],5)
    dc.set_aid_var("GPS_ALT",aid_set_dict['GNSS'],370,bnr_decode,[20,131072,0.125])


    dc.add_var("NS_SPEED",34) 
    #dc.set_xplane_var("NS_SPEED",xplane_set_dict["CUSTOM"],0,calc_ns_speed,[
        #(xplane_set_dict["HEADING"],3),
        #(xplane_set_dict["SPEED"],3)])
    dc.set_aid_var("NS_SPEED",aid_set_dict['GNSS'],166,bnr_decode,[15,4096,0.125])
    dc.set_ublox_var("NS_SPEED","VTG",3,parse_VTG)
    #add custom for ublcs

    dc.add_var("EW_SPEED",35) 
    #dc.set_xplane_var("EW_SPEED",xplane_set_dict["CUSTOM"],1,calc_ew_speed,[
        #(xplane_set_dict["HEADING"],3),
        #(xplane_set_dict["SPEED"],3)])
    dc.set_aid_var("EW_SPEED",aid_set_dict['GNSS'],174,bnr_decode,[15,4096,0.125])
    dc.set_ublox_var("EW_SPEED","VTG",2,parse_VTG)
    #add custom for ublcs

    dc.add_var("GROUND_KTS",32) 
    dc.set_xplane_var("GROUND_KTS",xplane_set_dict["SPEED"],3)
    dc.set_aid_var("GROUND_KTS",aid_set_dict['GNSS'],112,bnr_decode,[15,4096,0.125])
    dc.set_ublox_var("GROUND_KTS","VTG",1,parse_VTG)

    dc.add_var("VS_FPM",33) 
    dc.set_xplane_var("VS_FPM",xplane_set_dict["MACH_GLOAD"],2)
    dc.set_aid_var("VS_FPM",aid_set_dict['ADC1'],212,bnr_decode,[11,32768,16])

    dc.add_var("PITCH",42) 
    dc.set_xplane_var("PITCH",xplane_set_dict["HEADING"],0)
    dc.set_aid_var("PITCH",aid_set_dict['FMS1'],324,bnr_decode,[14,180,0.01])

    dc.add_var("ROLL",43) 
    dc.set_xplane_var("ROLL",xplane_set_dict["HEADING"],1)
    dc.set_aid_var("ROLL",aid_set_dict['FMS1'],325,bnr_decode,[14,180,0.01])

    dc.add_var("MAG_HDG",41) 
    dc.set_xplane_var("MAG_HDG",xplane_set_dict["HEADING"],3)
    dc.set_aid_var("MAG_HDG",aid_set_dict['IRS'],320,bnr_decode,[12,180,0.05]) # Note: verify precision
    dc.set_ublox_var("GROUND_KTS","VTG",0,parse_VTG)


    #--------src setup--------------------
    print "---------"   
    dest=Zmq_pmt((dest_ip,dest_port))
    if mode =='x':
        pp(dc.get_xplane_dict())
        src=Xplane(dc.get_xplane_dict(),(src_ip,src_port),False)
    if mode == 'a':
        raise('AA: not implemented')
    if mode == 'u':
        pp(dc.get_ublox_dict())
        src=NMEA_ublox(dc.get_ublox_dict(),com_port)

    src.check()
    src.connect()

    #-------dest setup------------
    dest=Zmq_pmt((dest_ip,dest_port))
    dest.connect();
    #-------logging---------------
    if file_prefix:
        thread = Thread(target = task_log, args = (file_prefix,))
        thread.setDaemon(True)
        thread.start()


    #-------------------------------
    #--------run--------------------
    try :
        while True:
            rec=src.recv()
            if rec:
                recv_data=src.format_recv(rec)
                pp(recv_data)
                print
                try:
                    dest.send_dict(recv_data)
                except zmq.error.Again:
                    print '[warning] zmq destination is not available' 

    except KeyboardInterrupt :
        print "\n[info] Gracefully killed"
        src.disconnect()
        dest.disconnect()

    # <END of main>
#------------------------------
# Globals
#------------------------------- 
def parse_adr(adr_str):
    """parse adr string to ("ip",port)
    return (string,int) (ip,port)
    
    Args:
        adr_str (TYPE): Description
    
    Returns:
        TYPE: Description
    """
    adr_str=adr_str.split(":")
    ip=adr_str[0]
    port=int(adr_str[1])
    return (ip,port) 
#--------LUT--------------------
#Xplane data set lists
xplane_set_dict={
    'TIMES'                 :1,
    'SPEED'                 :3,
    'MACH_GLOAD'            :4,
    'ATMOSPHERE_AIRCRAFT'   :6,
    'SYSTEM_PRESSURE'       :7,
    'HEADING'               :17,
    'AERODYNAMICS'          :19,
    'GPS'                   :20,# I assume that pos. as gps pos. and alt as baro
    'DISTTRAVELLED'         :21,
    'ENGINE_RPM'            :37,
    'N1'                    :41,
    'N2'                    :42,
    'FUEL_FLOW'             :45,
    'ITT'                   :46,
    'EGT'                   :47,
    'CHT'                   :48,
    'OIL_PRES'              :49,
    'OIL_TEMP'              :50,
    'FUEL_PRES'             :51,
    'BATTERY_AMP'           :53,
    'BATTERY_VOLT'          :54,
    'FUEL_WEIGHT'           :62,
    'PAYLOAD_WEIGHTS'       :63,
    'NAV_FREQ'              :97,
    'NAV_OBS'               :98,
    'NAV_DEFLECTION'        :99,
    'ADF'                   :100,
    'DME'                   :101,
    'GPS_STATUS'            :102,
    'EFIS'                  :106,
    'AUTOPILOT_MODES'       :117,
    'AUTOPILOT_VALUES'      :118,
    'CUSTOM'                :255} 
    # last one does't exists, It represent post calculated fields
 
#xplane data positions
xplane_custom_pos={
    'EW_SPEED'      :0,
    'NS_SPEED'      :1}
#AID chanels list
aid_set_dict={
    'FMS1'  :0,
    'FMS2'  :1,
    'IRS'   :2,
    'ARHS'  :3,
    'GNSS'  :4,
    'ADC1'  :5,
    'AFDR'  :6,
    'ADSB'  :7,
    'TCAS'  :8,
    'EFIS'  :9}
#conversion functions
def test(a):
    """Summary
    
    Args:
        a (TYPE): Description
    
    Returns:
        TYPE: Description
    """
    print "[warning] test called"
    return a

def scale_to_int(value,scale):
    """scale and convert to int 
    
    args:
        value (number): value to convert
        scale (TYPE): Description
        retuns 
        (int) int(value*scale)
    
    Deleted Parameters:
        scale(number): scale by this
    
    Returns:
        TYPE: Description
    """
    return math.floor(value*scale)

def calc_ew_speed(xplane_dict,mag_hdg_adr,gnd_speed_adr):
    """compute ew speed from xplane
    
    args:
        xplane_dict (TYPE): Description
        mag_hdg_adr (TYPE): Description
        gnd_speed_adr (TYPE): Description
        return (float) east west speed (kts)
    
    Deleted Parameters:
        xplane_dict(dict): xplane reception list {data_set:data_list}
        mag_hdg_adr(tupple): placement of heading (0-2pi) in dict (data_set,data_pos)
        gnd_speed_adr(tupple): placement of ground speed  
            in dict (data_set,data_pos)
    
    Returns:
        TYPE: Description
    """
    mag_hdg=xplane_dict[mag_hdg_adr[0]][mag_hdg_adr[1]]
    gnd_speed=xplane_dict[gnd_speed_adr[0]][gnd_speed_adr[1]]
    
    ew_speed = math.sin(mag_hdg*(math.pi)/180)*gnd_speed

    return ew_speed

def calc_ns_speed(xplane_dict,mag_hdg_adr,gnd_speed_adr):
    """compute ns speed from xplane
    
    args:
        xplane_dict (TYPE): Description
        mag_hdg_adr (TYPE): Description
        gnd_speed_adr (TYPE): Description
        return (float) north-south speed(kts)
    
    Deleted Parameters:
        xplane_dict(dict): xplane reception list {data_set:data_list}
        mag_hdg_adr(tupple): placement of heading (0-2pi) in dict (data_set,data_pos)
        gnd_speed_adr(tupple): placement of ground speed  
            in dict (data_set,data_pos)
    
    Returns:
        TYPE: Description
    """
    mag_hdg=xplane_dict[mag_hdg_adr[0]][mag_hdg_adr[1]]
    gnd_speed=xplane_dict[gnd_speed_adr[0]][gnd_speed_adr[1]]

    ns_speed = math.cos(mag_hdg*(math.pi)/180)*gnd_speed

    return ns_speed

def bnr_decode(data,msb,scale,resolution=None):
    """decode ARINC 429
    
    Expected bnr frame:
        +----+-------+----------------------------------------------------------+------+
        | 32 | 31|30 | 29|28|27|26|25|24|23|22|21|20|19|18|17|16|15|14|13|12|11 | 10|9 |
        +----+-------+----------------------------------------------------------+------+
        | P  | SSM   | MSB              DATA                                LSB | SDI  |
        +----+-------+----------------------------------------------------------+------+
    
    Args:
        data (int): arinc429 data  (see above)
        msb (int): is number of bits used (check Marinvent GJMM_AID_ICD.xls)
        scale (float): a scale mutiplyer (check Marinvent GJMM_AID_ICD.xls)
        resolution (float, optional): if defined ronds the value for lower bound using int
    
    Returns:
        float: decoded float value
    """
    #TODO test code
    data_bin=bin(data)[2:].zfill(24)
    data_bin=data_bin[4:] # remove P and SSN
    sign=data_bin[0]
    data_bin=data_bin[1:] # remove sign
    if sign == '1':
        value=(~int(data_bin[:msb-1],2) & (2**(msb-1)-1)) +1
        value=-value/(2.0**msb-1)
    else:
        value=int(data_bin[:msb-1],2)/(2.0**(msb)-1)
    value=value*scale
    if resolution:
        value=int(value/resolution)*resolution
    return value

def bcd_decode(data,len_list,scale_list):
    """decode ARINC 429 BCD
    typical BCD frame
    +----+-------+----------+-------------+-------------+-------------+-------------+------+
    | 32 | 31|30 | 29|28|27 | 26|25|24|23 | 22|21|20|19 | 18|17|16|15 | 14|13|12|11 | 10|9 |
    +----+-------+----------+-------------+-------------+-------------+-------------+------+
    | P  | SSM   | DIGIT1   | DIGIT2      | DIGIT3      | DIGIT4      | DIGIT5      | SDI  |
    +----+-------+----------+-------------+-------------+-------------+-------------+------+
    
    Args:
        data (int): arinc429 bdc data
        len_list (list): list en lenghts (for slicing )
        scale_list ([float]): list of scler for each digit starting for MSB
    
    Returns:
        float: decoded float value
    
    Deleted Parameters:
        digit_list ([int]): list of lengths (in bits) for each digit starting for MSB
    """
    #TODO: handle other cases of SSM (10|01)
    data_bin=bin(data)[2:].zfill(24)
    data_bin=data_bin[1:] # remove P
    ssm = data_bin[:2]
    data_bin=data_bin[2:] #remove SSM 
    chunks=[]
    value = 0.0
    for l,s in zip(len_list,scale_list):
        chunk=int(data_bin[:l],2)*s
        data_bin=data_bin[l:]
        value=value+chunk
    
    return value    
    #### UBLOX ####

def parse_GGA(str_data):
    """GGA parser
    
    Args:
        str_data (str): GGA list str
    Returns:
        TYPE: list (ENMEA_sentence,utc time in sec, lat,lon,altitude)

    example
    ------
    $GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47

Where:
     GGA          Global Positioning System Fix Data
     123519       Fix taken at 12:35:19 UTC
     4807.038,N   Latitude 48 deg 07.038' N
     01131.000,E  Longitude 11 deg 31.000' E
     1            Fix quality: 0 = invalid
                               1 = GPS fix (SPS)
                               2 = DGPS fix
                               3 = PPS fix
                   4 = Real Time Kinematic
                   5 = Float RTK
                               6 = estimated (dead reckoning) (2.3 feature)
                   7 = Manual input mode
                   8 = Simulation mode
     08           Number of satellites being tracked
     0.9          Horizontal dilution of position
     545.4,M      Altitude, Meters, above mean sea level
     46.9,M       Height of geoid (mean sea level) above WGS84
                      ellipsoid
     (empty field) time in seconds since last DGPS update
     (empty field) DGPS station ID number
     *47          the checksum data, always begins with *
    """
    data=str_data.split(',')
    ts=data[1]
    utc=int(ts[0:2])*3600+int(ts[2:4])*60+int(ts[4:6])

    if data[2] and data[2] : 
        lat=int(float(data[2])/100)+((float(data[2]))%100)/60.0 #check this
        if data[3]=='S':lat=-lat
    else :
        lat=0
    if data[4] and data[5]:
        lon=int(float(data[4])/100)+((float(data[4]))%100)/60.0 #check this
        if data[5]=='W':lon=-lon
    else: 
        lon = 0 

    if data[9]:
        alt_ft=float(data[9])*3.28084 # x3.28084 ==> m to ft
    else :
        alt_ft=0
    return (utc,lat,lon,alt_ft)  

def parse_VTG(str_data):
    """VTG - Velocity made good parser
    
    Args:
        str_data (TYPE): Description
    
    Returns:
        TYPE: 'VTG',mag_track,kts_speed,ew_speed,ns_speed)
    """

    data=str_data.split(',')
    if data[1]:
        track=float(data[1])
    else:
        track=0
    if data[5]:
        kts_speed = float(data[5])
    else:
        kts_speed=0
    if data[1] and data[5]:
        ew_speed=math.cos(math.radians(track))*kts_speed
        ns_speed=math.sin(math.radians(track))*kts_speed
    else :
        ew_speed=0
        ns_speed=0
    return (track,kts_speed,ew_speed,ns_speed)


def task_log(file_prefix):
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.connect("ipc://my-endpoint")
    socket.setsockopt(zmq.SUBSCRIBE, "")
    filename=file_prefix+"_%i.txt" % int(time.time())
    while True:
	f=open(filename,'a')
        data=socket.recv()
        now_ms=int(time.time()*1000)
        f.write(str(now_ms)+"|"+data+"\n")
        f.close()
if __name__ == '__main__':
    sys.exit(main())
