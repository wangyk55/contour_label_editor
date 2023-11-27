import tkinter as tk

import os
import cv2
import numpy as np
from PIL import Image, ImageTk
from tkinter import filedialog, messagebox
from ai_module import generate_contour, read_and_preprocess, prepare_model


class Contour:
    def __init__(self, canvas, points, undo_stack=[], redo_stack=[]):
        global append_mode
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

        # the difference between points and nodes is that points saves the coordinates of the points, nodes is the id of the points
        self.points = points.tolist()
        self.max_node_index = len(self.points) - 1
        self.tag_index = {}

        # polygon
        if len(self.points) > 1:
            self.polygon = self.canvas.create_polygon(self.points, outline="mediumseagreen", fill="", width=3, tags="polygon", activeoutline='lime', activefill='')
            self.canvas.tag_bind(self.polygon, '<ButtonPress-1>',   lambda event, tag="polygon": self.on_press_tag(event, tag))
            self.canvas.tag_bind(self.polygon, '<ButtonRelease-1>', lambda event, tag="polygon": self.on_release_tag(event, tag))
            self.canvas.tag_bind(self.polygon, '<B1-Motion>', self.on_move_polygon)
            self.canvas.tag_bind(self.polygon, '<Alt-ButtonPress-1>', self.do_nothing)
            # self.canvas.tag_bind(self.polygon, '<Alt-ButtonRelease-1>', self.do_nothing)
            self.canvas.tag_bind(self.polygon, '<Control-ButtonPress-1>', self.do_nothing)
            # self.canvas.tag_bind(self.polygon, '<Control-ButtonRelease-1>', self.do_nothing)
            self.canvas.tag_bind(self.polygon, '<Shift-ButtonPress-1>', self.do_nothing)

        # nodes
        for number, point in enumerate(self.points):
            tag_of_this_node = f"node{number}"
            self.tag_index[tag_of_this_node] = number
            x, y = point
            _ = self.canvas.create_rectangle((x, y, x, y), outline='red', fill='red', width=4, tags=tag_of_this_node, activeoutline='yellow', activefill='yellow', activewidth=8)
            self.canvas.tag_bind(tag_of_this_node, '<ButtonPress-1>',   lambda event, tag=tag_of_this_node: self.on_press_tag(event, tag))
            self.canvas.tag_bind(tag_of_this_node, '<ButtonRelease-1>', lambda event, tag=tag_of_this_node: self.on_release_tag(event, tag))
            self.canvas.tag_bind(tag_of_this_node, '<Control-ButtonPress-1>',   lambda event, tag=tag_of_this_node: self.on_press_tag_multi(event, tag))
            # self.canvas.tag_bind(node, '<Control-ButtonRelease-1>', self.do_nothing)
            self.canvas.tag_bind(tag_of_this_node, '<Alt-ButtonPress-1>', self.do_nothing)
            # self.canvas.tag_bind(node, '<Alt-ButtonRelease-1>', self.do_nothing)
            self.canvas.tag_bind(tag_of_this_node, '<B1-Motion>', lambda event, tag=tag_of_this_node: self.on_move_node(event, tag))
            # self.canvas.tag_bind(node, '<Control-B1-Motion>', self.do_nothing)
            self.canvas.tag_bind(tag_of_this_node, '<Shift-ButtonPress-1>', self.do_nothing)

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
        # Delete键删除
        self.canvas.bind_all("<Delete>", self.delete_node)
        # 按住shift键添加节点
        self.canvas.bind_all("<Shift-ButtonPress-1>", self.add_node)

    def on_press_tag(self, event, tag):
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

    def on_release_tag(self, event, tag):
        if not self.select_box:
            if self.node_selected_flag or self.polygon_selected_flag:
                self.selected = None
                self.last_x = None
                self.last_y = None
                self.undo_stack[-1]["curr_x"] = event.x
                self.undo_stack[-1]["curr_y"] = event.y
                self.redo_stack = []
            self.node_selected_flag = False
            self.polygon_selected_flag = False

    def on_press_tag_multi(self, event, tag):
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
        for item in self.tag_index.keys():
            self.canvas.itemconfigure(item, state='hidden')
    
    def show_polygon(self, e):
        self.canvas.itemconfigure(self.polygon, state='normal')
        for item in self.tag_index.keys():
            self.canvas.itemconfigure(item, state='normal')

    def on_move_node(self, event, tag):
        '''move single/multi node in polygon'''
        if not self.node_selected_flag:
            return
        if self.multiselected:
            dx = event.x - self.last_x
            dy = event.y - self.last_y

            for tag in self.multiselected:
                self.canvas.move(tag, dx, dy)
                self.points[self.tag_index[tag]][0] += dx
                self.points[self.tag_index[tag]][1] += dy

        elif self.selected:
            dx = event.x - self.last_x
            dy = event.y - self.last_y

            self.canvas.move(self.selected, dx, dy)
            self.points[self.tag_index[tag]][0] += dx
            self.points[self.tag_index[tag]][1] += dy
        
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
            for item in self.tag_index.keys():
                self.canvas.move(item, dx, dy)

            # recalculate values in self.points
            for item in self.points:
                item[0] += dx
                item[1] += dy

            self.last_x = event.x
            self.last_y = event.y

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

    def add_node(self, e):
        if append_mode:
            if len(self.points) < 3:
                if len(self.points) == 2:
                    self.points.append([e.x, e.y])
                    tag = f"node{self.max_node_index + 1}"
                    self.tag_index[tag] = len(self.points) - 1
                    _ = self.canvas.create_rectangle((e.x, e.y, e.x, e.y), outline='red', fill='red', width=4, tags=tag, activeoutline='yellow', activefill='yellow', activewidth=8)
                    self.canvas.tag_bind(tag, '<ButtonPress-1>',   lambda event, tag=tag: self.on_press_tag(event, tag))
                    self.canvas.tag_bind(tag, '<ButtonRelease-1>', lambda event, tag=tag: self.on_release_tag(event, tag))
                    self.canvas.tag_bind(tag, '<Control-ButtonPress-1>',   lambda event, tag=tag: self.on_press_tag_multi(event, tag))
                    self.canvas.tag_bind(tag, '<Alt-ButtonPress-1>', self.do_nothing)
                    self.canvas.tag_bind(tag, '<B1-Motion>', lambda event, tag=tag: self.on_move_node(event, tag))
                    self.canvas.tag_bind(tag, '<Shift-ButtonPress-1>', self.do_nothing)
                    self.max_node_index += 1
                    coords = sum(self.points, [])
                    self.canvas.coords(self.polygon, coords)
                    self.undo_stack.append({"selected": tag, "item": "add", "index": len(self.points) - 1, "x": e.x, "y": e.y})
                    self.redo_stack = []
                if len(self.points) == 1:
                    first_node_tag = list(self.tag_index.keys())[0]
                    self.points.append([e.x, e.y])
                    tag = f"node{self.max_node_index + 1}"
                    self.tag_index[tag] = len(self.points) - 1
                    self.max_node_index += 1
                    coords = sum(self.points, [])
                    # 这时候有polgon?不知道两个点能不能显示, 按道理三个才行
                    self.polygon = self.canvas.create_polygon(self.points, outline="mediumseagreen", fill="", width=3, tags="polygon", activeoutline='lime', activefill='')
                    self.canvas.lower("polygon", first_node_tag)
                    _ = self.canvas.create_rectangle((e.x, e.y, e.x, e.y), outline='red', fill='red', width=4, tags=tag, activeoutline='yellow', activefill='yellow', activewidth=8)
                    self.canvas.tag_bind(tag, '<ButtonPress-1>',   lambda event, tag=tag: self.on_press_tag(event, tag))
                    self.canvas.tag_bind(tag, '<ButtonRelease-1>', lambda event, tag=tag: self.on_release_tag(event, tag))
                    self.canvas.tag_bind(tag, '<Control-ButtonPress-1>',   lambda event, tag=tag: self.on_press_tag_multi(event, tag))
                    self.canvas.tag_bind(tag, '<Alt-ButtonPress-1>', self.do_nothing)
                    self.canvas.tag_bind(tag, '<B1-Motion>', lambda event, tag=tag: self.on_move_node(event, tag))
                    self.canvas.tag_bind(tag, '<Shift-ButtonPress-1>', self.do_nothing)

                    self.canvas.tag_bind(self.polygon, '<ButtonPress-1>',   lambda event, tag="polygon": self.on_press_tag(event, tag))
                    self.canvas.tag_bind(self.polygon, '<ButtonRelease-1>', lambda event, tag="polygon": self.on_release_tag(event, tag))
                    self.canvas.tag_bind(self.polygon, '<B1-Motion>', self.on_move_polygon)
                    self.canvas.tag_bind(self.polygon, '<Alt-ButtonPress-1>', self.do_nothing)
                    # self.canvas.tag_bind(self.polygon, '<Alt-ButtonRelease-1>', self.do_nothing)
                    self.canvas.tag_bind(self.polygon, '<Control-ButtonPress-1>', self.do_nothing)
                    # self.canvas.tag_bind(self.polygon, '<Control-ButtonRelease-1>', self.do_nothing)
                    self.canvas.tag_bind(self.polygon, '<Shift-ButtonPress-1>', self.do_nothing)
                    self.undo_stack.append({"selected": tag, "item": "add", "index": len(self.points) - 1, "x": e.x, "y": e.y})
                    self.redo_stack = []
                if len(self.points) == 0:
                    self.points.append([e.x, e.y])
                    tag = f"node{self.max_node_index + 1}"
                    self.tag_index[tag] = len(self.points) - 1
                    self.max_node_index += 1
                    _ = self.canvas.create_rectangle((e.x, e.y, e.x, e.y), outline='red', fill='red', width=4, tags=tag, activeoutline='yellow', activefill='yellow', activewidth=8)
                    self.canvas.tag_bind(tag, '<ButtonPress-1>',   lambda event, tag=tag: self.on_press_tag(event, tag))
                    self.canvas.tag_bind(tag, '<ButtonRelease-1>', lambda event, tag=tag: self.on_release_tag(event, tag))
                    self.canvas.tag_bind(tag, '<Control-ButtonPress-1>',   lambda event, tag=tag: self.on_press_tag_multi(event, tag))
                    self.canvas.tag_bind(tag, '<Alt-ButtonPress-1>', self.do_nothing)
                    self.canvas.tag_bind(tag, '<B1-Motion>', lambda event, tag=tag: self.on_move_node(event, tag))
                    self.canvas.tag_bind(tag, '<Shift-ButtonPress-1>', self.do_nothing)
                    self.undo_stack.append({"selected": tag, "item": "add", "index": len(self.points) - 1, "x": e.x, "y": e.y})
                    self.redo_stack = []

            else:
                if len(self.points) == 199:
                    messagebox.showinfo("提示", "点数已达上限(200)")
                    return
                self.points.append([e.x, e.y])
                tag = f"node{self.max_node_index + 1}"
                self.tag_index[tag] = len(self.points) - 1
                _ = self.canvas.create_rectangle((e.x, e.y, e.x, e.y), outline='red', fill='red', width=4, tags=tag, activeoutline='yellow', activefill='yellow', activewidth=8)
                self.canvas.tag_bind(tag, '<ButtonPress-1>',   lambda event, tag=tag: self.on_press_tag(event, tag))
                self.canvas.tag_bind(tag, '<ButtonRelease-1>', lambda event, tag=tag: self.on_release_tag(event, tag))
                self.canvas.tag_bind(tag, '<Control-ButtonPress-1>',   lambda event, tag=tag: self.on_press_tag_multi(event, tag))
                self.canvas.tag_bind(tag, '<Alt-ButtonPress-1>', self.do_nothing)
                self.canvas.tag_bind(tag, '<B1-Motion>', lambda event, tag=tag: self.on_move_node(event, tag))
                self.canvas.tag_bind(tag, '<Shift-ButtonPress-1>', self.do_nothing)
                self.max_node_index += 1
                coords = sum(self.points, [])
                self.canvas.coords(self.polygon, coords)
                self.undo_stack.append({"selected": tag, "item": "add", "index": len(self.points) - 1, "x": e.x, "y": e.y})
                self.redo_stack = []

        elif len(self.points) > 2:
            if len(self.points) == 199:
                messagebox.showinfo("提示", "点数已达上限(200)")
                return
            closest_item = self.canvas.gettags(self.canvas.find_closest(e.x, e.y, halo=50))
            if closest_item[0].startswith("node"):
                # 在self.points里, 这个closest_item[0]对应的点的index是
                closest_node_index = self.tag_index[closest_item[0]]
                # 前后两个点的index是closest_node_index +- 1, 如果遇到边界要特殊处理
                closest_node_prev_index = closest_node_index - 1 if closest_node_index > 0 else len(self.points) - 1
                closest_node_next_index = closest_node_index + 1 if closest_node_index < len(self.points) - 1 else 0
                # 从鼠标出发, 计算到最近点和前后点的向量
                closest_node_vector = np.array([self.points[closest_node_index][0] - e.x, self.points[closest_node_index][1] - e.y])
                closest_node_prev_vector = np.array([self.points[closest_node_prev_index][0] - e.x, self.points[closest_node_prev_index][1] - e.y])
                closest_node_next_vector = np.array([self.points[closest_node_next_index][0] - e.x, self.points[closest_node_next_index][1] - e.y])
                # 计算closest_node_vector和另外两个向量的夹角余弦值
                closest_node_prev_cos = np.dot(closest_node_vector, closest_node_prev_vector) / (np.linalg.norm(closest_node_vector) * np.linalg.norm(closest_node_prev_vector))
                closest_node_next_cos = np.dot(closest_node_vector, closest_node_next_vector) / (np.linalg.norm(closest_node_vector) * np.linalg.norm(closest_node_next_vector))
                # 选择夹角较小的那两个向量对应的点, 在self.points中它们两个点之间插入鼠标位置作为一个新点
                insert_next_index = closest_node_index if closest_node_prev_cos < closest_node_next_cos else closest_node_next_index
                
                self.points.insert(insert_next_index, [e.x, e.y])
                for key in self.tag_index.keys():
                    if self.tag_index[key] >= insert_next_index:
                        self.tag_index[key] += 1
                tag = f"node{self.max_node_index + 1}"
                self.tag_index[tag] = insert_next_index
                _ = self.canvas.create_rectangle((e.x, e.y, e.x, e.y), outline='red', fill='red', width=4, tags=tag, activeoutline='yellow', activefill='yellow', activewidth=8)
                self.canvas.tag_bind(tag, '<ButtonPress-1>',   lambda event, tag=tag: self.on_press_tag(event, tag))
                self.canvas.tag_bind(tag, '<ButtonRelease-1>', lambda event, tag=tag: self.on_release_tag(event, tag))
                self.canvas.tag_bind(tag, '<Control-ButtonPress-1>',   lambda event, tag=tag: self.on_press_tag_multi(event, tag))
                self.canvas.tag_bind(tag, '<Alt-ButtonPress-1>', self.do_nothing)
                self.canvas.tag_bind(tag, '<B1-Motion>', lambda event, tag=tag: self.on_move_node(event, tag))
                self.canvas.tag_bind(tag, '<Shift-ButtonPress-1>', self.do_nothing)
                self.max_node_index += 1
                
                coords = sum(self.points, [])
                self.canvas.coords(self.polygon, coords)
                self.undo_stack.append({"selected": tag, "item": "add", "index": insert_next_index, "x": e.x, "y": e.y})
                self.redo_stack = []

    def delete_node(self, e):
        if self.multiselected:
            deleted_tag_index = {}
            deleted_tag_x = {}
            deleted_tag_y = {}
            sorted_selected_tags = sorted({tag: self.tag_index[tag] for tag in self.multiselected}.items(), key=lambda x: x[1], reverse=True)
            self.undo_stack.append({"selected": self.multiselected.copy(), "item": "delete"})
            self.redo_stack = []
            for tag, index in sorted_selected_tags:
                deleted_tag_x[tag] = self.points[index][0]
                deleted_tag_y[tag] = self.points[index][1]
                self.canvas.delete(tag)
                self.points.pop(index)
                # tag_index中index大于tag_index[tag]的都要减一
                for key in self.tag_index.keys():
                    if self.tag_index[key] > index:
                        self.tag_index[key] -= 1
                deleted_tag_index[tag] = index
                self.tag_index.pop(tag)
            self.undo_stack[-1]["index"] = deleted_tag_index
            self.undo_stack[-1]["x"] = deleted_tag_x
            self.undo_stack[-1]["y"] = deleted_tag_y
            self.multiselected = []
            if len(self.points) > 1:
                self.canvas.coords(self.polygon, sum(self.points, []))
            if len(self.points) <= 1:
                self.canvas.delete(self.polygon)
                self.polygon = None

    def undo(self, e):
        if self.undo_stack:
            op = self.undo_stack.pop()
            self.redo_stack.append(op)
            if not (op["item"] == "delete" or op["item"] == "add"):
                dx = op["prev_x"] - op["curr_x"]
                dy = op["prev_y"] - op["curr_y"]
            if op["item"] == "multinode":
                for tag in op["selected"]:
                    self.canvas.move(tag, dx, dy)
                    self.points[self.tag_index[tag]][0] += dx
                    self.points[self.tag_index[tag]][1] += dy
                    coords = sum(self.points, [])
                    self.canvas.coords(self.polygon, coords)

            elif op["item"] == "polygon":
                self.canvas.move(op["selected"], dx, dy)
                for item in self.tag_index.keys():
                    self.canvas.move(item, dx, dy)
                for p in self.points:
                    p[0] += dx
                    p[1] += dy

            elif op["item"] == "node":
                self.canvas.move(op["selected"], dx, dy)
                tag = op["selected"]
                self.points[self.tag_index[tag]][0] += dx
                self.points[self.tag_index[tag]][1] += dy
                coords = sum(self.points, [])
                self.canvas.coords(self.polygon, coords)
            
            elif op["item"] == "delete":
                sorted_selected_tags = sorted(op["index"].items(), key=lambda x: x[1])
                if len(self.points) == 0:
                    first_node_tag = sorted_selected_tags[0][0]
                if len(self.points) == 1:
                    first_node_tag = list(self.tag_index.keys())[0]
                for tag, index in sorted_selected_tags:
                    self.points.insert(index, [op["x"][tag], op["y"][tag]])
                    for key in self.tag_index.keys():
                        if self.tag_index[key] >= index:
                            self.tag_index[key] += 1
                    self.tag_index[tag] = index
                    _ = self.canvas.create_rectangle((op["x"][tag], op["y"][tag], op["x"][tag], op["y"][tag]), outline='red', fill='red', width=4, tags=tag, activeoutline='yellow', activefill='yellow', activewidth=8)
                    self.canvas.tag_bind(tag, '<ButtonPress-1>',   lambda event, tag=tag: self.on_press_tag(event, tag))
                    self.canvas.tag_bind(tag, '<ButtonRelease-1>', lambda event, tag=tag: self.on_release_tag(event, tag))
                    self.canvas.tag_bind(tag, '<Control-ButtonPress-1>',   lambda event, tag=tag: self.on_press_tag_multi(event, tag))
                    self.canvas.tag_bind(tag, '<Alt-ButtonPress-1>', self.do_nothing)
                    self.canvas.tag_bind(tag, '<B1-Motion>', lambda event, tag=tag: self.on_move_node(event, tag))
                    self.canvas.tag_bind(tag, '<Shift-ButtonPress-1>', self.do_nothing)
                if not self.polygon and len(self.points) > 1:
                    self.polygon = self.canvas.create_polygon(self.points, outline="mediumseagreen", fill="", width=3, tags="polygon", activeoutline='lime', activefill='')
                    self.canvas.lower("polygon", first_node_tag)
                    self.canvas.tag_bind(self.polygon, '<ButtonPress-1>',   lambda event, tag="polygon": self.on_press_tag(event, tag))
                    self.canvas.tag_bind(self.polygon, '<ButtonRelease-1>', lambda event, tag="polygon": self.on_release_tag(event, tag))
                    self.canvas.tag_bind(self.polygon, '<B1-Motion>', self.on_move_polygon)
                    self.canvas.tag_bind(self.polygon, '<Alt-ButtonPress-1>', self.do_nothing)
                    # self.canvas.tag_bind(self.polygon, '<Alt-ButtonRelease-1>', self.do_nothing)
                    self.canvas.tag_bind(self.polygon, '<Control-ButtonPress-1>', self.do_nothing)
                    # self.canvas.tag_bind(self.polygon, '<Control-ButtonRelease-1>', self.do_nothing)
                    self.canvas.tag_bind(self.polygon, '<Shift-ButtonPress-1>', self.do_nothing)
                if len(self.points) > 2:
                    self.canvas.coords(self.polygon, sum(self.points, []))
            
            elif op["item"] == "add":
                tag = op["selected"]
                self.canvas.delete(tag)
                self.points.pop(op["index"])
                for key in self.tag_index.keys():
                    if self.tag_index[key] > op["index"]:
                        self.tag_index[key] -= 1
                self.tag_index.pop(tag)
                if len(self.points) > 1:
                    self.canvas.coords(self.polygon, sum(self.points, []))
                if len(self.points) == 1:
                    self.canvas.delete(self.polygon)
                    self.polygon = None

        else:
            print("undo stack is empty")

    def redo(self, e):
        if self.redo_stack:
            op = self.redo_stack.pop()
            self.undo_stack.append(op)
            if not (op["item"] == "delete" or op["item"] == "add"):
                dx = op["curr_x"] - op["prev_x"]
                dy = op["curr_y"] - op["prev_y"]
            if op["item"] == "multinode":
                for tag in op["selected"]:
                    self.canvas.move(tag, dx, dy)
                    self.points[self.tag_index[tag]][0] += dx
                    self.points[self.tag_index[tag]][1] += dy
                    coords = sum(self.points, [])
                    self.canvas.coords(self.polygon, coords)

            elif op["item"] == "polygon":
                self.canvas.move(op["selected"], dx, dy)
                for item in self.tag_index.keys():
                    self.canvas.move(item, dx, dy)
                for p in self.points:
                    p[0] += dx
                    p[1] += dy

            elif op["item"] == "node":
                tag = op["selected"]
                self.canvas.move(tag, dx, dy)
                self.points[self.tag_index[tag]][0] += dx
                self.points[self.tag_index[tag]][1] += dy
                coords = sum(self.points, [])
                self.canvas.coords(self.polygon, coords)
            
            elif op["item"] == "delete":
                sorted_selected_tags = sorted(op["index"].items(), key=lambda x: x[1], reverse=True)
                for tag, index in sorted_selected_tags:
                    self.canvas.delete(tag)
                    self.points.pop(index)
                    for key in self.tag_index.keys():
                        if self.tag_index[key] > index:
                            self.tag_index[key] -= 1
                    self.tag_index.pop(tag)
                if len(self.points) > 1:
                    self.canvas.coords(self.polygon, sum(self.points, []))
                if len(self.points) <= 1:
                    self.canvas.delete(self.polygon)
                    self.polygon = None
            
            elif op["item"] == "add":
                if len(self.points) == 1:
                    first_node_tag = list(self.tag_index.keys())[0]
                self.points.insert(op["index"], [op["x"], op["y"]])
                for key in self.tag_index.keys():
                    if self.tag_index[key] >= op["index"]:
                        self.tag_index[key] += 1
                tag = op["selected"]
                self.tag_index[tag] = op["index"]
                _ = self.canvas.create_rectangle((op["x"], op["y"], op["x"], op["y"]), outline='red', fill='red', width=4, tags=tag, activeoutline='yellow', activefill='yellow', activewidth=8)
                self.canvas.tag_bind(tag, '<ButtonPress-1>',   lambda event, tag=tag: self.on_press_tag(event, tag))
                self.canvas.tag_bind(tag, '<ButtonRelease-1>', lambda event, tag=tag: self.on_release_tag(event, tag))
                self.canvas.tag_bind(tag, '<Control-ButtonPress-1>',   lambda event, tag=tag: self.on_press_tag_multi(event, tag))
                self.canvas.tag_bind(tag, '<Alt-ButtonPress-1>', self.do_nothing)
                self.canvas.tag_bind(tag, '<B1-Motion>', lambda event, tag=tag: self.on_move_node(event, tag))
                self.canvas.tag_bind(tag, '<Shift-ButtonPress-1>', self.do_nothing)
                if len(self.points) == 2:
                    self.polygon = self.canvas.create_polygon(self.points, outline="mediumseagreen", fill="", width=3, tags="polygon", activeoutline='lime', activefill='')
                    self.canvas.lower("polygon", first_node_tag)
                    self.canvas.tag_bind(self.polygon, '<ButtonPress-1>',   lambda event, tag="polygon": self.on_press_tag(event, tag))
                    self.canvas.tag_bind(self.polygon, '<ButtonRelease-1>', lambda event, tag="polygon": self.on_release_tag(event, tag))
                    self.canvas.tag_bind(self.polygon, '<B1-Motion>', self.on_move_polygon)
                    self.canvas.tag_bind(self.polygon, '<Alt-ButtonPress-1>', self.do_nothing)
                    # self.canvas.tag_bind(self.polygon, '<Alt-ButtonRelease-1>', self.do_nothing)
                    self.canvas.tag_bind(self.polygon, '<Control-ButtonPress-1>', self.do_nothing)
                    # self.canvas.tag_bind(self.polygon, '<Control-ButtonRelease-1>', self.do_nothing)
                    self.canvas.tag_bind(self.polygon, '<Shift-ButtonPress-1>', self.do_nothing)
                if len(self.points) > 2:
                    self.canvas.coords(self.polygon, sum(self.points, []))

        else:
            print("redo stack is empty")
    
    def reduce_nodes(self, scale):
        points_array = np.array(self.points)
        points_array = np.round(points_array / scale, decimals=0)
        # 重叠的点只保留一个, np.unique保证不了顺序，所以得用别的来去重
        points_array, ind = np.unique(points_array, return_index=True, axis=0)
        points_array = points_array[np.argsort(ind)] * scale
        self.points = points_array.tolist()
        # 根据self.points重新画一版轮廓，原来的轮廓包括undo/redo stack全部清空
        self.canvas.delete("polygon")
        for item in self.tag_index.keys():
            self.canvas.delete(item)
        self.tag_index = {}
        self.max_node_index = 0
        self.polygon = None
        self.multiselected = []
        self.undo_stack = []
        self.redo_stack = []
        if len(self.points) > 1:
            self.polygon = self.canvas.create_polygon(self.points, outline="mediumseagreen", fill="", width=3, tags="polygon", activeoutline='lime', activefill='')
            self.canvas.tag_bind(self.polygon, '<ButtonPress-1>',   lambda event, tag="polygon": self.on_press_tag(event, tag))
            self.canvas.tag_bind(self.polygon, '<ButtonRelease-1>', lambda event, tag="polygon": self.on_release_tag(event, tag))
            self.canvas.tag_bind(self.polygon, '<B1-Motion>', self.on_move_polygon)
            self.canvas.tag_bind(self.polygon, '<Alt-ButtonPress-1>', self.do_nothing)
            # self.canvas.tag_bind(self.polygon, '<Alt-ButtonRelease-1>', self.do_nothing)
            self.canvas.tag_bind(self.polygon, '<Control-ButtonPress-1>', self.do_nothing)
            # self.canvas.tag_bind(self.polygon, '<Control-ButtonRelease-1>', self.do_nothing)
            self.canvas.tag_bind(self.polygon, '<Shift-ButtonPress-1>', self.do_nothing)
        for i, point in enumerate(self.points):
            tag = f"node{self.max_node_index + 1}"
            self.tag_index[tag] = i
            _ = self.canvas.create_rectangle((point[0], point[1], point[0], point[1]), outline='red', fill='red', width=4, tags=tag, activeoutline='yellow', activefill='yellow', activewidth=8)
            self.canvas.tag_bind(tag, '<ButtonPress-1>',   lambda event, tag=tag: self.on_press_tag(event, tag))
            self.canvas.tag_bind(tag, '<ButtonRelease-1>', lambda event, tag=tag: self.on_release_tag(event, tag))
            self.canvas.tag_bind(tag, '<Control-ButtonPress-1>',   lambda event, tag=tag: self.on_press_tag_multi(event, tag))
            self.canvas.tag_bind(tag, '<Alt-ButtonPress-1>', self.do_nothing)
            self.canvas.tag_bind(tag, '<B1-Motion>', lambda event, tag=tag: self.on_move_node(event, tag))
            self.canvas.tag_bind(tag, '<Shift-ButtonPress-1>', self.do_nothing)
            self.max_node_index += 1
    
    def cache_result(self):
        return (np.array(self.points), self.undo_stack, self.redo_stack)


def pop_err_win(message, font, winsize=(260, 60), exit=True, title="错误"):
    global root
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    err_win_x = screen_width // 2 - winsize[0] // 2
    err_win_y = screen_height // 2 - winsize[1] // 2
    err = tk.Toplevel()
    err.transient(root)
    err.title(title)
    err.geometry(f"{winsize[0]}x{winsize[1]}+{err_win_x}+{err_win_y}")
    err.resizable(False, False)
    err.attributes("-topmost", True)
    err.grab_set()
    err.focus_set()
    tk.Label(err, text=message, font=font).pack(fill=tk.BOTH, expand=True)
    err.wait_window()
    err.destroy()
    if exit:
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
    # if cnts.shape[1] != 2:
    #     pop_err_win(f"轮廓数据格式不正确\n期望形状为(点数, 2, 图像数)\n实际为{cnts.shape}", font=("微软雅黑", 10, "bold"), winsize=(300, 80))
    cnts = cnts * scale
    cnts = cnts[:, ::-1]
    # cnts = cnts.transpose(2, 0, 1)
    cnts = cnts[0:-1, :] # 观察发现最后一个点和第一个点重合 去除减少计算量
    return cnts

def save_new_cnts(scale, temp=False):
    global cnts_cache
    global current_image_no
    global curr_contour
    global undo_stack
    global redo_stack
    global img_file_name
    global images_paths

    if not temp:
        if not any(i is None for i in cnts_cache):
            file = filedialog.asksaveasfile(initialdir=".", initialfile="New_Unnamed_Contour.npy", filetypes=[("npy文件", ".npy"), ("所有文件", ".*")], defaultextension=".npy", title=f"选择保存路径", mode="wb")
            if file:
                (cnts_cache[current_image_no], undo_stack[current_image_no], redo_stack[current_image_no]) = curr_contour.cache_result()
                new_cnts = cnts_cache.copy()
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
            pop_err_win(f"部分图像暂无对应轮廓，无法保存", font=("微软雅黑", 10, "bold"), winsize=(300, 80), exit=False)
    else:
        if cnts_cache[current_image_no] is not None:
            new_cnts = cnts_cache[current_image_no].copy()
            # new_cnts = np.concatenate((new_cnts, np.expand_dims(new_cnts[0, :], axis=0)), axis=0)
            # new_cnts = new_cnts.transpose(1, 2, 0)
            # new_cnts = new_cnts[:, ::-1, :]
            new_cnts = np.round(new_cnts / scale, decimals=0)
            # for file in os.listdir("."):
            #     if file.startswith(f"{img_file_name.split('.')[0]}_contour"):
            #         os.remove(file)
            np.save(f"{images_paths[current_image_no].split('.')[0]}_cnt.npy", new_cnts.astype(np.float64))

def generate_cnt(modelpack, image):
    global curr_contour
    global canvas
    global current_image_no
    global undo_stack
    global redo_stack

    if curr_contour is not None:
        response = messagebox.askokcancel("警告", "检测到当前图像已有轮廓，是否覆盖？")
        if not response:
            return
        else:
            canvas.delete("polygon")
            for item in curr_contour.tag_index.keys():
                canvas.delete(item)
            undo_stack[current_image_no] = []
            redo_stack[current_image_no] = []
            curr_contour = None

    cnts = generate_contour(read_and_preprocess(image), modelpack=modelpack, device="cuda")
    cnts = cvt_tkpolygons(cnts, scale=scale)
    curr_contour = Contour(canvas, cnts, undo_stack[current_image_no], redo_stack[current_image_no])

def pop_startup_window(root):
    global img_file_name
    # global cnt_file_name
    global current_image_no
    global scale

    def cancel():
        img_file_nameVar.set(None)
        # cnt_file_nameVar.set(None)
        ask_filename_win.destroy()
        root.destroy()
    
    def openit():
        global img_file_name
        # global cnt_file_name
        img_file_name = img_entry.get()
        # cnt_file_name = cnt_entry.get()
        with open("history.txt", "w") as f:
            f.write(f"{img_file_name}\n")
            # f.write(f"{cnt_file_name}\n")
        ask_filename_win.destroy()

    def select_file(file_nameVar, title):
        filename = filedialog.askdirectory(initialdir='.', title=f"选择{title}")
        if filename:
            file_nameVar.set(filename)

    history_img_file_name = ""
    # history_cnt_file_name = ""

    if os.path.exists("history.txt"):
        with open("history.txt", "r") as f:
            history_img_file_name = f.readline().strip()
            # history_cnt_file_name = f.readline().strip()

    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    ask_win_x = screen_width // 2 - 150
    ask_win_y = screen_height // 2 - 50

    ask_filename_win = tk.Toplevel(root)
    ask_filename_win.title("打开文件夹")
    ask_filename_win.geometry(f"300x100+{ask_win_x}+{ask_win_y}")
    ask_filename_win.resizable(False, False)
    ask_filename_win.attributes("-topmost", True)
    ask_filename_win.grab_set()
    ask_filename_win.focus_set()
    ask_filename_win.transient(root)
    ask_filename_win.protocol("WM_DELETE_WINDOW", lambda: cancel())

    tk.Label(ask_filename_win, text="请输入图像文件夹路径").pack()
    img_file_nameVar = tk.StringVar(ask_filename_win, value=f"{history_img_file_name}")
    # cnt_file_nameVar = tk.StringVar(ask_filename_win, value=f"{history_cnt_file_name}")
    file_select_frame = tk.Frame(ask_filename_win)
    img_select_frame = tk.Frame(file_select_frame)
    # cnt_select_frame = tk.Frame(file_select_frame)
    tk.Label(img_select_frame, text="文件夹路径").pack(side=tk.LEFT)
    img_entry = tk.Entry(img_select_frame, textvariable=img_file_nameVar, width=20)
    img_select_button = tk.Button(img_select_frame, text="选择", height=0, width=6)
    img_entry.xview_moveto(1)
    # cnt_entry.xview_moveto(1)
    img_entry.pack(side=tk.LEFT)
    # cnt_entry.pack(side=tk.LEFT)
    img_select_frame.pack()
    # cnt_select_frame.pack()
    file_select_frame.pack()

    button_frame = tk.Frame(ask_filename_win)
    place_holder = tk.Label(button_frame, text=" " * 7)
    button_frame.pack()

    open_button = tk.Button(button_frame, text="打开", height=0,width=7)
    cancel_button = tk.Button(button_frame, text="取消", height=0,width=7)

    open_button.pack(side=tk.LEFT)
    place_holder.pack(side=tk.LEFT)
    cancel_button.pack(side=tk.RIGHT)
    img_select_button.pack(side=tk.RIGHT)
    # cnt_select_button.pack(side=tk.RIGHT)

    open_button.config(command=lambda:openit())
    cancel_button.config(command=lambda:cancel())
    img_select_button.config(command=lambda:select_file(img_file_nameVar, "图像文件夹"))
    # cnt_select_button.config(command=lambda:select_file(cnt_file_nameVar, "轮廓npy"))
    ask_filename_win.wait_window()

def read_images_from_dir(dir):
    images = []
    images_path = []
    for file in os.listdir(dir):
        if file.endswith(".png") or file.endswith(".jpg") or file.endswith(".jpeg"):
            images.append(cv2.resize(cv2.imread(os.path.join(dir, file)).astype(np.uint8), (128, 128)))
            images_path.append(os.path.join(dir, file))
    return np.array(images).transpose([1, 2, 3, 0]), images_path

def change_append_mode(e):
    global append_mode
    append_mode = not append_mode
    print(f"append_mode: {append_mode}")

def create_contour(e):
    global curr_contour
    global undo_stack
    global redo_stack
    global current_image_no
    global append_mode
    if not curr_contour and append_mode:
        undo_stack[current_image_no] = [{"selected": "node0", "item": "add", "index": 0, "x": e.x, "y": e.y}]
        curr_contour = Contour(canvas, np.array([[e.x, e.y]]), undo_stack[current_image_no], redo_stack[current_image_no])


if __name__ == "__main__":

    single_img = None

    img_file_name = None
    # cnt_file_name = None
    current_image_no = 0
    scale = 10
    append_mode = False

    root = tk.Tk()
    pop_startup_window(root)
    # if img_file_name is None or cnt_file_name is None:
    if img_file_name is None:
        print("未选择路径，程序退出")
        exit(0)
    print("正在读取数据...")
    images, images_paths = read_images_from_dir(img_file_name)
    # images = np.expand_dims(cv2.imread(img_file_name).astype(np.uint8), 3)
    # images = np.load(img_file_name).astype(np.uint8)
    # contours = np.load(cnt_file_name).astype(np.uint16)

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
    ai_button = tk.Button(button_frame, text="生成轮廓", width=10)
    reduce_nodes_button = tk.Button(button_frame, text="规整轮廓", width=10)
    save_button = tk.Button(button_frame, text="保存", width=10)
    place_holder1.pack(side=tk.LEFT, anchor=tk.CENTER)
    jump_num.pack(side=tk.LEFT, anchor=tk.CENTER)
    jump_button.pack(side=tk.LEFT, anchor=tk.CENTER)
    prev_image_button.pack(side=tk.LEFT, anchor=tk.CENTER)
    next_image_button.pack(side=tk.LEFT, anchor=tk.CENTER)
    place_holder2.pack(side=tk.RIGHT, anchor=tk.CENTER)
    ai_button.pack(side=tk.LEFT, anchor=tk.CENTER)
    reduce_nodes_button.pack(side=tk.RIGHT, anchor=tk.CENTER)
    save_button.pack(side=tk.RIGHT, anchor=tk.CENTER)
    canvas.pack()


    print("正在转换数据...")
    cvt_single_tkimage(images[:, :, :, current_image_no], scale=scale)
    modelpack = prepare_model(device="cuda")
    cnts_cache = [None for _ in range(image_no)]
    # cnts = generate_cnt(modelpack, images[:, :, :, current_image_no])
    # cnts = cvt_tkpolygons(contours, scale=scale)
    # print(cnts.shape)
    # if len(cnts) != image_no:
    #     pop_err_win(f"轮廓数据与图像数量不一致\n轮廓数据数量为{len(cnts)}\n图像数量为{image_no}", font=("微软雅黑", 10, "bold"), winsize=(300, 80))
    print("完成，正在启动编辑器...")
    canvas.create_image(0, 0, anchor=tk.NW, image=single_img)
    curr_contour = None
    # curr_contour = Contour(canvas, generate_cnt(modelpack, images[:, :, :, current_image_no]), undo_stack[current_image_no], redo_stack[current_image_no])
    
    def change_image(new_no):
        global current_image_no
        global curr_contour
        global images_paths
        global cnts_cache

        if curr_contour:
            (cnts_cache[current_image_no], undo_stack[current_image_no], redo_stack[current_image_no]) = curr_contour.cache_result()
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
        if cnts_cache[current_image_no] is not None:
            curr_contour = Contour(canvas, cnts_cache[current_image_no], undo_stack[current_image_no], redo_stack[current_image_no])
        else:
            curr_contour = None
        # cnts = generate_contour(read_and_preprocess(images[:, :, :, current_image_no]), modelpack=modelpack, device="cuda")
        # cnts = cvt_tkpolygons(cnts, scale=scale)
        # curr_contour = Contour(canvas, generate_cnt(modelpack, images[:, :, :, current_image_no]), undo_stack[current_image_no], redo_stack[current_image_no])

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
    
    # def clear_temp_files():
    #     for file in os.listdir("."):
    #         if file.startswith("~temp"):
    #             os.remove(file)

    jump_button.config(command=lambda:jump_image())
    prev_image_button.config(command=lambda:change_image(current_image_no-1))
    next_image_button.config(command=lambda:change_image(current_image_no+1))
    ai_button.config(command=lambda:generate_cnt(modelpack, images[:, :, :, current_image_no]))
    reduce_nodes_button.config(command=lambda:curr_contour.reduce_nodes(scale=scale))
    save_button.config(command=lambda:save_new_cnts(scale=scale))
    root.bind("<Left>", lambda e:change_image(current_image_no-1))
    root.bind("<Right>", lambda e:change_image(current_image_no+1))
    root.bind("<Control-s>", lambda e:save_new_cnts(scale=scale))
    root.bind("<Control-S>", lambda e:save_new_cnts(scale=scale))
    root.bind("<Return>", lambda e:jump_image())
    root.bind("<Shift-a>", change_append_mode)
    root.bind("<Shift-A>", change_append_mode)
    root.bind("<Shift-ButtonPress-1>", lambda e:create_contour(e))
    # root.bind("<Destroy>", lambda e:clear_temp_files())
    root.mainloop()
