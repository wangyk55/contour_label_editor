import os
os.environ['CUDA_VISIBLE_DEVICES'] = '0'
os.environ['FOR_DISABLE_CONSOLE_CTRL_HANDLER'] = '1'

import cv2
import torch
import numpy as np

from config import *
from models.ACStep import active_contour_process
from models.UNet_head import UNet
from models.CAT import CATkernel, ConVEF_model
from process.mapprocess import map_normalization
from process.snake_initialization import initialize_snake
from process.auxiliary_evolve_module import auxevolvehandler

from torchvision.transforms import Resize


def read_and_preprocess(img):
    img = cv2.resize(img, (image_size, image_size))
    img = img.astype(np.float32) / 255.0
    img = torch.from_numpy(img).unsqueeze(0)
    img = img.transpose(2, 3)
    img = img.transpose(1, 2)
    return img

def prepare_model(device):
    model = UNet()
    model.load_state_dict(torch.load(load_ckpt_dir))
    device = torch.device(device)
    model.train()
    model.to(device)
    Mx, My = CATkernel(image_size, image_size, CAT_Sharpness)
    if use_dsp_CAT:  # 下采样CAT模型，有助于提高训练速度(此处为卷积核定义)
        Mx_dsp, My_dsp = CATkernel(image_size/dsp_CAT_scale, image_size/dsp_CAT_scale, CAT_Sharpness)
        # 上句，设置下采样后CAT滤波的卷积核，卷积核小了，执行卷积的时候效率会提高一些。
        CAT_dsp = Resize([int(image_size/dsp_CAT_scale), int(image_size/dsp_CAT_scale)])  # 这个只是定义下采样操作（未放入数据），缩放到image_size/dsp_CAT_scale大小。
        CAT_usp = Resize([image_size, image_size])  # 这个是定义上采样操作，缩放到image_size大小。model = UNet()
    model.load_state_dict(torch.load(load_ckpt_dir))
    device = torch.device(device)
    model.train()
    model.to(device)
    return (model, Mx, My, Mx_dsp, My_dsp, CAT_dsp, CAT_usp)

def generate_contour(img, modelpack, device):
    model, Mx, My, Mx_dsp, My_dsp, CAT_dsp, CAT_usp = modelpack
    img = img.to(device)
    mapEo, mapAo, mapBo = model(img)
    with torch.no_grad():
        mapE = map_normalization(mapEo, batch_size) * 12
        mapB = map_normalization(mapBo, batch_size)
        mapA = map_normalization(mapAo, batch_size)
    snake_result = np.zeros([batch_size, L, 2])
    if use_dsp_CAT:
        dsp_mapE = CAT_dsp(mapE)
    b = 0
    if use_located_snake_init:  # 蛇的自适应初始化规则
        now_snake = initialize_snake(snake_type, image_size, snake_init_scale, L,
                                        adaptive=True, Emap=mapE[b,0,:,:], device=device)
    else:
        now_snake = initialize_snake(snake_type, image_size, snake_init_scale, L,
                                        adaptive=False, device=device)

    # MapE计算图像梯度
    Fu = torch.gradient(mapE[b,0,:,:],dim=0)[0]
    Fv = torch.gradient(mapE[b,0,:,:],dim=1)[0]
    # 以上，从u/v两个方向计算图像能量的导数。

    if not use_dsp_CAT:  # 计算CAT方向力
        gx0, gy0 = ConVEF_model(mapE[b,0,:,:], Mx, My)
    else:  # 计算CAT方向力（下采样版），为了加速，用的是这一版。
        gx0, gy0 = ConVEF_model(dsp_mapE[b,0,:,:], Mx_dsp, My_dsp)

    # 进行图均一化，使得CAT在各个方向上的绝对值均为1，这有助于加速蛇演化，并且真实的去做了capture range的扩大
    gx1, gy1 = gx0, gy0
    for ikk in range(0, gx0.shape[0]):
        for jkk in range(0, gx0.shape[1]):
            n_valsum = gx0[ikk, jkk] * gx0[ikk, jkk] + gy0[ikk, jkk] * gy0[ikk, jkk]  # CAT力的幅值
            franum = torch.sqrt(1 / n_valsum)
            gx1[ikk, jkk] *= franum
            gy1[ikk, jkk] *= franum
    # 以上，归一化CAT力场，每个点的CAT力都除以幅值。

    if not use_dsp_CAT:  # 如果没用下采样，那就直接用归一化的CAT力。
        gx1 = gx1.to(device)
        gy1 = gy1.to(device)
    else:  # 计算CAT方向力（下采样版）：如果用了下采样，现在把CAT力上采样回来。
        gx1 = CAT_usp(gx1.unsqueeze(0))[0].to(device)
        gy1 = CAT_usp(gy1.unsqueeze(0))[0].to(device)

    if adaptive_ACM_mode == 'yes':
        shistall = []
        last_evolve_rate = 0.0
        evolve_tries = 0
        while evolve_tries < max_ACM_reiter:
            su, sv, shist = active_contour_process(now_snake, Fu, Fv, mapA[b,0,:,:], mapB[b,0,:,:],
                                                    mCATu=-gx1, mCATv=gy1, iteration=ACM_iteration_base, delta_s=ACM_paramset['delta_s'],
                                                    CAT_force_weight=ACM_paramset['CAT_forceweight'], MAP_force_weight=ACM_paramset['Map_forceweight'], max_pixel_move=ACM_paramset['max_pixel_move'],
                                                    gamma=ACM_paramset['gamma'], device=device)

            now_snake[:,0] = su[:, 0]
            now_snake[:,1] = sv[:, 0]
            shistall += shist
            evolve_tries += 1

            coincide_rate = auxevolvehandler(mapE[b, 0, :, :], now_snake, image_size)
            if coincide_rate > 0.9:  # 判定为基本收敛
                print("[Converge:%d]"%evolve_tries)
                break
            elif abs(coincide_rate - last_evolve_rate) < 0.01 and evolve_tries > 10:
                print("[StopMove:%d]"%evolve_tries)
                break
            else:
                last_evolve_rate = coincide_rate
        snake_result[b, :, 0] = now_snake[:,0].detach().cpu().numpy()
        snake_result[b, :, 1] = now_snake[:,1].detach().cpu().numpy()
    else: # 常规演化情况
        su, sv, shist = active_contour_process(now_snake, Fu, Fv, mapA[b, 0, :, :], mapB[b, 0, :, :],
                                                mCATu=-gx1, mCATv=gy1, iteration=ACM_iterations,
                                                delta_s=ACM_paramset['delta_s'],
                                                CAT_force_weight=ACM_paramset['CAT_forceweight'],
                                                MAP_force_weight = ACM_paramset['Map_forceweight'],
                                                max_pixel_move=ACM_paramset['max_pixel_move'],
                                                gamma=ACM_paramset['gamma'], device=device)

        snake_result[b, :, 0] = su.detach().cpu().numpy()[:, 0]
        snake_result[b, :, 1] = sv.detach().cpu().numpy()[:, 0]
    
    snake_result = snake_result.transpose([1, 2, 0])
    return snake_result[:, :, 0]
