# 运行参数 ----------------------------------------------------------------------------
device = "cuda"  # 可选择："cuda"为NVIDIA显卡，"mps"为Apple ARM架构芯片，其他情况下请使用 "cpu"

# 训练参数 ----------------------------------------------------------------------------
batch_size = 1  # 运行批次大小(1为单张图片训练，接受大batch_size)

use_dsp_CAT = True  # 是否使用下采样CAT模型，有助于提高训练速度
dsp_CAT_scale = 4  # 下采样CAT模型的缩放比例

snake_type = 'circle'  # 初始化蛇的形状，'circle'或者'square'
snake_init_scale = 0.8  # 蛇的直径占据边长的比例

use_located_snake_init = True  # 是否通过mapE定位进行蛇初始化 (wyk蛇定位代码)

# ACM参数 ----------------------------------------------------------------------------
L = 200  # 蛇算法采样点数量

# 自适应演化参数
adaptive_ACM_mode = 'yes'  # 'no'表示不使用，'yes'保持常开
ACM_iteration_base = 50  # 自适应ACM基础演化次数
max_ACM_reiter = 20  # 自适应ACM最多重试演化次数

# 常规演化参数
ACM_iterations = 300  # Emap-ACM 蛇演化次数
CAT_Sharpness = 3  # 3.7在测试中是一个比较好的参数，适当增大锐度有助于提高性能
ACM_paramset = {
    "Map_forceweight": 30,  # MapE力场的权重# 30
    "CAT_forceweight": 1,  # CAT力场的权重 # 1
    "delta_s": 1.8,  # Emap-ACM delta_s 参量 # 1.8
    "max_pixel_move": 2,  # Emap-ACM 最大允许运行长度 # 2
    "gamma": 2.2  # Emap-ACM gamma 参量 # 2.2
}

# 数据读取 ----------------------------------------------------------------------------
image_size = 128  # 图片尺寸

# 模型权重读取 -------------------------------------------------------------------------
load_ckpt_dir = './checkpoints/ADMIRE_MRAVBCE_19.pth'
