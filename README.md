# label editor

### 环境要求

需要安装tkinter环境

### 适用数据

适用于图片和标签分别保存为两个npy文件的数据集

其中

```
# 设定数据集规模为N张图片, 轮廓点数量为L
images = np.load('images.npy').astype(np.uint8)
contours = np.load('contours.npy').astype(np.uint16) # uint8最大值只有255所以用uint16

print(f'img shape: {images.shape}')
print(f'cnt shape: {contours.shape}')

--------------运行结果--------------

img shape: (H, W, C, N)
cnt shape: (L, 2, N) # L个轮廓点, xy坐标, N张图片
```

### 运行

在命令行输入`python editor.py`启动

## 特色

功能：

1. 编辑轮廓标签，支持单点编辑和整体平移
3. 支持撤销/重做以及缓存更改记录，即切换图片再切回来依然可以进行撤销/重做
4. 支持键盘左右键翻页
5. 支持保存时自定义文件名
6. 启动弹窗，可以浏览本地文件选择图像和轮廓的npy
7. 图片跳转功能，可以直接跳转到任意序号的图片
8. 对错误进行检查、弹窗
9. 支持单选多个点同时编辑
10. 支持框选多个点同时编辑
11. 运行时状态写入临时文件，程序意外退出也可以恢复最新当前进度
12. 支持隐藏标注轮廓，直接查看图片，方便观察
13. 支持历史记忆功能，在启动时文件选择弹窗中默认填入上一次打开的文件

快捷键：

```
撤销：ctrl+z
重做：ctrl+y
保存：ctrl+s
单选多个点：ctrl+鼠标左键单击
框选多个点：ctrl+鼠标左键移动
隐藏/显示轮廓：tab
跳转图片：enter
```
