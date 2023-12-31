import tkinter as tk

import os
import cv2
import time
import glob
import shutil
import numpy as np
from PIL import Image, ImageTk
from tkinter import filedialog, messagebox


class Contour:
    def __init__(self, canvas, points, undo_stack=[], redo_stack=[]):
        self.undo_stack = undo_stack
        self.redo_stack = redo_stack
        self.last_x = None
        self.last_y = None
        self.selected = None
        self.multiselected = []
        self.select_box = None
        self.node_selected_flag = False
        self.polygon_selected_flag = False
        self.canvas = canvas
        self.tag_id = 0

        self.points = points

        # polygon
        self.polygon = self.canvas.create_polygon(self.points, outline="mediumseagreen", fill="", width=3, tags="polygon", activeoutline='lime', activefill='')
        self.canvas.tag_bind(self.polygon, '<ButtonPress-1>',   lambda event, tag="polygon": self.on_press_tag(event, 0, tag))
        self.canvas.tag_bind(self.polygon, '<ButtonRelease-1>', lambda event, tag="polygon": self.on_release_tag(event, 0, tag))
        self.canvas.tag_bind(self.polygon, '<B1-Motion>', self.on_move_polygon)
        self.canvas.tag_bind(self.polygon, '<Alt-ButtonPress-1>', self.do_nothing)
        # self.canvas.tag_bind(self.polygon, '<Alt-ButtonRelease-1>', self.do_nothing)
        self.canvas.tag_bind(self.polygon, '<Control-ButtonPress-1>', self.do_nothing)
        # self.canvas.tag_bind(self.polygon, '<Control-ButtonRelease-1>', self.do_nothing)

        # nodes
        self.nodes = []
        for number, point in enumerate(self.points):
            x, y = point
            node = self.canvas.create_rectangle((x, y, x, y), outline='red', fill='red', width=4, tags=f"node{number}", activeoutline='yellow', activefill='yellow', activewidth=8)
            self.nodes.append(node)
            self.canvas.tag_bind(node, '<ButtonPress-1>',   lambda event, number=number, tag=f"node{number}": self.on_press_tag(event, number, tag))
            self.canvas.tag_bind(node, '<ButtonRelease-1>', lambda event, number=number, tag=f"node{number}": self.on_release_tag(event, number, tag))
            self.canvas.tag_bind(node, '<Control-ButtonPress-1>',   lambda event, number=number, tag=f"node{number}": self.on_press_tag_multi(event, number, tag))
            # self.canvas.tag_bind(node, '<Control-ButtonRelease-1>', self.do_nothing)
            self.canvas.tag_bind(node, '<Alt-ButtonPress-1>', self.do_nothing)
            # self.canvas.tag_bind(node, '<Alt-ButtonRelease-1>', self.do_nothing)
            self.canvas.tag_bind(node, '<B1-Motion>', lambda event, number=number: self.on_move_node(event, number))
            # self.canvas.tag_bind(node, '<Control-B1-Motion>', self.do_nothing)

        self.canvas.bind('<B1-Motion>', self.do_nothing2)
        self.canvas.bind('<Alt-ButtonPress-1>', lambda event:self.on_press_select(event))
        self.canvas.bind('<Alt-ButtonRelease-1>', lambda event:self.on_release_select(event))
        self.canvas.bind('<Alt-B1-Motion>', lambda event:self.on_move_select(event))
        self.canvas.bind('<ButtonPress-1>', self.root_grab_focus)
        self.canvas.bind('<ButtonPress-3>', self.on_press_tag_multi_cancel)
        # 绑定大小写z键来undo
        self.canvas.bind_all("<Control-z>", self.undo)
        self.canvas.bind_all("<Control-Z>", self.undo)
        # 绑定大小写y键来redo
        self.canvas.bind_all("<Control-y>", self.redo)
        self.canvas.bind_all("<Control-Y>", self.redo)
        # 按住tab键隐藏
        self.canvas.bind_all("<KeyPress-Tab>", self.hide_polygon)
        self.canvas.bind_all("<KeyRelease-Tab>", self.show_polygon)
    
    def on_press_tag(self, event, number, tag):
        if tag not in self.multiselected:
            for item in self.multiselected:
                c = self.canvas.coords(item)
                c[0], c[1], c[2], c[3] = c[0]+4, c[1]+4, c[2]-4, c[3]-4
                self.canvas.coords(item, c)
                self.canvas.itemconfig(item, outline='red', fill='red', activeoutline='yellow', activefill='yellow', width=4, activewidth=8)
            self.multiselected = []
        self.selected = tag
        self.last_x = event.x
        self.last_y = event.y
        self.redo_stack = []
        if self.multiselected:
            self.undo_stack.append({"selected": self.multiselected.copy(), "prev_x": event.x, "prev_y": event.y})
            self.undo_stack[-1]["item"] = "multinode"
            self.node_selected_flag = True
        else:
            self.undo_stack.append({"selected": self.selected, "prev_x": event.x, "prev_y": event.y})
            if tag == "polygon":
                self.undo_stack[-1]["item"] = "polygon"
                self.polygon_selected_flag = True
            else:
                self.undo_stack[-1]["item"] = "node"
                self.node_selected_flag = True
        self.undo_stack[-1]["tag_id"] = self.tag_id
        self.tag_id += 1

    def on_release_tag(self, event, number, tag):
        if not self.select_box:
            if self.node_selected_flag or self.polygon_selected_flag:
                self.selected = None
                self.last_x = None
                self.last_y = None
                self.undo_stack[-1]["curr_x"] = event.x
                self.undo_stack[-1]["curr_y"] = event.y
            self.node_selected_flag = False
            self.polygon_selected_flag = False

    def on_press_tag_multi(self, event, number, tag):
        if tag not in self.multiselected:
            self.multiselected.append(tag)
            c = self.canvas.coords(tag)
            c[0], c[1], c[2], c[3] = c[0]-4, c[1]-4, c[2]+4, c[3]+4
            self.canvas.coords(tag, c)
            self.canvas.itemconfig(tag, outline='yellow', fill='blue', activeoutline='yellow', activefill='blue', width=1, activewidth=1)
        else:
            c = self.canvas.coords(tag)
            c[0], c[1], c[2], c[3] = c[0]+4, c[1]+4, c[2]-4, c[3]-4
            self.canvas.coords(tag, c)
            self.canvas.itemconfig(tag, outline='red', fill='red', activeoutline='yellow', activefill='yellow', width=4, activewidth=8)
            self.multiselected.remove(tag)

    def on_press_tag_multi_cancel(self, event):
        if self.multiselected:
            for tag in self.multiselected:
                c = self.canvas.coords(tag)
                c[0], c[1], c[2], c[3] = c[0]+4, c[1]+4, c[2]-4, c[3]-4
                self.canvas.coords(tag, c)
                self.canvas.itemconfig(tag, outline='red', fill='red', activeoutline='yellow', activefill='yellow', width=4, activewidth=8)
            self.multiselected = []
    
    def do_nothing(self, e):
        pass

    def do_nothing2(self, e):
        if self.select_box:
            self.canvas.delete(self.select_box)
            self.select_box = None

    def root_grab_focus(self, e):
        global jump_num
        jump_num.delete(0, "end")
        self.canvas.master.focus_set()
    
    def hide_polygon(self, e):
        self.canvas.itemconfigure(self.polygon, state='hidden')
        for item in self.nodes:
            self.canvas.itemconfigure(item, state='hidden')
    
    def show_polygon(self, e):
        self.canvas.itemconfigure(self.polygon, state='normal')
        for item in self.nodes:
            self.canvas.itemconfigure(item, state='normal')

    def on_move_node(self, event, number):
        '''move single/multi node in polygon'''
        if not self.node_selected_flag:
            return
        if self.multiselected:
            dx = event.x - self.last_x
            dy = event.y - self.last_y

            for tag in self.multiselected:
                op_num = int(tag[4:])
                self.canvas.move(tag, dx, dy)
                self.points[op_num][0] += dx
                self.points[op_num][1] += dy

        elif self.selected:
            dx = event.x - self.last_x
            dy = event.y - self.last_y

            self.canvas.move(self.selected, dx, dy)
            self.points[number][0] += dx
            self.points[number][1] += dy
        
        else:
            return

        coords = sum(self.points, [])
        self.canvas.coords(self.polygon, coords)

        self.last_x = event.x
        self.last_y = event.y

    def on_move_polygon(self, event):
        '''move polygon and red rectangles in nodes'''
        if not self.polygon_selected_flag:
            return
        if self.selected:
            dx = event.x - self.last_x
            dy = event.y - self.last_y

            # move polygon
            self.canvas.move(self.selected, dx, dy)

            # move all nodes 
            for item in self.nodes:
                self.canvas.move(item, dx, dy)

            # recalculate values in self.points
            for item in self.points:
                item[0] += dx
                item[1] += dy

            self.last_x = event.x
            self.last_y = event.y

    def undo(self, e):
        if self.undo_stack:
            op = self.undo_stack.pop()
            self.redo_stack.append(op)
            dx = op["prev_x"] - op["curr_x"]
            dy = op["prev_y"] - op["curr_y"]
            if op["item"] == "multinode":
                for item in op["selected"]:
                    self.canvas.move(item, dx, dy)
                    op_num = int(item[4:])
                    self.points[op_num][0] += dx
                    self.points[op_num][1] += dy
                    coords = sum(self.points, [])
                    self.canvas.coords(self.polygon, coords)

            elif op["item"] == "polygon":
                self.canvas.move(op["selected"], dx, dy)
                for item in self.nodes:
                    self.canvas.move(item, dx, dy)
                for p in self.points:
                    p[0] += dx
                    p[1] += dy

            elif op["item"] == "node":
                self.canvas.move(op["selected"], dx, dy)
                op_num = int(op["selected"][4:])
                self.points[op_num][0] += dx
                self.points[op_num][1] += dy
                coords = sum(self.points, [])
                self.canvas.coords(self.polygon, coords)

        else:
            print("undo stack is empty")


    def redo(self, e):
        if self.redo_stack:
            op = self.redo_stack.pop()
            self.undo_stack.append(op)
            dx = op["curr_x"] - op["prev_x"]
            dy = op["curr_y"] - op["prev_y"]
            if op["item"] == "multinode":
                for item in op["selected"]:
                    self.canvas.move(item, dx, dy)
                    op_num = int(item[4:])
                    self.points[op_num][0] += dx
                    self.points[op_num][1] += dy
                    coords = sum(self.points, [])
                    self.canvas.coords(self.polygon, coords)

            elif op["item"] == "polygon":
                self.canvas.move(op["selected"], dx, dy)
                for item in self.nodes:
                    self.canvas.move(item, dx, dy)
                for p in self.points:
                    p[0] += dx
                    p[1] += dy

            else:
                self.canvas.move(op["selected"], dx, dy)
                op_num = int(op["selected"][4:])
                self.points[op_num][0] += dx
                self.points[op_num][1] += dy
                coords = sum(self.points, [])
                self.canvas.coords(self.polygon, coords)

        else:
            print("redo stack is empty")
    
    def on_press_select(self, event):
        if self.multiselected:
            for item in self.multiselected:
                c = self.canvas.coords(item)
                c[0], c[1], c[2], c[3] = c[0]+4, c[1]+4, c[2]-4, c[3]-4
                self.canvas.coords(item, c)
                self.canvas.itemconfig(item, outline='red', fill='red', activeoutline='yellow', activefill='yellow', width=4, activewidth=8)
            self.multiselected = []
        self.last_x = event.x
        self.last_y = event.y
        self.select_box = self.canvas.create_rectangle(event.x, event.y, event.x, event.y, outline='white', width=2)

    def on_move_select(self, event):
        if self.select_box:
            self.canvas.coords(self.select_box, [self.last_x, self.last_y, event.x, event.y])
            enclosed_nodes = self.canvas.find_enclosed(self.last_x, self.last_y, event.x, event.y)
            enclosed_nodes = [self.canvas.gettags(item)[0] for item in enclosed_nodes]
            if 'polygon' in enclosed_nodes:
                enclosed_nodes.remove('polygon')
            for item in enclosed_nodes:
                if item not in self.multiselected:
                    self.multiselected.append(item)
                    c = self.canvas.coords(item)
                    c[0], c[1], c[2], c[3] = c[0]-4, c[1]-4, c[2]+4, c[3]+4
                    self.canvas.coords(item, c)
                    self.canvas.itemconfig(item, outline='yellow', fill='blue', activeoutline='yellow', activefill='blue', width=1, activewidth=1)
            for item in self.multiselected:
                if item not in enclosed_nodes:
                    c = self.canvas.coords(item)
                    c[0], c[1], c[2], c[3] = c[0]+4, c[1]+4, c[2]-4, c[3]-4
                    self.canvas.coords(item, c)
                    self.canvas.itemconfig(item, outline='red', fill='red', activeoutline='yellow', activefill='yellow', width=4, activewidth=8)
                    self.multiselected.remove(item)

    def on_release_select(self, event):
        self.last_x = None
        self.last_y = None
        self.canvas.delete(self.select_box)
        self.select_box = None
    
    def cache_result(self):
        return (self.points, self.undo_stack, self.redo_stack)


def pop_err_win(message, font, winsize=(260, 60)):
    global root
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    err_win_x = screen_width // 2 - winsize[0] // 2
    err_win_y = screen_height // 2 - winsize[1] // 2
    err = tk.Toplevel()
    err.transient(root)
    err.title("错误")
    err.geometry(f"{winsize[0]}x{winsize[1]}+{err_win_x}+{err_win_y}")
    err.resizable(False, False)
    err.attributes("-topmost", True)
    err.grab_set()
    err.focus_set()
    tk.Label(err, text=message, font=font).pack(fill=tk.BOTH, expand=True)
    err.wait_window()
    err.destroy()
    root.destroy()
    raise ValueError(message)

def cvt_tkimages(imgs, scale):
    images = []
    shape = (imgs.shape[0] * scale, imgs.shape[1] * scale)
    img_num = imgs.shape[-1]
    for i in range(img_num):
        img = cv2.resize(imgs[:, :, :, i], shape)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(img)
        img = ImageTk.PhotoImage(img)
        images.append(img)
    return images

def cvt_single_tkimage(img, scale):
    global single_img
    shape = (img.shape[0] * scale, img.shape[1] * scale)
    single_img = cv2.resize(img, shape)
    single_img = cv2.cvtColor(single_img, cv2.COLOR_BGR2RGB)
    single_img = Image.fromarray(single_img)
    single_img = ImageTk.PhotoImage(single_img)

def cvt_tkpolygons(cnts, scale):
    if cnts.shape[1] != 2:
        pop_err_win(f"轮廓数据格式不正确\n期望形状为(点数, 2, 图像数)\n实际为{cnts.shape}", font=("微软雅黑", 10, "bold"), winsize=(300, 80))
    cnts = cnts * scale
    cnts = cnts[:, ::-1, :]
    cnts = cnts.transpose(2, 0, 1)
    cnts = cnts[:, 0:-1, :] # 观察发现最后一个点和第一个点重合 去除减少计算量
    return cnts.tolist()

def save_new_cnts(scale, temp=False):
    global cnts
    global current_image_no
    global curr_contour
    global undo_stack
    global redo_stack
    global img_file_name

    if not temp:
        file = filedialog.asksaveasfile(initialdir=".", initialfile="ACDC_RV_contour_200_new.npy", filetypes=[("npy文件", ".npy"), ("所有文件", ".*")], defaultextension=".npy", title=f"选择保存路径", mode="wb")
        if file:
            (cnts[current_image_no], undo_stack[current_image_no], redo_stack[current_image_no]) = curr_contour.cache_result()
            new_cnts = cnts.copy()
            new_cnts = np.array(new_cnts)
            new_cnts = np.concatenate((new_cnts, np.expand_dims(new_cnts[:, 0, :], axis=1)), axis=1) # 把去除的那个点加回来保证格式与原来的相同
            new_cnts = new_cnts.transpose(1, 2, 0)
            new_cnts = new_cnts[:, ::-1, :]
            new_cnts = np.round(new_cnts / scale, decimals=0)
            np.save(file, new_cnts.astype(np.float64))
            file.close()
            with open("history.txt", "w") as f:
                f.write(f"{img_file_name}\n")
                f.write(f"{file.name}\n")
    else:
        new_cnts = cnts.copy()
        new_cnts = np.array(new_cnts)
        new_cnts = np.concatenate((new_cnts, np.expand_dims(new_cnts[:, 0, :], axis=1)), axis=1)
        new_cnts = new_cnts.transpose(1, 2, 0)
        new_cnts = new_cnts[:, ::-1, :]
        new_cnts = np.round(new_cnts / scale, decimals=0)
        for file in os.listdir("."):
            if file.startswith("~temp"):
                os.remove(file)
        np.save(f"~temp-{current_image_no}.npy", new_cnts.astype(np.float64))

def pop_startup_window(root):
    global img_file_name
    global cnt_file_name
    global current_image_no
    global scale

    def cancel():
        img_file_nameVar.set(None)
        cnt_file_nameVar.set(None)
        ask_filename_win.destroy()
        root.destroy()
    
    def openit():
        global img_file_name
        global cnt_file_name
        img_file_name = img_entry.get()
        cnt_file_name = cnt_entry.get()
        with open("history.txt", "w") as f:
            f.write(f"{img_file_name}\n")
            f.write(f"{cnt_file_name}\n")
        ask_filename_win.destroy()

    def select_file(file_nameVar, title):
        filename = filedialog.askopenfilename(initialdir=".", filetypes=[("npy文件", ".npy"), ("所有文件", ".*")], defaultextension=".npy", title=f"选择{title}")
        if filename:
            file_nameVar.set(filename)

    history_img_file_name = ""
    history_cnt_file_name = ""

    if os.path.exists("history.txt"):
        with open("history.txt", "r") as f:
            history_img_file_name = f.readline().strip()
            history_cnt_file_name = f.readline().strip()

    # 如果存在临时文件则询问是否恢复
    temp_file_list = glob.glob("~temp-*.npy")
    if len(temp_file_list) > 0:
        if messagebox.askyesno("提示", "检测到存在临时文件，是否恢复？\n(若恢复, 则临时文件将保存为正式文件)\n(若不恢复, 则临时文件将被删除)"):
            current_image_no = int(temp_file_list[0].split("-")[-1].split(".")[0])
            restore_name = temp_file_list[0].replace("~temp-", f"{os.path.basename(history_cnt_file_name).split('.')[0]}_temp_").replace('.npy', f"(恢复于{time.strftime('%Y-%m-%d#%H-%M-%S', time.localtime())}).npy")
            os.rename(temp_file_list[0], restore_name)
            history_cnt_file_name = restore_name # 临时文件数量应该只有一个
        else:
            # 理论上来说应该只有一个temp file, 但是谁知道呢, 如果以后这个机制做好了可以优化掉这里的循环, 丑的要死
            for file in temp_file_list:
                os.remove(file)

    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    ask_win_x = screen_width // 2 - 150
    ask_win_y = screen_height // 2 - 60

    ask_filename_win = tk.Toplevel(root)
    ask_filename_win.title("打开文件")
    ask_filename_win.geometry(f"300x120+{ask_win_x}+{ask_win_y}")
    ask_filename_win.resizable(False, False)
    ask_filename_win.attributes("-topmost", True)
    ask_filename_win.grab_set()
    ask_filename_win.focus_set()
    ask_filename_win.transient(root)
    ask_filename_win.protocol("WM_DELETE_WINDOW", lambda: cancel())

    tk.Label(ask_filename_win, text="请输入文件路径").pack()
    img_file_nameVar = tk.StringVar(ask_filename_win, value=f"{history_img_file_name}")
    cnt_file_nameVar = tk.StringVar(ask_filename_win, value=f"{history_cnt_file_name}")
    file_select_frame = tk.Frame(ask_filename_win)
    img_select_frame = tk.Frame(file_select_frame)
    cnt_select_frame = tk.Frame(file_select_frame)
    tk.Label(img_select_frame, text="图像npy").pack(side=tk.LEFT)
    img_entry = tk.Entry(img_select_frame, textvariable=img_file_nameVar, width=20)
    img_select_button = tk.Button(img_select_frame, text="选择文件", height=0, width=7)
    tk.Label(cnt_select_frame, text="轮廓npy").pack(side=tk.LEFT)
    cnt_entry = tk.Entry(cnt_select_frame, textvariable=cnt_file_nameVar, width=20)
    cnt_select_button = tk.Button(cnt_select_frame, text="选择文件", height=0, width=7)
    img_entry.xview_moveto(1)
    cnt_entry.xview_moveto(1)
    img_entry.pack(side=tk.LEFT)
    cnt_entry.pack(side=tk.LEFT)
    img_select_frame.pack()
    cnt_select_frame.pack()
    file_select_frame.pack()

    button_frame = tk.Frame(ask_filename_win)
    place_holder = tk.Label(button_frame, text=" " * 7)
    button_frame.pack()

    open_button = tk.Button(button_frame, text="打开")
    cancel_button = tk.Button(button_frame, text="取消")

    open_button.pack(side=tk.LEFT)
    place_holder.pack(side=tk.LEFT)
    cancel_button.pack(side=tk.RIGHT)
    img_select_button.pack(side=tk.RIGHT)
    cnt_select_button.pack(side=tk.RIGHT)

    open_button.config(command=lambda:openit())
    cancel_button.config(command=lambda:cancel())
    img_select_button.config(command=lambda:select_file(img_file_nameVar, "图像npy"))
    cnt_select_button.config(command=lambda:select_file(cnt_file_nameVar, "轮廓npy"))
    ask_filename_win.wait_window()


if __name__ == "__main__":

    single_img = None

    img_file_name = None
    cnt_file_name = None
    current_image_no = 0
    scale = 10

    root = tk.Tk()
    pop_startup_window(root)
    if img_file_name is None or cnt_file_name is None:
        print("未选择文件，程序退出")
        exit(0)
    print("正在读取数据...")
    images = np.load(img_file_name).astype(np.uint8)
    contours = np.load(cnt_file_name).astype(np.uint16)

    print("正在创建画板...")
    images_shape = images.shape
    canvas_width = images_shape[0] * scale
    canvas_height = images_shape[1] * scale
    image_no = images_shape[-1]
    undo_stack = [[] for _ in range(image_no)]
    redo_stack = [[] for _ in range(image_no)]
    root.title(f"标签编辑器 - {current_image_no} / {image_no - 1}")
    canvas = tk.Canvas(root, bg="white", width=canvas_width, height=canvas_height)

    button_frame = tk.Frame(root)
    place_holder1 = tk.Label(button_frame, text=" " * 5)
    place_holder2 = tk.Label(button_frame, text=" " * 5)
    button_frame.pack(fill=tk.BOTH)
    jump_num = tk.Entry(button_frame)
    jump_button =tk.Button(button_frame, text="跳转")
    prev_image_button = tk.Button(button_frame, text="前一张")
    next_image_button = tk.Button(button_frame, text="后一张")
    save_button = tk.Button(button_frame, text="保存", width=10)
    place_holder1.pack(side=tk.LEFT, anchor=tk.CENTER)
    jump_num.pack(side=tk.LEFT, anchor=tk.W)
    jump_button.pack(side=tk.LEFT, anchor=tk.W)
    prev_image_button.pack(side=tk.LEFT, anchor=tk.CENTER)
    next_image_button.pack(side=tk.LEFT, anchor=tk.CENTER)
    place_holder2.pack(side=tk.RIGHT, anchor=tk.CENTER)
    save_button.pack(side=tk.RIGHT, anchor=tk.E)
    canvas.pack()


    print("正在转换数据...")
    cvt_single_tkimage(images[:, :, :, current_image_no], scale=scale)
    cnts = cvt_tkpolygons(contours, scale=scale)
    if len(cnts) != image_no:
        pop_err_win(f"轮廓数据与图像数量不一致\n轮廓数据数量为{len(cnts)}\n图像数量为{image_no}", font=("微软雅黑", 10, "bold"), winsize=(300, 80))
    print("完成，正在启动编辑器...")
    canvas.create_image(0, 0, anchor=tk.NW, image=single_img)
    curr_contour = Contour(canvas, cnts[current_image_no], undo_stack[current_image_no], redo_stack[current_image_no])
    
    def change_image(new_no):
        global current_image_no
        global curr_contour
        (cnts[current_image_no], undo_stack[current_image_no], redo_stack[current_image_no]) = curr_contour.cache_result()
        save_new_cnts(scale=scale, temp=True)
        current_image_no = new_no
        if current_image_no >= image_no:
            current_image_no = 0
        if current_image_no < 0:
            current_image_no = image_no - 1
        root.title(f"标签编辑器 - {current_image_no} / {image_no - 1}")
        canvas.delete("all")
        cvt_single_tkimage(images[:, :, :, current_image_no], scale=scale)
        canvas.create_image(0, 0, anchor=tk.NW, image=single_img)
        curr_contour = Contour(canvas, cnts[current_image_no], undo_stack[current_image_no], redo_stack[current_image_no])

    def jump_image():
        global jump_num
        new_image_no = jump_num.get()
        if new_image_no.isdigit():
            new_image_no = int(new_image_no)
            if new_image_no >= image_no:
                new_image_no = image_no - 1
                jump_num.delete(0, "end")
                jump_num.insert(0, str(new_image_no))
            if new_image_no < 0:
                new_image_no = 0
                jump_num.delete(0, "end")
                jump_num.insert(0, str(new_image_no))
            change_image(new_image_no)
        else:
            jump_num.delete(0, "end")
    
    def clear_temp_files():
        for file in os.listdir("."):
            if file.startswith("~temp"):
                os.remove(file)

    jump_button.config(command=lambda:jump_image())
    prev_image_button.config(command=lambda:change_image(current_image_no-1))
    next_image_button.config(command=lambda:change_image(current_image_no+1))
    save_button.config(command=lambda:save_new_cnts(scale=scale))
    root.bind("<Left>", lambda e:change_image(current_image_no-1))
    root.bind("<Right>", lambda e:change_image(current_image_no+1))
    root.bind("<Control-s>", lambda e:save_new_cnts(scale=scale))
    root.bind("<Control-S>", lambda e:save_new_cnts(scale=scale))
    root.bind("<Return>", lambda e:jump_image())
    root.bind("<Destroy>", lambda e:clear_temp_files())
    root.mainloop()
