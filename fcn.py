from tensorflow import keras
from tensorflow.keras.models import  Model
from tensorflow.keras.layers import Input, MaxPooling2D,\
  AveragePooling2D,Conv2D,Conv2DTranspose,concatenate,\
  Dropout,BatchNormalization, Dense,Softmax
from tensorflow.python.keras.layers import Layer, Lambda
from tensorflow.python.keras import initializers, regularizers, constraints, activations
#LayerNormalization = keras.layers.BatchNormalization
import numpy as np
from tensorflow.keras import backend as K
from matplotlib import pyplot as plt   
from tensorflow.keras.layers import Activation
from tensorflow.keras.utils import get_custom_objects
import random
import obspy
import time
from mathFunc import findPos
import os
from tensorflow.keras.utils import plot_model
import tensorflow as tf
def defProcess():
    config = tf.ConfigProto()
    config.gpu_options.per_process_gpu_memory_fraction = 0.4
    config.gpu_options.allow_growth = True
    session =tf.Session(config=config)
    K.set_session(session)

class LayerNormalization(Layer):
    """Layer Normalization Layer.
    
    # References
        [Layer Normalization](http://arxiv.org/abs/1607.06450)
    """
    def __init__(self, eps=1e-6, **kwargs):
        super(LayerNormalization, self).__init__(**kwargs)
        self.eps = eps
    
    def build(self, input_shape):
        self.gamma = self.add_weight(name='gamma', shape=input_shape[-1:],
                                     initializer=initializers.Ones(), trainable=True)
        self.beta = self.add_weight(name='beta', shape=input_shape[-1:],
                                    initializer=initializers.Zeros(), trainable=True)
        super(LayerNormalization, self).build(input_shape)
    
    def call(self, x):
        mean = K.mean(x, axis=-1, keepdims=True)
        std = K.std(x, axis=-1, keepdims=True)
        return self.gamma * (x - mean) / (std + self.eps) + self.beta
    
    def compute_output_shape(self, input_shape):
        return input_shape

    def get_config(self):
        config = super(LayerNormalization, self).get_config()
        config.update({
            'eps': self.eps,
        })
        return config

#默认是float32位的网络
def swish(inputs):
    return (K.sigmoid(inputs) * inputs)
class Swish(Activation):
    def __init__(self, activation, **kwargs):
        super(Swish, self).__init__(activation, **kwargs)
        self.__name__ = 'swish'
get_custom_objects().update({'swish': Swish(swish)})
#传统的方式
w0 = np.ones(50)
w0[-10:] = 1.5
w0[-5:]  = 2
#w0/=w0.mean()

channelW = K.variable(w0.reshape([1,1,1,-1]))
class lossFuncSoft:
    # 当有标注的时候才计算权重
    # 这样可以保持结构的一致性
    def __init__(self,w=1):
        self.w=w
        self.__name__ = 'lossFuncSoft'
    def __call__(self,y0,yout0):
        y1 = 1-y0
        yout1 = 1-yout0
        return -K.mean((self.w*y0*K.log(yout0+1e-13)+y1*K.log(yout1+1e-13))*\
            (K.max(y0,axis=1, keepdims=True)*1+0.0)*channelW,\
            axis=-1)

class lossFuncSoftBak:
    def __init__(self,w=1):
        self.w=w
    def __call__(self,y0,yout0):
        y1 = 1-y0
        yout1 = 1-yout0
        return -K.mean(self.w*y0*K.log(yout0+1e-8)+y1*K.log(yout1+1e-8),axis=-1)

def hitRate(yin,yout,maxD=10):
    yinPos  = K.argmax(yin ,axis=1)
    youtPos = K.argmax(yout,axis=1)
    d       = K.abs(yinPos - youtPos)
    count   = K.sum(K.sign(d+0.1))
    hitCount= K.sum(K.sign(-d+maxD))
    return hitCount/count

def rateNp(yinPos,youtPos,yinMax,youtMax,maxD=0.03,K=np,minP=0.5):
    threshold = yinPos*maxD
    d       = K.abs(yinPos - youtPos)
    count0   = K.sum(yinMax>0.5)
    count1   = K.sum((yinMax>0.5)*(youtMax>minP))
    hitCount= K.sum((d<threshold)*(yinMax>0.5)*(youtMax>minP))
    recall = hitCount/count0
    right  = hitCount/count1
    F = 2/(1/recall+1/right)
    return recall, right,F
'''
def rightRateNp(yinPos,youtPos,yinMax,youtMax,maxD=0.03,K=np, minP=0.5):
    threshold = yinPos*maxD
    d       = K.abs(yinPos - youtPos)
    #print(d)
    #print(d.mean(axis=(0,1)))
    count   = K.sum((yinMax>0.5)*(youtMax>minP))
    hitCount= K.sum((d<threshold)*(yinMax>0.5)*(youtMax>minP))
    return hitCount/count
'''


def printRes_old(yin, yout):
    #       0.01  0.8  0.36600 0.9996350
    strL   = 'maxD   minP hitRate rightRate F old'
    strfmt = '\n%5.3f %3.1f %7.5f %7.5f %7.5f'
    yinPos  = yin.argmax( axis=1)
    youtPos = yout.argmax(axis=1)
    yinMax = yin.max(axis=1)
    youtMax = yout.max(axis=1)
    for maxD in [0.03,0.02,0.01,0.005]:
        for minP in [0.5,0.7,0.8,0.9]:
            hitRate,rightRate,F = rateNp(\
                yinPos,youtPos,yinMax,youtMax,maxD=maxD,minP=minP)
            strL += strfmt%(maxD, minP, hitRate, rightRate,F)
    print(strL)
    return strL

def printRes(yin, yout):
    #       0.01  0.8  0.36600 0.9996350
    strL   = 'maxD   minP hitRate rightRate F'
    strfmt = '\n%5.3f %3.1f %7.5f %7.5f %7.5f'
    try:
        yinPos, yinMax = findPos(yin)
        youtPos, youtMax = findPos(yout) 
        for maxD in [0.03,0.02,0.01,0.005]:
            for minP in [0.5,0.7,0.8,0.9]:
                hitRate,rightRate, F = rateNp(\
                    yinPos,youtPos,yinMax,youtMax,maxD=maxD,minP=minP)
                strL += strfmt%(maxD, minP, hitRate, rightRate,F)
    except:
        print('cannot find')
    else:
        pass
    print(strL)
    return strL


def inAndOutFuncNewV6(config, onlyLevel=-10000):
    BNA = -1
    inputs  = Input(config.inputSize,name='inputs')
    depth   =  len(config.featureL)
    convL   = [None for i in range(depth+1)]
    dConvL  = [None for i in range(depth+1)]
    last    = inputs
    for i in range(depth):
        if i <4:
            name = 'conv'
        else:
            name = 'CONV'
        layerStr='_%d_'%i
        
        last = Conv2D(config.featureL[i],kernel_size=config.kernelL[i],\
            strides=(1,1),padding='same',name=name+layerStr+'0',\
            kernel_initializer=config.initializerL[i],\
            bias_initializer=config.bias_initializerL[i])(last)

        last = BatchNormalization(axis=BNA,trainable=True,name='BN'+layerStr+'0')(last)

        last = Activation(config.activationL[i],name='AC'+layerStr+'0')(last)

        convL[i] =last

        last = Conv2D(config.featureL[i],kernel_size=config.kernelL[i],\
            strides=(1,1),padding='same',name=name+layerStr+'1',\
            kernel_initializer=config.initializerL[i],\
            bias_initializer=config.bias_initializerL[i])(last)

        if i in config.dropOutL:
            ii   = config.dropOutL.index(i)
            last =  Dropout(config.dropOutRateL[ii],name='Dropout'+layerStr+'0')(last)
        else:
            last = BatchNormalization(axis=BNA,trainable=True,name='BN'+layerStr+'1')(last)

        last = Activation(config.activationL[i],name='AC'+layerStr+'1')(last)

        last = config.poolL[i](pool_size=config.strideL[i],\
            strides=config.strideL[i],padding='same',name='PL'+layerStr+'0')(last)

    convL[depth] =last
    outputsL =[]
    for i in range(depth-1,-1,-1):
        if i <3:
            name = 'dconv'
        else:
            name = 'DCONV'
        
        for j in range(i+1):

            layerStr='_%d_%d'%(i,j)

            dConvL[j]= Conv2DTranspose(config.featureL[j],kernel_size=config.kernelL[j],\
                strides=config.strideL[j],padding='same',name=name+layerStr+'0',\
                kernel_initializer=config.initializerL[j],\
                bias_initializer=config.bias_initializerL[j])(convL[j+1])

            if j in config.dropOutL:
                jj   = config.dropOutL.index(j)
                dConvL[j] =  Dropout(config.dropOutRateL[jj],name='Dropout_'+layerStr+'0')(dConvL[j])
            else:
                dConvL[j] = BatchNormalization(axis=BNA,trainable=True,name='BN_'+layerStr+'0')(dConvL[j])

            dConvL[j]  = Activation(config.activationL[j],name='Ac_'+layerStr+'0')(dConvL[j])
            dConvL[j]  = concatenate([dConvL[j],convL[j]],axis=BNA,name='conc_'+layerStr+'0')
            dConvL[j]  = Conv2D(config.featureL[j],kernel_size=config.kernelL[j],\
                strides=(1,1),padding='same',name=name+layerStr+'1',\
                kernel_initializer=config.initializerL[j],\
                bias_initializer=config.bias_initializerL[j])(dConvL[j])
            dConvL[j] = BatchNormalization(axis=BNA,trainable=True,name='BN_'+layerStr+'1')(dConvL[j])
            dConvL[j] = Activation(config.activationL[j],name='Ac_'+layerStr+'1')(dConvL[j])
            convL[j]  = concatenate([dConvL[j],convL[j]],axis=BNA,name='conc_'+layerStr+'1')
            if i <config.deepLevel and j==0:
                #outputsL.append(Conv2D(config.outputSize[-1],kernel_size=(8,1),strides=(1,1),\
                #padding='same',activation='sigmoid',name='dconv_out_%d'%i)(convL[0]))
                outputsL.append(Dense(config.outputSize[-1], activation='sigmoid'\
                    ,name='dense_out_%d'%i)(convL[0]))
        
    #outputs = Conv2D(config.outputSize[-1],kernel_size=(8,1),strides=(1,1),\
    #    padding='same',activation='sigmoid',name='dconv_out')(convL[0])
    if len(outputsL)>1:
        outputs = concatenate(outputsL,axis=2,name='lastConc')
    else:
        outputs = outputsL[-1]
        if config.mode == 'p' or config.mode == 's'or config.mode == 'ps':
            if config.outputSize[-1]>1:
                outputs = Softmax(axis=3)(outputs) 
    if onlyLevel>-100:
        outputs = outputsL[onlyLevel]
    return inputs,outputs


class xyt:
    def __init__(self,x,y,t=''):
        self.x = x
        self.y = y
        self.t = t
        self.timeDisKwarg={'sigma':-1}
    def __call__(self,iL):
        if not isinstance(iL,np.ndarray):
            iL= np.array(iL).astype(np.int)
        if len(self.t)>0:
            tout = self.t[iL]
        else:
            tout = self.t
        self.iL = iL
        return self.x[iL],self.y[iL],tout
    def __len__(self):
        return self.x.shape[0]


tTrain = (10**np.arange(0,1.000001,1/29))*16

def trainAndTest(model,corrLTrain,corrLValid,corrLTest,outputDir='predict/',tTrain=tTrain,\
    sigmaL=[4,3,2,1.5],count0=3,perN=200,w0=4):
    '''
    依次提高精度要求，加大到时附近权重，以在保证收敛的同时逐步提高精度
    '''
    #xTrain, yTrain, timeTrain =corrLTrain(np.arange(0,20000))
    #model.show(xTrain,yTrain,time0L=timeTrain ,delta=1.0,T=tTrain,outputDir=outputDir+'_train')
    #2#4#8#8*3#8#5#10##model.config.lossFunc.w
    tmpDir =  os.path.dirname(outputDir)
    if not os.path.exists(tmpDir):
        os.makedirs(tmpDir)
    model.plot(outputDir+'model.png')
    testCount = len(corrLTest)
    showCount = int(len(corrLTest)*1)
    showD     = int(showCount/40)
    resStr = 'testCount %d showCount %d \n'%(testCount,showCount)
    resStr +='train set setting: %s\n'%corrLTrain
    resStr +='test  set setting: %s\n'%corrLTest
    resStr +='perN: %d count0: %d w0: %.5f\n'%(perN, count0, w0)
    resStr +='sigmaL: %s\n'%sigmaL
    print(resStr)
    trainTestLossL =[]
    for sigma in sigmaL:
        model.config.lossFunc.w = w0*(1.5/sigma)**0.5
        corrLTrain.timeDisKwarg['sigma']=sigma
        corrLTest.timeDisKwarg['sigma']=sigma
        corrLValid.timeDisKwarg['sigma']=sigma
        corrLValid.iL=np.array([])
        corrLTrain.iL=np.array([])
        corrLTest.iL=np.array([])
        model.compile(loss=model.config.lossFunc, optimizer='Nadam')
        xTest, yTest, tTest =corrLValid(np.arange(len(corrLValid)))
        resStrTmp, trainTestLoss=model.trainByXYT(corrLTrain,xTest=xTest,yTest=yTest,\
            count0=count0, perN=perN)
        resStr += resStrTmp
        trainTestLossL.append(trainTestLoss)
    xTest, yTest, tTest =corrLValid(np.arange(len(corrLValid)))
    yout=model.predict(xTest)  
    for threshold in [0.5,0.7,0.8]:
        corrLValid.plotPickErro(yout,tTrain,fileName=outputDir+'erro_valid.jpg',\
            threshold=threshold)
    xTest, yTest, tTest =corrLTest(np.arange(showCount))
    yout=model.predict(xTest)
    resStr += '\n test part\n'
    for level in range(yout.shape[-2]):
        print('level: %d'%(len(model.config.featureL)\
            -yout.shape[-2]+level+1))
        resStr +='\nlevel: %d'%(len(model.config.featureL)\
            -yout.shape[-2]+level+1)
        resStr+= printRes_old(yTest, yout[:,:,level:level+1])+'\n'
        #resStr+= printRes(yTest, yout[:,:,level:level+1])+'\n'
    head = outputDir+'resStr_'+\
        obspy.UTCDateTime(time.time()).strftime('%y%m%d-%H%M%S')
    with open(head+'.log','w') as f:
        ###save model
        model.summary(print_fn=lambda x: f.write(x + '\n'))
        f.write(resStr)
    for i in range(len(sigmaL)):
        sigma = sigmaL[i]
        trainTestLoss = trainTestLossL[i]
        np.savetxt('%s_sigma%.3f_loss'%(head,sigma),np.array(trainTestLoss))
    for threshold in [0.5,0.7,0.8]:
        corrLTest.plotPickErro(yout,tTrain,fileName=outputDir+'erro_test.jpg',\
                threshold=threshold)
    model.save(head+'_model')
    iL=np.arange(0,showCount,showD)
    for level in range(-1,-model.config.deepLevel-1,-1):
        model.show(xTest[iL],yTest[iL],time0L=tTest[iL],delta=1.0,\
        T=tTrain,outputDir=outputDir,level=level)



def trainAndTestCross(model0,model1,corrLTrain0,corrLTrain1,corrLTest,outputDir='predict/',tTrain=tTrain,\
    sigmaL=[4,2],modeL=['conv','conv']):
    '''
    依次提高精度要求，加大到时附近权重，以在保证收敛的同时逐步提高精度
    '''
    #xTrain, yTrain, timeTrain =corrLTrain(np.arange(0,20000))
    #model.show(xTrain,yTrain,time0L=timeTrain ,delta=1.0,T=tTrain,outputDir=outputDir+'_train')
    #different data train different part
    w0 = 2#5#10##model.config.lossFunc.w
    for i in range(len(sigmaL)):
        sigma = sigmaL[i]
        mode = modeL[i]
        model0.config.lossFunc.w = w0*(4/sigma)**0.5
        model1.config.lossFunc.w = w0*(4/sigma)**0.5
        corrLTrain0.timeDisKwarg['sigma']=sigma
        corrLTrain1.timeDisKwarg['sigma']=sigma
        corrLTest.timeDisKwarg['sigma']=sigma
        corrLTest.iL=np.array([])
        if mode =='conv':
            model0.setTrain(['conv','CONV'],True)
            model1.setTrain([],False)
            per1=0.5
        if mode =='anti_conv':
            model0.setTrain([],False)
            model1.setTrain(['conv','CONV'],True)
            per1=0.5
        if mode =='dconv':
            model0.setTrain([],False)
            model1.setTrain(['dconv'],True)
            per1=2
        if mode =='None':
            model0.setTrain([],False)
            model1.setTrain([],False)
            per1=0.5
        if mode =='conv_dconv':
            model0.setTrain(['conv','CONV'],True)
            model1.setTrain(['dconv','DCONV'],True)
            per1 = 0.5
        if mode =='0':
            model0.setTrain([],False)
            model1.setTrain([],True)
            per1 = 0.5
        xTest, yTest, tTest =corrLTest(np.arange(2000,4000))
        model0.trainByXYTCross(model1,corrLTrain0,corrLTrain1,xTest=xTest,yTest=yTest,per1=per1)
    xTest, yTest, tTest =corrLTest(np.arange(2000))
    corrLTest.plotPickErro(model0.predict(xTest),tTrain,\
    fileName=outputDir+'erro.jpg')
    iL=np.arange(0,1000,50)
    model0.show(xTest[iL],yTest[iL],time0L=tTest[iL],delta=1.0,\
    T=tTrain,outputDir=outputDir)
    xTest, yTest, tTest =corrLTrain0(np.arange(10000))
    corrLTrain0.plotPickErro(model0.predict(xTest),tTrain,\
    fileName=outputDir+'erro0.jpg')
    iL=np.arange(0,1000,50)
    model0.show(xTest[iL],yTest[iL],time0L=tTest[iL],delta=1.0,\
    T=tTrain,outputDir=outputDir+'_0_')
    xTest, yTest, tTest =corrLTrain1(np.arange(10000))
    corrLTrain1.plotPickErro(model0.predict(xTest),tTrain,\
    fileName=outputDir+'erro1.jpg')
    iL=np.arange(0,1000,50)
    model0.show(xTest[iL],yTest[iL],time0L=tTest[iL],delta=1.0,\
    T=tTrain,outputDir=outputDir+'_1_')

class fcnConfig:
    def __init__(self,mode='surf'):
        self.mode=mode
        if mode=='surf':
            self.inputSize     = [4096*3,1,4]
            self.outputSize    = [4096*3,1,50]
            self.featureL      = [min(2**(i+1)+20,80) for i in range(7)]
            self.featureL      = [30,40,60,60,80,60,40]
            self.featureL      = [15,20,20,25,25,40,60]
            self.featureL      = [32,32,64,64,64,128,128]#[8,16,32,64,128,128,256]
            self.featureL      = [32,32,32,64,64,64,128]
            self.featureL      = [32,32,32,64,64,64,128]
            self.featureL      = [24,24,32,48,48,64,128]
            self.featureL      = [32,32,48,48,64,64,128]
            self.featureL      = [32,48,48,64,64,96,128]
            self.featureL      = [32,32,32,32,48,64,96,128]
            self.featureL      = [16,32,48,64,128,256,512]#high
            self.featureL      = [24,32,48,64,128,256,512]
            self.strideL       = [(2,1),(4,1),(4,1),(4,1),(4,1),(4,1),(6,1),\
            (4,1),(2,1),(2,1),(2,1)]
            self.kernelL       = [(6,1),(8,1),(8,1),(8,1),(8,1),(16,1),(6,1),\
            (8,1),(4,1),(4,1),(4,1)]
            self.initializerL  = ['truncated_normal' for i in range(10)]
            self.initializerL  = ['he_normal' for i in range(10)]
            self.bias_initializerL = ['random_normal' for i in range(10)]
            self.bias_initializerL = ['he_normal' for i in range(10)]
            self.dropOutL     =[]# [0,1,2]#[5,6,7]#[1,3,5,7]#[1,3,5,7]
            self.dropOutRateL = []#[0.2,0.2,0.2]#[0.2,0.2,0.2]
            self.activationL  = ['relu','relu','relu','relu','relu',\
            'relu','relu','relu','relu','relu','relu']
            self.activationL  = ['relu','relu']+['swish' for i in range(4)]+['relu']
            self.poolL        = [AveragePooling2D,AveragePooling2D,MaxPooling2D,\
            AveragePooling2D,AveragePooling2D,MaxPooling2D,MaxPooling2D,AveragePooling2D,\
            MaxPooling2D,AveragePooling2D,MaxPooling2D]
            self.poolL        = [MaxPooling2D,AveragePooling2D,MaxPooling2D,\
            AveragePooling2D,MaxPooling2D,MaxPooling2D,MaxPooling2D,AveragePooling2D,\
            MaxPooling2D,AveragePooling2D,MaxPooling2D]
            self.lossFunc     = lossFuncSoft(w=10)#10
            self.inAndOutFunc = inAndOutFuncNewV6
            self.deepLevel = 1
        elif mode == 'p' or mode=='s':
            self.inputSize     = [2000,1,3]
            self.outputSize    = [2000,1,1]
            #self.featureL      = [min(2**(i+1)+20,80) for i in range(7)]#high
            #self.featureL      = [8,16,32,64,128,256,512]
            #self.featureL      = [6,12,24,48,96,192,384]
            self.featureL      = [4,8,16,32,64,128,256]
            self.strideL       = [(2,1),(2,1),(2,1),(2,1),(5,1),(5,1),(5,1)]
            #self.kernelL       = [(4,1),(4,1),(4,1),(4,1),(10,1),(10,1),(10,1),\
            #(8,1),(4,1),(4,1),(4,1)]
            self.kernelL       = [(4,1),(4,1),(4,1),(4,1),(10,1),(10,1),(5,1),\
            (8,1),(4,1),(4,1),(4,1)]
            #self.initializerL  = ['truncated_normal' for i in range(10)]
            self.initializerL  = ['he_normal' for i in range(10)]
            #self.bias_initializerL = ['random_normal' for i in range(10)]
            self.bias_initializerL = ['he_normal' for i in range(10)]
            self.dropOutL     =[]# [0,1,2]#[5,6,7]#[1,3,5,7]#[1,3,5,7]
            self.dropOutRateL = []#[0.2,0.2,0.2]#[0.2,0.2,0.2]
            self.activationL  = ['relu','relu','relu','relu','relu',\
            'relu','relu','relu','relu','relu','relu']
            #self.activationL  = ['relu','relu']+['swish' for i in range(4)]+['relu']
            self.activationL  = ['relu','swish' ,'relu','swish','relu','swish' ,'relu']
            self.poolL        = [AveragePooling2D,AveragePooling2D,MaxPooling2D,\
            AveragePooling2D,AveragePooling2D,MaxPooling2D,MaxPooling2D,AveragePooling2D,\
            MaxPooling2D,AveragePooling2D,MaxPooling2D]
            self.poolL        = [MaxPooling2D,AveragePooling2D,MaxPooling2D,\
            AveragePooling2D,MaxPooling2D,MaxPooling2D,MaxPooling2D,AveragePooling2D,\
            MaxPooling2D,AveragePooling2D,MaxPooling2D]
            if mode=='p':
                self.lossFunc     = lossFuncNew#10
            elif mode =='s': 
                self.lossFunc     = lossFuncNewS
            self.inAndOutFunc = inAndOutFuncNewV6
            self.deepLevel = 1
    def inAndOut(self,*argv,**kwarg):
        return self.inAndOutFunc(self,*argv,**kwarg)

w1=np.ones(1500)*0.5
w0=np.ones(250)*(-0.75)
w2=np.ones(250)*(-0.25)
w=np.append(w0,w1)
w=np.append(w,w2)
wY=K.variable(w.reshape((1,2000,1,1)))

w11=np.ones(1800)*0
w01=np.ones(100)*(-0.8)*0
w21=np.ones(100)*(-0.3)*0
w1=np.append(w01,w11)
w1=np.append(w1,w21)
W1=w1.reshape((1,2000,1,1))
wY1=K.variable(W1)
wY1Short=K.variable(W1[:,200:1800])
wY1Shorter=K.variable(W1[:,400:1600])
wY1500=K.variable(W1[:,250:1750])
W2=np.zeros((1,2000,1,3))
W2[0,:,:,0]=W1[0,:,:,0]*0+(1-0.13)
W2[0,:,:,1]=W1[0,:,:,0]*0+(1-0.13)
W2[0,:,:,2]=W1[0,:,:,0]*0+0.13
wY2=K.variable(W2)

def lossFuncNew(y,yout):

    #yW=(K.sign(-y-0.1)+1)*10*(K.sign(yout-0.35)+1)+1
    #y=(K.sign(y+0.1)+1)*y/2
    y0=0.13
    return -K.mean((y*K.log(yout+1e-9)/y0+(1-y)*(K.log(1-yout+1e-9))/(1-y0))*(y*0+1)*(1+K.sign(y)*wY1),axis=[0,1,2,3])
'''
def lossFuncNew(y,yout):

    yW=(K.sign(-y-0.1)+1)*10*(K.sign(yout-0.35)+1)+1
    y=(K.sign(y+0.1)+1)*y/2
    y0=0.13
    return -K.mean((y*K.log(yout+1e-9)/y0+(1-y)*(K.log(1-yout+1e-9))/(1-y0))*(y*0+1)*(1+K.sign(y)*wY1)*yW,axis=[0,1,2,3])

def lossFuncNewS(y,yout):
    y=y
    yW=(K.sign(-y-0.1)+1)*10*(K.sign(yout-0.35)+1)+1
    y=(K.sign(y+0.1)+1)*y/2
    y0=0.13
    return -K.mean((y*K.log(yout+1e-9)/y0+(1-y)*(K.log(1-yout+1e-9))/(1-y0))*(y*0+1)*(1+K.sign(y)*wY1)*yW,axis=[0,1,2,3])
'''
def lossFuncNewS(y,yout):
    #y=y
    #yW=(K.sign(-y-0.1)+1)*10*(K.sign(yout-0.35)+1)+1
    #y=(K.sign(y+0.1)+1)*y/2
    y0=0.13
    return -K.mean((y*K.log(yout+1e-9)/y0+(1-y)*(K.log(1-yout+1e-9))/(1-y0))*(y*0+1)*(1+K.sign(y)*wY1),axis=[0,1,2,3])


def genModel0(modelType='norm',phase='p'):
    return model(config=fcnConfig(mode=phase),channelList=[0,1,2]),2000,1
'''

for i in range(10):
    plt.plot(inputData[i,:,0,0]/5,'k',linewidth=0.3)
    plt.plot(probP[i,:,0,0].transpose(),'b',linewidth=0.3)
    plt.plot(probS[i,:,0,0].transpose(),'r',linewidth=0.3)
    plt.show()
'''
class model(Model):
    def __init__(self,weightsFile='',config=fcnConfig(),metrics=rateNp,\
        channelList=[1,2,3,4],onlyLevel=-1000):
        config.inputSize[-1]=len(channelList)
        self.genM(config, onlyLevel)
        self.config = config
        self.Metrics = metrics
        self.channelList = channelList
        self.compile(loss=self.config.lossFunc, optimizer='Nadam')
        if len(weightsFile)>0:
            model.load_weights(weightsFile)
        print(self.summary())

    def genM(self,config, onlyLevel=-1000):
        inputs, outputs = config.inAndOut(onlyLevel=onlyLevel)
        #outputs  = Softmax(axis=3)(last)
        super().__init__(inputs=inputs,outputs=outputs)
        self.compile(loss=config.lossFunc, optimizer='Nadam')
        return model
    def predict(self,x):
        #print('inx')
        x = self.inx(x)
        #print('inx done')
        return super().predict(x).astype(np.float16)
    def fit(self,x,y,batchSize=None):
        x=self.inx(x)
        if np.isnan(x).sum()>0 or np.isinf(x).sum()>0:
            print('bad record')
            return None
        return super().fit(x ,y,batch_size=batchSize)
    def plot(self,filename='model.png'):
        plot_model(self, to_file=filename)
    def inx(self,x):
        if self.config.mode=='surf':
            if x.shape[-1] > len(self.channelList):
                x = x[:,:,:,self.channelList]
            timeN0 = np.float32(x.shape[1])
            timeN  = (x!=0).sum(axis=1,keepdims=True).astype(np.float32)
            timeN *= 1+0.2*(np.random.rand(*timeN.shape).astype(np.float32)-0.5)
            x/=(x.std(axis=(1,2),keepdims=True))*(timeN0/timeN)**0.5
        else:
            x/=x.std(axis=(1,2,3),keepdims=True)
        return x
    def __call__(self,x):
        return super(Model, self).__call__(K.tensor(self.inx(x)))
    def train(self,x,y,**kwarg):
        if 't' in kwarg:
            t = kwarg['t']
        else:
            t = ''
        XYT = xyt(x,y,t)
        self.trainByXYT(XYT,**kwarg)
    def trainByXYT(self,XYT,N=2000,perN=200,batchSize=None,xTest='',\
        yTest='',k0 = 4e-3,t='',count0=3):
        if k0>1:
            K.set_value(self.optimizer.lr, k0)
        indexL = range(len(XYT))
        sampleDone = np.zeros(len(XYT))
        #print(indexL)
        lossMin =100
        count   = count0
        w0 = self.get_weights()
        resStr=''
        trainTestLoss = []
        iL = random.sample(indexL,xTest.shape[0])
        xTrain, yTrain , t0LTrain = XYT(iL)
        #print(self.metrics)
        for i in range(N):
            iL = random.sample(indexL,perN)
            for ii in iL:
                sampleDone[ii]+=1
            x, y , t0L = XYT(iL)
            #print(XYT.iL)
            self.fit(x ,y,batchSize=batchSize)
            if i%10==0:
                if len(xTest)>0:
                    lossTrain = self.evaluate(self.inx(xTrain),yTrain)
                    lossTest    = self.evaluate(self.inx(xTest),yTest)
                    print('train loss',lossTrain,'test loss: ',lossTest,\
                        'sigma: ',XYT.timeDisKwarg['sigma'],\
                        'w: ',self.config.lossFunc.w, \
                        'no sampleRate:', 1 - np.sign(sampleDone).mean(),\
                        'sampleTimes',sampleDone.mean())
                    resStr+='\n %d train loss : %f valid loss :%f'%(i,lossTrain,lossTest)
                    trainTestLoss.append([i,lossTrain,lossTest])
                    if lossTest >= lossMin:
                        count -= 1
                    if lossTest > 3*lossMin:
                        self.set_weights(w0)
                        #count = count0
                        print('reset to smallest')
                    if lossTest < lossMin:
                        count = count0
                        lossMin = lossTest
                        w0 = self.get_weights()
                        print('find better')
                    if count ==0:
                        break
                    #print(self.metrics)
                    
                    if i%30==0 and i>10:
                        youtTrain = 0
                        youtTest  = 0
                        youtTrain = self.predict(xTrain)
                        youtTest  = self.predict(xTest)
                        for level in range(youtTrain.shape[-2]):
                            print('level',len(self.config.featureL)\
                                -youtTrain.shape[-2]+level+1)
                            resStr +='\nlevel: %d'%(len(self.config.featureL)\
                                -youtTrain.shape[-2]+level+1)
                            resStr+='\ntrain '+printRes_old(yTrain, youtTrain[:,:,level:level+1])
                            resStr+='\ntest '+printRes_old(yTest, youtTest[:,:,level:level+1])
            if i%5==0:
                print('learning rate: ',self.optimizer.lr)
                K.set_value(self.optimizer.lr, K.get_value(self.optimizer.lr) * 0.95)
            if i>10 and i%5==0:
                perN += int(perN*0.05)
                perN = min(1000, perN)
        self.set_weights(w0)
        return resStr,trainTestLoss
    def trainByXYTCross(self,self1,XYT0,XYT1,N=2000,perN=100,batchSize=None,\
        xTest='',yTest='',k0 = -1,t='',per1=0.5):
        #XYT0 syn
        #XYT1 real
        if k0>1:
            K.set_value(self.optimizer.lr, k0)
        indexL0 = range(len(XYT0))
        indexL1 = range(len(XYT1))
        #print(indexL)
        lossMin =100
        count0  = 10
        count   = count0
        w0 = self.get_weights()

        #print(self.metrics)
        for i in range(N):
            is0 =False
            if (i < 10) or (np.random.rand()<per1  and i <20):
                print('1')
                is0 =False
                XYT = XYT1
                iL = random.sample(indexL1,perN)
                SELF = self1
            else:
                print('0')
                is0 = True
                XYT = XYT0
                iL = random.sample(indexL0,perN)
                SELF = self
            x, y , t0L = XYT(iL)   
            #print(XYT.iL)
            SELF.fit(x ,y ,batchSize=batchSize)
            if  is0:
                self1.set_weights(self.get_weights())
            else:
                self.set_weights(self1.get_weights())
            if i%3==0 and (is0 or per1>=1):
                if len(xTest)>0:
                    loss    = self.evaluate(self.inx(xTest),yTest)
                    lossM = self.Metrics(yTest,self.predict(xTest))
                    if loss >= lossMin:
                        count -= 1
                    if loss > 3*lossMin:
                        self.set_weights(w0)
                        #count = count0
                        print('reset to smallest')
                    if loss < lossMin:
                        count = count0
                        lossMin = loss
                        w0 = self.get_weights()
                    if count ==0:
                        break
                    #print(self.metrics)
                   
                    print('test loss: ',loss,' metrics: ',lossM,'sigma: ',\
                        XYT.timeDisKwarg['sigma'],'w: ',self.config.lossFunc.w)
            if i%5==0:
                print('learning rate: ',self.optimizer.lr)
                K.set_value(self.optimizer.lr, K.get_value(self.optimizer.lr) * 0.9)
                K.set_value(self1.optimizer.lr, K.get_value(self1.optimizer.lr) * 0.9)
            if i==50:
                perN = 100
            if i>10 and i%5==0:
                perN += int(perN*0.02)
        self.set_weights(w0)
    def show(self, x, y0,outputDir='predict/',time0L='',delta=0.5,T=np.arange(19),fileStr='',\
        level=-1):
        y = self.predict(x)
        f = 1/T
        count = x.shape[1]
        for i in range(len(x)):
            #print('show',i)
            timeL = np.arange(count)*delta
            if len(time0L)>0:
                timeL+=time0L[i]
            xlim=[timeL[0],timeL[-1]]
            xlimNew=[0,500]
            #xlim=xlimNew
            tmpy0=y0[i,:,0,:]
            pos0  =tmpy0.argmax(axis=0)
            tmpy=y[i,:,0,:]
            pos  =tmpy.argmax(axis=0)
            plt.close()
            plt.figure(figsize=[12,8])
            plt.subplot(4,1,1)
            plt.title('%s%d'%(outputDir,i))
            legend = ['r s','i s',\
            'r h','i h']
            for j in range(x.shape[-1]):
                plt.plot(timeL,self.inx(x[i:i+1,:,0:1,j:j+1])[0,:,-1,0]-j,'rbgk'[j],\
                    label=legend[j],linewidth=0.3)
            #plt.legend()
            plt.xlim(xlim)
            plt.subplot(4,1,2)
            #plt.clim(0,1)
            plt.pcolor(timeL,f,y0[i,:,0,:].transpose(),cmap='bwr',vmin=0,vmax=1)
            plt.plot(timeL[pos.astype(np.int)],f,'k',linewidth=0.5,alpha=0.5)
            plt.ylabel('f/Hz')
            plt.gca().semilogy()
            plt.xlim(xlimNew)
            plt.subplot(4,1,3)
            plt.pcolor(timeL,f,y[i,:,level,:].transpose(),cmap='bwr',vmin=0,vmax=1)
            #plt.clim(0,1)
            plt.plot(timeL[pos0.astype(np.int)],f,'k',linewidth=0.5,alpha=0.5)
            plt.ylabel('f/Hz')
            plt.xlabel('t/s')
            plt.gca().semilogy()
            plt.xlim(xlimNew)
            plt.subplot(4,1,4)
            delta = timeL[1] -timeL[0]
            N = len(timeL)
            fL = np.arange(N)/N*1/delta
            for j in range(x.shape[-1]):
                spec=np.abs(np.fft.fft(self.inx(x[i:i+1,:,0:1,j:j+1])[0,:,0,0])).reshape([-1])
                plt.plot(fL,spec/(spec.max()+1e-16),'rbgk'[j],\
                    label=legend[j],linewidth=0.3)
            plt.xlabel('f/Hz')
            plt.ylabel('A')
            plt.xlim([fL[1],fL[-1]/2])
            #plt.gca().semilogx()
            plt.savefig('%s%s_%d_%d.jpg'%(outputDir,fileStr,level,i),dpi=200)
    def predictRaw(self,x):
        yShape = list(x.shape)
        yShape[-1] = self.config.outputSize[-1]
        y = np.zeros(yShape)
        d = self.config.outputSize[0]
        halfD = int(self.config.outputSize[0]/2)
        iL = list(range(0,x.shape[0]-d,halfD))
        iL.append(x.shape[0]-d)
        for i0 in iL:
            y[:,i0:(i0+d)] = x.predict(x[:,i0:(i0+d)])
        return y
    def set(self,modelOld):
        self.set_weights(modelOld.get_weights())
    def setTrain(self,name,trainable=True):
        lr0= K.get_value(self.optimizer.lr)
        for layer in self.layers:
            if layer.name.split('_')[0] in name:
                layer.trainable = trainable
                print('set',layer.name,trainable)
            else:
                layer.trainable = not trainable
                print('set',layer.name,not trainable)

        self.compile(loss=self.config.lossFunc, optimizer='Nadam')
        K.set_value(self.optimizer.lr,  lr0)