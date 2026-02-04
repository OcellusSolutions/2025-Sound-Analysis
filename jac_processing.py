import os
import datetime
import numpy as np
import json
from scipy.io import wavfile


local_base_path = "/Volumes/Case_portable/ocellus/hives_acs/"   # path to local drive containing data
today = datetime.date.today()                                   # get today's datetime
today_str2 = datetime.datetime.strftime(today, '%Y%m%d') # format datetime [year, month, day]

# Find local nodes
print('Checking local nodes...')
local_node_list = os.listdir(local_base_path)
local_node_list = [node for node in local_node_list if not node.startswith('.')]
local_nodes = {}
for ii in range(len(local_node_list)):
    local_file_list = os.listdir(os.path.join(local_base_path, local_node_list[ii]))
    local_nodes[local_node_list[ii]] = local_file_list

import tkinter as tk
from tkinter import ttk

def pick_node_gui(node_list, title="Select a Node"):
    selected = {"value": None}

    def on_select():
        sel = listbox.curselection()
        if sel:
            selected["value"] = node_list[sel[0]]
            root.quit()   # exit mainloop cleanly

    def on_double_click(event):
        on_select()

    root = tk.Tk()
    root.title(title)
    root.geometry("400x300")
    root.attributes('-topmost', True)  # show on top (fixes Mac dock issue)

    label = ttk.Label(root, text="Available Nodes:")
    label.pack(pady=10)

    frame = ttk.Frame(root)
    frame.pack(fill="both", expand=True, padx=10)

    scrollbar = ttk.Scrollbar(frame)
    scrollbar.pack(side="right", fill="y")

    listbox = tk.Listbox(frame, yscrollcommand=scrollbar.set)
    for node in node_list:
        listbox.insert(tk.END, node)
    listbox.pack(fill="both", expand=True)
    scrollbar.config(command=listbox.yview)

    listbox.bind("<Double-Button-1>", on_double_click)

    button = ttk.Button(root, text="Select", command=on_select)
    button.pack(pady=10)

    root.mainloop()
    root.destroy()  # <-- CRITICAL for Mac

    return selected["value"]

selected_node = pick_node_gui(local_node_list)

if selected_node is None:
    print("No node selected.")
    exit()

print(f"You selected: {selected_node}")
node = selected_node
# selected_node = node
mainDir = os.path.join(local_base_path,node)
node_name = node[5:]
print('Processing node: ',node_name,'...')
audioFile = 'audio.wav'
dataFile = 'data.json'
dateFolders = os.listdir(mainDir)
dateFolders.sort()

dateFolders = [date for date in dateFolders if '.' not in date]
dateWavPaths = [os.path.join(mainDir, path, audioFile) for path in dateFolders]
dateJsonPaths = [os.path.join(mainDir, path, dataFile) for path in dateFolders]

# Parallel loop implementation
fs, y1 = wavfile.read(dateWavPaths[0])  # Read sample file to get sampling frequency
data = {}