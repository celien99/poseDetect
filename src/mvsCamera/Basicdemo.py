import sys
from pathlib import Path
import numpy as np
from os import getcwd
import cv2
from ctypes import *

try:
    import msvcrt
except ImportError:
    msvcrt = None

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from mvsCamera.MvCameraControl_class import *
    from mvsCamera.pixel_utils import char_array_to_string, copy_frame_buffer, frame_data_size, int_to_ip
else:
    from .MvCameraControl_class import *
    from .pixel_utils import char_array_to_string, copy_frame_buffer, frame_data_size, int_to_ip


WINFUNCTYPE = globals().get("WINFUNCTYPE", CFUNCTYPE)
 
 
# 枚举设备
def enum_devices(device = 0 , device_way = False):
    """
    device = 0  枚举网口、USB口、未知设备、cameralink 设备
    device = 1 枚举GenTL设备
    """
    if device_way:
        raise NotImplementedError("GenTL enumeration is not implemented in this demo")
    if device != 0:
        raise NotImplementedError("Only default GigE/USB enumeration is implemented")

    tlayerType = MV_GIGE_DEVICE | MV_USB_DEVICE | MV_UNKNOW_DEVICE | MV_1394_DEVICE | MV_CAMERALINK_DEVICE
    deviceList = MV_CC_DEVICE_INFO_LIST()
    ret = MvCamera.MV_CC_EnumDevices(tlayerType, deviceList)
    if ret != 0:
        print("enum devices fail! ret[0x%x]" % ret)
        sys.exit()
    if deviceList.nDeviceNum == 0:
        print("find no device!")
        sys.exit()
    print("Find %d devices!" % deviceList.nDeviceNum)
    return deviceList
 
# 判断不同类型设备
def identify_different_devices(deviceList):
    # 判断不同类型设备，并输出相关信息
    for i in range(0, deviceList.nDeviceNum):
        mvcc_dev_info = cast(deviceList.pDeviceInfo[i], POINTER(MV_CC_DEVICE_INFO)).contents
        # 判断是否为网口相机
        if mvcc_dev_info.nTLayerType == MV_GIGE_DEVICE:
            print ("\n网口设备序号: [%d]" % i)
            gige_info = mvcc_dev_info.SpecialInfo.stGigEInfo
            print ("当前设备型号名: %s" % char_array_to_string(gige_info.chModelName))
            print ("当前 ip 地址: %s" % int_to_ip(gige_info.nCurrentIp))
            print ("当前子网掩码 : %s" % int_to_ip(gige_info.nCurrentSubNetMask))
            print("当前网关 : %s" % int_to_ip(gige_info.nDefultGateWay))
            print("当前连接的网口 IP 地址 : %s" % int_to_ip(gige_info.nNetExport))
            print("制造商名称 : %s" % char_array_to_string(gige_info.chManufacturerName))
            print("设备当前使用固件版本 : %s" % char_array_to_string(gige_info.chDeviceVersion))
            print("设备制造商的具体信息 : %s" % char_array_to_string(gige_info.chManufacturerSpecificInfo))
            print("设备序列号 : %s" % char_array_to_string(gige_info.chSerialNumber))
            print("用户自定义名称 : %s" % char_array_to_string(gige_info.chUserDefinedName))
 
        # 判断是否为 USB 接口相机
        elif mvcc_dev_info.nTLayerType == MV_USB_DEVICE:
            print ("\nU3V 设备序号e: [%d]" % i)
            usb_info = mvcc_dev_info.SpecialInfo.stUsb3VInfo
            print ("当前设备型号名 : %s" % char_array_to_string(usb_info.chModelName))
            print ("当前设备序列号 : %s" % char_array_to_string(usb_info.chSerialNumber))
            print("制造商名称 : %s" % char_array_to_string(usb_info.chVendorName))
            print("设备当前使用固件版本 : %s" % char_array_to_string(usb_info.chDeviceVersion))
            print("设备序列号 : %s" % char_array_to_string(usb_info.chSerialNumber))
            print("用户自定义名称 : %s" % char_array_to_string(usb_info.chUserDefinedName))
            print("设备GUID号 : %s" % char_array_to_string(usb_info.chDeviceGUID))
            print("设备的家族名称 : %s" % char_array_to_string(usb_info.chFamilyName))
 
        # 判断是否为 1394-a/b 设备
        elif mvcc_dev_info.nTLayerType == MV_1394_DEVICE:
            print("\n1394-a/b device: [%d]" % i)
 
        # 判断是否为 cameralink 设备
        elif mvcc_dev_info.nTLayerType == MV_CAMERALINK_DEVICE:
            print("\ncameralink device: [%d]" % i)
            cam_link_info = mvcc_dev_info.SpecialInfo.stCamLInfo
            print("当前设备型号名 : %s" % char_array_to_string(cam_link_info.chModelName))
            print("当前设备序列号 : %s" % char_array_to_string(cam_link_info.chSerialNumber))
            print("制造商名称 : %s" % char_array_to_string(cam_link_info.chVendorName))
            print("设备当前使用固件版本 : %s" % char_array_to_string(cam_link_info.chDeviceVersion))
 
# 输入需要连接的相机的序号
def input_num_camera(deviceList):
    nConnectionNum = input("please input the number of the device to connect:")
    if int(nConnectionNum) >= deviceList.nDeviceNum:
        print("intput error!")
        sys.exit()
    return nConnectionNum
 
# 创建相机实例并创建句柄,(设置日志路径)
def creat_camera(deviceList , nConnectionNum ,log = True , log_path = getcwd()):
    """
    :param deviceList:        设备列表
    :param nConnectionNum:    需要连接的设备序号
    :param log:               是否创建日志
    :param log_path:          日志保存路径
    :return:                  相机实例和设备列表
    """
    # 创建相机实例
    cam = MvCamera()
    # 选择设备并创建句柄
    stDeviceList = cast(deviceList.pDeviceInfo[int(nConnectionNum)], POINTER(MV_CC_DEVICE_INFO)).contents
    if log == True:
        ret = cam.MV_CC_SetSDKLogPath(log_path)
        print(log_path)
        if ret != 0:
            print("set Log path  fail! ret[0x%x]" % ret)
            sys.exit()
        # 创建句柄,生成日志
        ret = cam.MV_CC_CreateHandle(stDeviceList)
        if ret != 0:
            print("create handle fail! ret[0x%x]" % ret)
            sys.exit()
    elif log == False:
        # 创建句柄,不生成日志
        ret = cam.MV_CC_CreateHandleWithoutLog(stDeviceList)
        if ret != 0:
            print("create handle fail! ret[0x%x]" % ret)
            sys.exit()
    return cam , stDeviceList
 
# 打开设备
def open_device(cam):
    # ch:打开设备 | en:Open device
    ret = cam.MV_CC_OpenDevice(MV_ACCESS_Exclusive, 0)
    if ret != 0:
        print("open device fail! ret[0x%x]" % ret)
        sys.exit()
 
# 获取各种类型节点参数
def get_Value(cam , param_type = "int_value" , node_name = "PayloadSize"):
    """
    :param cam:            相机实例
    :param_type:           获取节点值得类型
    :param node_name:      节点名 可选 int 、float 、enum 、bool 、string 型节点
    :return:               节点值
    """
    if param_type == "int_value":
        stParam = MVCC_INTVALUE_EX()
        memset(byref(stParam), 0, sizeof(MVCC_INTVALUE_EX))
        ret = cam.MV_CC_GetIntValueEx(node_name, stParam)
        if ret != 0:
            print("获取 int 型数据 %s 失败 ! 报错码 ret[0x%x]" % (node_name , ret))
            sys.exit()
        int_value = stParam.nCurValue
        return int_value
 
    elif param_type == "float_value":
        stFloatValue = MVCC_FLOATVALUE()
        memset(byref(stFloatValue), 0, sizeof(MVCC_FLOATVALUE))
        ret = cam.MV_CC_GetFloatValue( node_name , stFloatValue)
        if ret != 0:
            print("获取 float 型数据 %s 失败 ! 报错码 ret[0x%x]" % (node_name , ret))
            sys.exit()
        float_value = stFloatValue.fCurValue
        return float_value
 
    elif param_type == "enum_value":
        stEnumValue = MVCC_ENUMVALUE()
        memset(byref(stEnumValue), 0, sizeof(MVCC_ENUMVALUE))
        ret = cam.MV_CC_GetEnumValue(node_name, stEnumValue)
        if ret != 0:
            print("获取 enum 型数据 %s 失败 ! 报错码 ret[0x%x]" % (node_name , ret))
            sys.exit()
        enum_value = stEnumValue.nCurValue
        return enum_value
 
    elif param_type == "bool_value":
        stBool = c_bool(False)
        ret = cam.MV_CC_GetBoolValue(node_name, stBool)
        if ret != 0:
            print("获取 bool 型数据 %s 失败 ! 报错码 ret[0x%x]" % (node_name , ret))
            sys.exit()
        return stBool.value
 
    elif param_type == "string_value":
        stStringValue =  MVCC_STRINGVALUE()
        memset(byref(stStringValue), 0, sizeof( MVCC_STRINGVALUE))
        ret = cam.MV_CC_GetStringValue(node_name, stStringValue)
        if ret != 0:
            print("获取 string 型数据 %s 失败 ! 报错码 ret[0x%x]" % (node_name , ret))
            sys.exit()
        string_value = stStringValue.chCurValue
        return string_value
 
# 设置各种类型节点参数
def set_Value(cam , param_type = "int_value" , node_name = "PayloadSize" , node_value = None):
    """
    :param cam:               相机实例
    :param param_type:        需要设置的节点值得类型
        int:
        float:
        enum:     参考于客户端中该选项的 Enum Entry Value 值即可
        bool:     对应 0 为关，1 为开
        string:   输入值为数字或者英文字符，不能为汉字
    :param node_name:         需要设置的节点名
    :param node_value:        设置给节点的值
    :return:
    """
    if param_type == "int_value":
        stParam = int(node_value)
        ret = cam.MV_CC_SetIntValueEx(node_name, stParam)
        if ret != 0:
            print("设置 int 型数据节点 %s 失败 ! 报错码 ret[0x%x]" % (node_name , ret))
            sys.exit()
        print("设置 int 型数据节点 %s 成功 ！设置值为 %s !"%(node_name , node_value))
 
    elif param_type == "float_value":
        stFloatValue = float(node_value)
        ret = cam.MV_CC_SetFloatValue( node_name , stFloatValue)
        if ret != 0:
            print("设置 float 型数据节点 %s 失败 ! 报错码 ret[0x%x]" % (node_name , ret))
            sys.exit()
        print("设置 float 型数据节点 %s 成功 ！设置值为 %s !" % (node_name, node_value))
 
    elif param_type == "enum_value":
        stEnumValue = node_value
        ret = cam.MV_CC_SetEnumValue(node_name, stEnumValue)
        if ret != 0:
            print("设置 enum 型数据节点 %s 失败 ! 报错码 ret[0x%x]" % (node_name , ret))
            sys.exit()
        print("设置 enum 型数据节点 %s 成功 ！设置值为 %s !" % (node_name, node_value))
 
    elif param_type == "bool_value":
        ret = cam.MV_CC_SetBoolValue(node_name, node_value)
        if ret != 0:
            print("设置 bool 型数据节点 %s 失败 ！ 报错码 ret[0x%x]" %(node_name,ret))
            sys.exit()
        print("设置 bool 型数据节点 %s 成功 ！设置值为 %s !" % (node_name, node_value))
 
    elif param_type == "string_value":
        stStringValue = str(node_value)
        ret = cam.MV_CC_SetStringValue(node_name, stStringValue)
        if ret != 0:
            print("设置 string 型数据节点 %s 失败 ! 报错码 ret[0x%x]" % (node_name , ret))
            sys.exit()
        print("设置 string 型数据节点 %s 成功 ！设置值为 %s !" % (node_name, node_value))
 
# 判断相机是否处于连接状态(返回值如何获取)=================================
def decide_divice_on_line(cam):
    value = cam.MV_CC_IsDeviceConnected()
    if value == True:
        print("该设备在线 ！")
    else:
        print("该设备已掉线 ！", value)
 
# 设置 SDK 内部图像缓存节点个数
def set_image_Node_num(cam , Num = 1):
    ret = cam.MV_CC_SetImageNodeNum(nNum = Num)
    if ret != 0:
        print("设置 SDK 内部图像缓存节点个数失败 ,报错码 ret[0x%x]" % ret)
    else:
        print("设置 SDK 内部图像缓存节点个数为 %d  ，设置成功!" % Num)
 
# 设置取流策略
def set_grab_strategy(cam , grabstrategy = 0 , outputqueuesize = 1):
    """
    • OneByOne: 从旧到新一帧一帧的从输出缓存列表中获取图像，打开设备后默认为该策略
    • LatestImagesOnly: 仅从输出缓存列表中获取最新的一帧图像，同时清空输出缓存列表
    • LatestImages: 从输出缓存列表中获取最新的OutputQueueSize帧图像，其中OutputQueueSize范围为1 - ImageNodeNum，可用MV_CC_SetOutputQueueSize()接口设置，ImageNodeNum默认为1，可用MV_CC_SetImageNodeNum()接口设置OutputQueueSize设置成1等同于LatestImagesOnly策略，OutputQueueSize设置成ImageNodeNum等同于OneByOne策略
    • UpcomingImage: 在调用取流接口时忽略输出缓存列表中所有图像，并等待设备即将生成的一帧图像。该策略只支持GigE设备，不支持U3V设备
    """
    if grabstrategy != 2:
        ret = cam.MV_CC_SetGrabStrategy(enGrabStrategy = grabstrategy)
        if ret != 0:
            print("设置取流策略失败 ,报错码 ret[0x%x]" % ret)
        else:
            print("设置 取流策略为 %d  ，设置成功!" % grabstrategy)
    else:
        ret = cam.MV_CC_SetGrabStrategy(enGrabStrategy=grabstrategy)
        if ret != 0:
            print("设置取流策略失败 ,报错码 ret[0x%x]" % ret)
        else:
            print("设置 取流策略为 %d  ，设置成功!" % grabstrategy)
 
        ret = cam.MV_CC_SetOutputQueueSize(nOutputQueueSize = outputqueuesize)
        if ret != 0:
            print("设置使出缓存个数失败 ,报错码 ret[0x%x]" % ret)
        else:
            print("设置 输出缓存个数为 %d  ，设置成功!" % outputqueuesize)
 
# 显示图像
def image_show(image , name):
    image = cv2.resize(image, (600, 400), interpolation=cv2.INTER_AREA)
    name = str(name)
    cv2.imshow(name, image)
    cv2.waitKey(1)
 
# 需要显示的图像数据转换
def image_control(data , stFrameInfo):
    if stFrameInfo.enPixelType == PixelType_Gvsp_Mono8:
        image = data.reshape((stFrameInfo.nHeight, stFrameInfo.nWidth))
        image_show(image=image , name = stFrameInfo.nHeight)
    elif stFrameInfo.enPixelType == PixelType_Gvsp_BayerGB8:
        data = data.reshape(stFrameInfo.nHeight, stFrameInfo.nWidth, -1)
        image = cv2.cvtColor(data, cv2.COLOR_BAYER_GB2RGB)
        image_show(image=image, name = stFrameInfo.nHeight)
    elif stFrameInfo.enPixelType == PixelType_Gvsp_RGB8_Packed:
        data = data.reshape(stFrameInfo.nHeight, stFrameInfo.nWidth, -1)
        image = cv2.cvtColor(data, cv2.COLOR_RGB2BGR)
        image_show(image=image, name = stFrameInfo.nHeight)
    elif stFrameInfo.enPixelType == PixelType_Gvsp_YUV422_Packed:
        data = data.reshape(stFrameInfo.nHeight, stFrameInfo.nWidth, -1)
        image = cv2.cvtColor(data, cv2.COLOR_YUV2BGR_Y422)
        image_show(image = image, name = stFrameInfo.nHeight)
 
# 主动图像采集
def access_get_image(cam , active_way = "getImagebuffer"):
    """
    :param cam:     相机实例
    :active_way:主动取流方式的不同方法 分别是（getImagebuffer）（getoneframetimeout）
    :return:
    """
    if active_way == "getImagebuffer":
        stOutFrame = MV_FRAME_OUT()
        memset(byref(stOutFrame), 0, sizeof(stOutFrame))
        while True:
            ret = cam.MV_CC_GetImageBuffer(stOutFrame, 1000)
            if None != stOutFrame.pBufAddr and 0 == ret:
                print("get one frame: Width[%d], Height[%d], nFrameNum[%d]" % (stOutFrame.stFrameInfo.nWidth, stOutFrame.stFrameInfo.nHeight, stOutFrame.stFrameInfo.nFrameNum))
                try:
                    data = copy_frame_buffer(stOutFrame.pBufAddr, frame_data_size(stOutFrame.stFrameInfo))
                except ValueError as exc:
                    print(exc)
                else:
                    image_control(data=data, stFrameInfo=stOutFrame.stFrameInfo)
            else:
                print("no data[0x%x]" % ret)
            cam.MV_CC_FreeImageBuffer(stOutFrame)
 
    elif active_way == "getoneframetimeout":
        stParam = MVCC_INTVALUE_EX()
        memset(byref(stParam), 0, sizeof(MVCC_INTVALUE_EX))
        ret = cam.MV_CC_GetIntValueEx("PayloadSize", stParam)
        if ret != 0:
            print("get payload size fail! ret[0x%x]" % ret)
            sys.exit()
        nDataSize = stParam.nCurValue
        pData = (c_ubyte * nDataSize)()
        stFrameInfo = MV_FRAME_OUT_INFO_EX()
        memset(byref(stFrameInfo), 0, sizeof(stFrameInfo))
        while True:
            ret = cam.MV_CC_GetOneFrameTimeout(pData, nDataSize, stFrameInfo, 1000)
            if ret == 0:
                print("get one frame: Width[%d], Height[%d], nFrameNum[%d] " % (stFrameInfo.nWidth, stFrameInfo.nHeight, stFrameInfo.nFrameNum))
                image = np.asarray(pData)
                image_control(data=image, stFrameInfo=stFrameInfo)
            else:
                print("no data[0x%x]" % ret)
 
# 回调取图采集
winfun_ctype = WINFUNCTYPE
stFrameInfo = POINTER(MV_FRAME_OUT_INFO_EX)
pData = POINTER(c_ubyte)
FrameInfoCallBack = winfun_ctype(None, pData, stFrameInfo, c_void_p)
def image_callback(pData, pFrameInfo, pUser):
    global img_buff
    img_buff = None
    stFrameInfo = cast(pFrameInfo, POINTER(MV_FRAME_OUT_INFO_EX)).contents
    if stFrameInfo:
        print ("get one frame: Width[%d], Height[%d], nFrameNum[%d]" % (stFrameInfo.nWidth, stFrameInfo.nHeight, stFrameInfo.nFrameNum))
    try:
        data = copy_frame_buffer(pData, frame_data_size(stFrameInfo))
    except ValueError as exc:
        print(exc)
        return
    image_control(data=data, stFrameInfo=stFrameInfo)
CALL_BACK_FUN = FrameInfoCallBack(image_callback)
 
# 注册回调取图
def call_back_get_image(cam):
    # ch:注册抓图回调 | en:Register image callback
    ret = cam.MV_CC_RegisterImageCallBackEx(CALL_BACK_FUN, None)
    if ret != 0:
        print("register image callback fail! ret[0x%x]" % ret)
        sys.exit()
 
# 关闭设备与销毁句柄
def close_and_destroy_device(cam , data_buf=None):
    # 停止取流
    ret = cam.MV_CC_StopGrabbing()
    if ret != 0:
        print("stop grabbing fail! ret[0x%x]" % ret)
        sys.exit()
    # 关闭设备
    ret = cam.MV_CC_CloseDevice()
    if ret != 0:
        print("close deivce fail! ret[0x%x]" % ret)
        if data_buf is not None:
            del data_buf
        sys.exit()
    # 销毁句柄
    ret = cam.MV_CC_DestroyHandle()
    if ret != 0:
        print("destroy handle fail! ret[0x%x]" % ret)
        if data_buf is not None:
            del data_buf
        sys.exit()
    if data_buf is not None:
        del data_buf
 
# 开启取流并获取数据包大小
def start_grab_and_get_data_size(cam):
    ret = cam.MV_CC_StartGrabbing()
    if ret != 0:
        print("开始取流失败! ret[0x%x]" % ret)
        sys.exit()
 
def main():
    # 枚举设备
    deviceList = enum_devices(device=0, device_way=False)
    # 判断不同类型设备
    identify_different_devices(deviceList)
    # 输入需要被连接的设备
    nConnectionNum = input_num_camera(deviceList)
    # 创建相机实例并创建句柄,(设置日志路径)
    cam, stDeviceList = creat_camera(deviceList, nConnectionNum, log=False)
    # 打开设备
    open_device(cam)
 
    stdcall = input("回调方式取流显示请输入 0    主动取流方式显示请输入 1:")
    if int(stdcall) == 0:
        # 回调方式抓取图像
        call_back_get_image(cam)
        # 开启设备取流
        start_grab_and_get_data_size(cam)
        # 当使用 回调取流时，需要在此处添加
        print ("press a key to stop grabbing.")
        if msvcrt is None:
            raise RuntimeError("msvcrt is required for callback-mode demo on Windows")
        msvcrt.getch()
        # 关闭设备与销毁句柄
        close_and_destroy_device(cam)
    elif int(stdcall) == 1:
        # 开启设备取流
        start_grab_and_get_data_size(cam)
        # 主动取流方式抓取图像
        access_get_image(cam, active_way="getImagebuffer")
        # 关闭设备与销毁句柄
        close_and_destroy_device(cam)
 
if __name__=="__main__":
    main()
