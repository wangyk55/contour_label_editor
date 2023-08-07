import tkinter as tk

import cv2
import numpy as np
from PIL import Image, ImageTk


class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y
    
    def coord(self):
        return [self.x, self.y]

class Contour:
    def __init__(self, canvas, points, undo_stack=[], redo_stack=[]):
        self.undo_stack = undo_stack
        self.redo_stack = redo_stack
        self.last_x = None
        self.last_y = None
        self.selected = None

        self.points = []
        for p in points:
            self.points.append(Point(p[0], p[1]))

        # polygon
        self.polygon = canvas.create_polygon([p.coord() for p in self.points], outline="mediumseagreen", fill="", width=3, tags="polygon", activeoutline='lime', activefill='')
        canvas.tag_bind(self.polygon, '<ButtonPress-1>',   lambda event, tag="polygon": self.on_press_tag(event, 0, tag))
        canvas.tag_bind(self.polygon, '<ButtonRelease-1>', lambda event, tag="polygon": self.on_release_tag(event, 0, tag))
        canvas.tag_bind(self.polygon, '<B1-Motion>', self.on_move_polygon)

        # nodes - red rectangles
        self.nodes = []
        for number, point in enumerate([p.coord() for p in self.points]):
            x, y = point
            node = canvas.create_rectangle((x, y, x, y), outline='red', fill='red', width=4, tags=f"node{number}", activeoutline='yellow', activefill='yellow', activewidth=8)
            self.nodes.append(node)
            canvas.tag_bind(node, '<ButtonPress-1>',   lambda event, number=number, tag=f"node{number}": self.on_press_tag(event, number, tag))
            canvas.tag_bind(node, '<ButtonRelease-1>', lambda event, number=number, tag=f"node{number}": self.on_release_tag(event, number, tag))
            canvas.tag_bind(node, '<B1-Motion>', lambda event, number=number: self.on_move_node(event, number))

        # 绑定大小写z键来undo
        canvas.bind_all("<Control-z>", self.undo)
        canvas.bind_all("<Control-Z>", self.undo)
        # 绑定大小写y键来redo
        canvas.bind_all("<Control-y>", self.redo)
        canvas.bind_all("<Control-Y>", self.redo)
    
    def on_press_tag(self, event, number, tag):
        self.selected = tag
        self.last_x = event.x
        self.last_y = event.y
        self.undo_stack.append({"selected": self.selected, "number": number, "prev_x": event.x, "prev_y": event.y})
        if number == 0:
            self.undo_stack[-1]["item"] = "polygon"
        else:
            self.undo_stack[-1]["item"] = "node"

    def on_release_tag(self, event, number, tag):
        self.selected = None
        self.last_x = None
        self.last_y = None
        self.undo_stack[-1]["curr_x"] = event.x
        self.undo_stack[-1]["curr_y"] = event.y

    def on_move_node(self, event, number):
        '''move single node in polygon'''
        if self.selected:
            dx = event.x - self.last_x
            dy = event.y - self.last_y

            canvas.move(self.selected, dx, dy)
            self.points[number].x += dx
            self.points[number].y += dy

            coords = sum([p.coord() for p in self.points], [])
            canvas.coords(self.polygon, coords)

            self.last_x = event.x
            self.last_y = event.y

    def on_move_polygon(self, event):
        '''move polygon and red rectangles in nodes'''
        if self.selected:
            dx = event.x - self.last_x
            dy = event.y - self.last_y

            # move polygon
            canvas.move(self.selected, dx, dy)

            # move red nodes 
            for item in self.nodes:
                canvas.move(item, dx, dy)

            # recalculate values in self.points
            for item in self.points:
                item.x += dx
                item.y += dy

            self.last_x = event.x
            self.last_y = event.y

    def undo(self, e):
        if self.undo_stack:
            op = self.undo_stack.pop()
            self.redo_stack.append(op)
            dx = op["prev_x"] - op["curr_x"]
            dy = op["prev_y"] - op["curr_y"]
            canvas.move(op["selected"], dx, dy)
            if op["item"] == "polygon":
                for item in self.nodes:
                    canvas.move(item, dx, dy)
                for p in self.points:
                    p.x += dx
                    p.y += dy
            else:
                self.points[op["number"]].x += dx
                self.points[op["number"]].y += dy
                coords = sum([p.coord() for p in self.points], [])
                canvas.coords(self.polygon, coords)
        else:
            print("undo stack is empty")


    def redo(self, e):
        if self.redo_stack:
            op = self.redo_stack.pop()
            self.undo_stack.append(op)
            dx = op["curr_x"] - op["prev_x"]
            dy = op["curr_y"] - op["prev_y"]
            canvas.move(op["selected"], dx, dy)
            if op["item"] == "polygon":
                for item in self.nodes:
                    canvas.move(item, dx, dy)
                for p in self.points:
                    p.x += dx
                    p.y += dy
            else:
                self.points[op["number"]].x += dx
                self.points[op["number"]].y += dy
                coords = sum([p.coord() for p in self.points], [])
                canvas.coords(self.polygon, coords)
        else:
            print("redo stack is empty")
    
    def cache_result(self):
        return ([[p.x, p.y] for p in self.points], self.undo_stack, self.redo_stack)


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

def cvt_tkpolygons(cnts, scale):
    cnts = cnts * scale
    cnts = cnts[:, ::-1, :]
    cnts = cnts.transpose(2, 0, 1)
    return cnts.tolist()

def save_new_cnts(scale):
    global root
    global cnts
    global current_image_no
    global curr_contour
    global undo_stack
    global redo_stack

    def cancel():
        ask_win.destroy()
    
    def saveit(file_name):
        (cnts[current_image_no], undo_stack[current_image_no], redo_stack[current_image_no]) = curr_contour.cache_result()
        new_cnts = cnts.copy()
        new_cnts = np.array(new_cnts)
        new_cnts = new_cnts.transpose(1, 2, 0)
        new_cnts = new_cnts[:, ::-1, :]
        new_cnts = new_cnts // scale
        np.save(file_name, new_cnts.astype(np.float64))
        ask_win.destroy()

    root_x = root.winfo_x()
    root_y = root.winfo_y()
    root_width = root.winfo_width()
    root_height = root.winfo_height()
    ask_win_x = root_x + root_width // 2 - 150
    ask_win_y = root_y + root_height // 2 - 50

    ask_win = tk.Toplevel(root)
    ask_win.title("保存")
    ask_win.geometry(f"300x100+{ask_win_x}+{ask_win_y}")
    ask_win.resizable(False, False)
    ask_win.attributes("-topmost", True)
    ask_win.grab_set()
    ask_win.focus_set()
    ask_win.transient(root)
    ask_win.protocol("WM_DELETE_WINDOW", lambda: cancel())

    tk.Label(ask_win, text="请输入文件名").pack()
    file_name = tk.StringVar(ask_win, value=f"ACDC_RV_contour_200_new.npy")
    tk.Entry(ask_win, textvariable=file_name, width=30).pack()

    button_frame = tk.Frame(ask_win)
    place_holder = tk.Label(button_frame, text=" " * 7)
    button_frame.pack()

    save_button = tk.Button(button_frame, text="保存")
    cancel_button = tk.Button(button_frame, text="取消")

    save_button.pack(side=tk.LEFT)
    place_holder.pack(side=tk.LEFT)
    cancel_button.pack(side=tk.RIGHT)

    save_button.config(command=lambda:saveit(file_name.get()))
    cancel_button.config(command=lambda:cancel())
    ask_win.wait_window()


if __name__ == "__main__":

    images = np.load("ACDC_RV_images_128.npy").astype(np.uint8)
    contours = np.load("ACDC_RV_contour_200.npy").astype(np.uint16)
    images_shape = images.shape

    print("正在创建画板...")
    root = tk.Tk()
    scale = 10
    canvas_width = images_shape[0] * scale
    canvas_height = images_shape[1] * scale
    image_no = images_shape[-1]
    undo_stack = [[] for _ in range(image_no)]
    redo_stack = [[] for _ in range(image_no)]
    current_image_no = 0
    root.title(f"标签编辑器 - {current_image_no + 1} / {image_no}")
    canvas = tk.Canvas(root, bg="white", width=canvas_width, height=canvas_height)

    button_frame = tk.Frame(root)
    place_holder = tk.Label(button_frame, text=" " * 10)
    button_frame.pack()
    prev_image_button = tk.Button(button_frame, text="前一张")
    next_image_button = tk.Button(button_frame, text="后一张")
    save_button = tk.Button(button_frame, text="保存")
    prev_image_button.pack(side=tk.LEFT)
    next_image_button.pack(side=tk.LEFT)
    place_holder.pack(side=tk.LEFT)
    save_button.pack(side=tk.RIGHT)

    print("正在转换数据...")
    imgs = cvt_tkimages(images, scale=scale)
    cnts = cvt_tkpolygons(contours, scale=scale)
    canvas.pack()
    canvas.create_image(0, 0, anchor=tk.NW, image=imgs[current_image_no])
    curr_contour = Contour(canvas, cnts[current_image_no], undo_stack[current_image_no], redo_stack[current_image_no])
    
    def change_image(next_no):
        global current_image_no
        global curr_contour
        (cnts[current_image_no], undo_stack[current_image_no], redo_stack[current_image_no]) = curr_contour.cache_result()
        current_image_no = next_no + current_image_no
        if current_image_no >= image_no:
            current_image_no = 0
        if current_image_no < 0:
            current_image_no = image_no - 1
        root.title(f"标签编辑器 - {current_image_no + 1} / {image_no}")
        canvas.delete("all")
        canvas.create_image(0, 0, anchor=tk.NW, image=imgs[current_image_no])
        curr_contour = Contour(canvas, cnts[current_image_no], undo_stack[current_image_no], redo_stack[current_image_no])

    prev_image_button.config(command=lambda:change_image(-1))
    next_image_button.config(command=lambda:change_image(1))
    save_button.config(command=lambda:save_new_cnts(scale=scale))
    root.bind("<Left>", lambda e:change_image(-1))
    root.bind("<Right>", lambda e:change_image(1))
    root.bind("<Control-s>", lambda e:save_new_cnts(scale=scale))
    root.bind("<Control-S>", lambda e:save_new_cnts(scale=scale))
    root.mainloop()
