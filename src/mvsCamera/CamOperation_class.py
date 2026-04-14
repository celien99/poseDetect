# -- coding: utf-8 --
import ctypes
import inspect
import sys
import threading
import time
import tkinter.messagebox
from ctypes import *
from pathlib import Path

import cv2
import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from mvsCamera.MvCameraControl_class import *
    from mvsCamera.pixel_utils import is_color_pixel_type, is_mono_pixel_type
else:
    from .MvCameraControl_class import *
    from .pixel_utils import is_color_pixel_type, is_mono_pixel_type
 
def Async_raise(tid, exctype):
    tid = ctypes.c_long(tid)
    if not inspect.isclass(exctype):
        exctype = type(exctype)
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))
    if res == 0:
        raise ValueError("invalid thread id")
    elif res != 1:
        ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
        raise SystemError("PyThreadState_SetAsyncExc failed")
 
def Stop_thread(thread):
    Async_raise(thread.ident, SystemExit)
 
class CameraOperation():
 
    def __init__(self,obj_cam,st_device_list,n_connect_num=0,b_open_device=False,b_start_grabbing = False,h_thread_handle=None,\
                b_thread_closed=False,st_frame_info=None,b_exit=False,frame_rate=0,exposure_time=0,gain=0):
 
        self.obj_cam = obj_cam
        self.st_device_list = st_device_list
        self.n_connect_num = n_connect_num
        self.b_open_device = b_open_device
        self.b_start_grabbing = b_start_grabbing 
        self.b_thread_closed = b_thread_closed
        self.st_frame_info = st_frame_info
        self.b_exit = b_exit
        self.h_thread_handle = h_thread_handle
        self.frame_rate = frame_rate
        self.exposure_time = exposure_time
        self.gain = gain
 
    def To_hex_str(self,num):
        chaDic = {10: 'a', 11: 'b', 12: 'c', 13: 'd', 14: 'e', 15: 'f'}
        hexStr = ""
        if num < 0:
            num = num + 2**32
        while num >= 16:
            digit = num % 16
            hexStr = chaDic.get(digit, str(digit)) + hexStr
            num //= 16
        hexStr = chaDic.get(num, str(num)) + hexStr   
        return hexStr
 
    def Open_device(self):
        if False == self.b_open_device:
            # ch:选择设备并创建句柄 | en:Select device and create handle
            nConnectionNum = int(self.n_connect_num)
            stDeviceList = cast(self.st_device_list.pDeviceInfo[int(nConnectionNum)], POINTER(MV_CC_DEVICE_INFO)).contents
            self.obj_cam = MvCamera()
            ret = self.obj_cam.MV_CC_CreateHandle(stDeviceList)
            if ret != 0:
                self.obj_cam.MV_CC_DestroyHandle()
                tkinter.messagebox.showerror('show error','create handle fail! ret = '+ self.To_hex_str(ret))
                return ret
 
            ret = self.obj_cam.MV_CC_OpenDevice(MV_ACCESS_Exclusive, 0)
            if ret != 0:
                tkinter.messagebox.showerror('show error','open device fail! ret = '+ self.To_hex_str(ret))
                return ret
            print ("open device successfully!")
            self.b_open_device = True
            self.b_thread_closed = False
 
            # ch:探测网络最佳包大小(只对GigE相机有效) | en:Detection network optimal package size(It only works for the GigE camera)
            if stDeviceList.nTLayerType == MV_GIGE_DEVICE:
                nPacketSize = self.obj_cam.MV_CC_GetOptimalPacketSize()
                if int(nPacketSize) > 0:
                    ret = self.obj_cam.MV_CC_SetIntValue("GevSCPSPacketSize",nPacketSize)
                    if ret != 0:
                        print ("warning: set packet size fail! ret[0x%x]" % ret)
                else:
                    print ("warning: set packet size fail! ret[0x%x]" % nPacketSize)
 
            stBool = c_bool(False)
            ret =self.obj_cam.MV_CC_GetBoolValue("AcquisitionFrameRateEnable", stBool)
            if ret != 0:
                print ("get acquisition frame rate enable fail! ret[0x%x]" % ret)
 
            # ch:设置触发模式为off | en:Set trigger mode as off
            ret = self.obj_cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_OFF)
            if ret != 0:
                print ("set trigger mode fail! ret[0x%x]" % ret)
            return 0
 
    def Start_grabbing(self):
        if False == self.b_start_grabbing and True == self.b_open_device:
            self.b_exit = False
            ret = self.obj_cam.MV_CC_StartGrabbing()
            if ret != 0:
                tkinter.messagebox.showerror('show error', 'start grabbing fail! ret = '+ self.To_hex_str(ret))
                return
            self.b_start_grabbing = True
            print("start grabbing successfully!")
            try:
                self.h_thread_handle = threading.Thread(target=CameraOperation.Work_thread, args=(self,))
                self.h_thread_handle.start()
                self.b_thread_closed = True
            except:
                tkinter.messagebox.showerror('show error','error: unable to start thread')
                False == self.b_start_grabbing
 
    def Stop_grabbing(self):
        if True == self.b_start_grabbing and self.b_open_device == True:
            #退出线程
            if True == self.b_thread_closed:
                Stop_thread(self.h_thread_handle)
                self.b_thread_closed = False
            ret = self.obj_cam.MV_CC_StopGrabbing()
            if ret != 0:
                tkinter.messagebox.showerror('show error','stop grabbing fail! ret = '+self.To_hex_str(ret))
                return
            print ("stop grabbing successfully!")
            self.b_start_grabbing = False
            self.b_exit  = True      
 
    def Close_device(self):
        if True == self.b_open_device:
            #退出线程
            if True == self.b_thread_closed:
                Stop_thread(self.h_thread_handle)
                self.b_thread_closed = False
            ret = self.obj_cam.MV_CC_CloseDevice()
            if ret != 0:
                tkinter.messagebox.showerror('show error','close deivce fail! ret = '+self.To_hex_str(ret))
                return
                
        # ch:销毁句柄 | Destroy handle
        self.obj_cam.MV_CC_DestroyHandle()
        self.b_open_device = False
        self.b_start_grabbing = False
        self.b_exit  = True
        print ("close device successfully!")
 
    def Set_trigger_mode(self,strMode):
        if True == self.b_open_device:
            if "continuous" == strMode: 
                ret = self.obj_cam.MV_CC_SetEnumValue("TriggerMode",0)
                if ret != 0:
                    tkinter.messagebox.showerror('show error','set triggermode fail! ret = '+self.To_hex_str(ret))
            if "triggermode" == strMode:
                ret = self.obj_cam.MV_CC_SetEnumValue("TriggerMode",1)
                if ret != 0:
                    tkinter.messagebox.showerror('show error','set triggermode fail! ret = '+self.To_hex_str(ret))
                ret = self.obj_cam.MV_CC_SetEnumValue("TriggerSource",7)
                if ret != 0:
                    tkinter.messagebox.showerror('show error','set triggersource fail! ret = '+self.To_hex_str(ret))
 
    def Trigger_once(self,nCommand):
        if True == self.b_open_device:
            if 1 == nCommand: 
                ret = self.obj_cam.MV_CC_SetCommandValue("TriggerSoftware")
                if ret != 0:
                    tkinter.messagebox.showerror('show error','set triggersoftware fail! ret = '+self.To_hex_str(ret))
 
    def Get_parameter(self):
        if True == self.b_open_device:
            stFloatParam_FrameRate =  MVCC_FLOATVALUE()
            memset(byref(stFloatParam_FrameRate), 0, sizeof(MVCC_FLOATVALUE))
            stFloatParam_exposureTime = MVCC_FLOATVALUE()
            memset(byref(stFloatParam_exposureTime), 0, sizeof(MVCC_FLOATVALUE))
            stFloatParam_gain = MVCC_FLOATVALUE()
            memset(byref(stFloatParam_gain), 0, sizeof(MVCC_FLOATVALUE))
            ret = self.obj_cam.MV_CC_GetFloatValue("AcquisitionFrameRate", stFloatParam_FrameRate)
            if ret != 0:
                tkinter.messagebox.showerror('show error','get acquistion frame rate fail! ret = '+self.To_hex_str(ret))
            self.frame_rate = stFloatParam_FrameRate.fCurValue
            ret = self.obj_cam.MV_CC_GetFloatValue("ExposureTime", stFloatParam_exposureTime)
            if ret != 0:
                tkinter.messagebox.showerror('show error','get exposure time fail! ret = '+self.To_hex_str(ret))
            self.exposure_time = stFloatParam_exposureTime.fCurValue
            ret = self.obj_cam.MV_CC_GetFloatValue("Gain", stFloatParam_gain)
            if ret != 0:
                tkinter.messagebox.showerror('show error','get gain fail! ret = '+self.To_hex_str(ret))
            self.gain = stFloatParam_gain.fCurValue
            tkinter.messagebox.showinfo('show info','get parameter success!')
 
    def Set_parameter(self,frameRate,exposureTime,gain):
        if '' == frameRate or '' == exposureTime or '' == gain:
            tkinter.messagebox.showinfo('show info','please type in the text box !')
            return
        if True == self.b_open_device:
            ret = self.obj_cam.MV_CC_SetFloatValue("ExposureTime",float(exposureTime))
            if ret != 0:
                tkinter.messagebox.showerror('show error','set exposure time fail! ret = '+self.To_hex_str(ret))
 
            ret = self.obj_cam.MV_CC_SetFloatValue("Gain",float(gain))
            if ret != 0:
                tkinter.messagebox.showerror('show error','set gain fail! ret = '+self.To_hex_str(ret))
 
            ret = self.obj_cam.MV_CC_SetFloatValue("AcquisitionFrameRate",float(frameRate))
            if ret != 0:
                tkinter.messagebox.showerror('show error','set acquistion frame rate fail! ret = '+self.To_hex_str(ret))
 
            tkinter.messagebox.showinfo('show info','set parameter success!')
 
    def Work_thread(self):
        stOutFrame = MV_FRAME_OUT()  
        img_buff = None
        buf_cache = None
        numArray = None
        while True:
            ret = self.obj_cam.MV_CC_GetImageBuffer(stOutFrame, 1000)
            if 0 == ret:
                if None == buf_cache:
                    buf_cache = (c_ubyte * stOutFrame.stFrameInfo.nFrameLen)()
                #获取到图像的时间开始节点获取到图像的时间开始节点
                self.st_frame_info = stOutFrame.stFrameInfo
                memmove(buf_cache, stOutFrame.pBufAddr, self.st_frame_info.nFrameLen)
                print ("get one frame: Width[%d], Height[%d], nFrameNum[%d]"  % (self.st_frame_info.nWidth, self.st_frame_info.nHeight, self.st_frame_info.nFrameNum))
                image_buffer_size = self.st_frame_info.nWidth * self.st_frame_info.nHeight * 3 + 2048
                if img_buff is None:
                    img_buff = (c_ubyte * image_buffer_size)()
            else:
                print("no data, nret = "+self.To_hex_str(ret))
                continue
 
            #转换像素结构体赋值
            stConvertParam = MV_CC_PIXEL_CONVERT_PARAM()
            memset(byref(stConvertParam), 0, sizeof(stConvertParam))
            stConvertParam.nWidth = self.st_frame_info.nWidth
            stConvertParam.nHeight = self.st_frame_info.nHeight
            stConvertParam.pSrcData = cast(buf_cache, POINTER(c_ubyte))
            stConvertParam.nSrcDataLen = self.st_frame_info.nFrameLen
            stConvertParam.enSrcPixelType = self.st_frame_info.enPixelType 
 
            # RGB8直接显示
            if PixelType_Gvsp_RGB8_Packed == self.st_frame_info.enPixelType :
                numArray = CameraOperation.Color_numpy(self,buf_cache,self.st_frame_info.nWidth,self.st_frame_info.nHeight)
 
            # Mono8直接显示
            elif PixelType_Gvsp_Mono8 == self.st_frame_info.enPixelType :
                numArray = CameraOperation.Mono_numpy(self,buf_cache,self.st_frame_info.nWidth,self.st_frame_info.nHeight)
 
            # 如果是彩色且非RGB则转为RGB后显示
            elif is_color_pixel_type(self.st_frame_info.enPixelType):
                nConvertSize = self.st_frame_info.nWidth * self.st_frame_info.nHeight * 3
                stConvertParam.enDstPixelType = PixelType_Gvsp_RGB8_Packed
                stConvertParam.pDstBuffer = (c_ubyte * nConvertSize)()
                stConvertParam.nDstBufferSize = nConvertSize
                time_start=time.time()
                ret = self.obj_cam.MV_CC_ConvertPixelType(stConvertParam)
                time_end=time.time()
                print('MV_CC_ConvertPixelType to RGB:',time_end - time_start) 
                if ret != 0:
                    print('show error','convert pixel fail! ret = '+self.To_hex_str(ret))
                    continue
                memmove(img_buff, stConvertParam.pDstBuffer, nConvertSize)
                numArray = CameraOperation.Color_numpy(self,img_buff,self.st_frame_info.nWidth,self.st_frame_info.nHeight)
                
            # 如果是黑白且非Mono8则转为Mono8后显示
            elif is_mono_pixel_type(self.st_frame_info.enPixelType):
                nConvertSize = self.st_frame_info.nWidth * self.st_frame_info.nHeight
                stConvertParam.enDstPixelType = PixelType_Gvsp_Mono8
                stConvertParam.pDstBuffer = (c_ubyte * nConvertSize)()
                stConvertParam.nDstBufferSize = nConvertSize
                time_start=time.time()
                ret = self.obj_cam.MV_CC_ConvertPixelType(stConvertParam)
                time_end=time.time()
                print('MV_CC_ConvertPixelType to Mono8:',time_end - time_start) 
                if ret != 0:
                    print('show error','convert pixel fail! ret = '+self.To_hex_str(ret))
                    continue
                memmove(img_buff, stConvertParam.pDstBuffer, nConvertSize)
                numArray = CameraOperation.Mono_numpy(self,img_buff,self.st_frame_info.nWidth,self.st_frame_info.nHeight)
            numArray = cv2.cvtColor(numArray, cv2.COLOR_BGR2RGB)
            cv2.imshow('view', numArray)
 
            if cv2.waitKey(1) & 0xFF == ord('q') :
                break
 
            self.obj_cam.MV_CC_FreeImageBuffer(stOutFrame)
            if self.b_exit == True:
                if img_buff is not None:
                    del img_buff
                if buf_cache is not None:
                    del buf_cache
                break
 
    def Mono_numpy(self,data,nWidth,nHeight):
        data_ = np.frombuffer(data, count=int(nWidth * nHeight), dtype=np.uint8, offset=0)
        data_mono_arr = data_.reshape(nHeight, nWidth)
        numArray = np.zeros([nHeight, nWidth, 1],"uint8")
        numArray[:, :, 0] = data_mono_arr
        return numArray
 
    def Color_numpy(self,data,nWidth,nHeight):
        data_ = np.frombuffer(data, count=int(nWidth*nHeight*3), dtype=np.uint8, offset=0)
        data_r = data_[0:nWidth*nHeight*3:3]
        data_g = data_[1:nWidth*nHeight*3:3]
        data_b = data_[2:nWidth*nHeight*3:3]
 
        data_r_arr = data_r.reshape(nHeight, nWidth)
        data_g_arr = data_g.reshape(nHeight, nWidth)
        data_b_arr = data_b.reshape(nHeight, nWidth)
        numArray = np.zeros([nHeight, nWidth, 3],"uint8")
 
        numArray[:, :, 0] = data_r_arr
        numArray[:, :, 1] = data_g_arr
        numArray[:, :, 2] = data_b_arr
        return numArray
