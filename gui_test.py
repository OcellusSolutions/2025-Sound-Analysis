import os
import tkinter as tk
from tkinter import ttk, messagebox


import os
import tkinter as tk
from tkinter import ttk, messagebox


def node_folder_two_panel_selector(
    local_node_list,
    local_base_path,
    audioFile="audio.wav",
    dataFile="data.json",
    title="Select Node, Folders, and Parameters",
):

    out = {
        "selected_node": None,
        "selected_folders": [],
        "dateWavPaths": [],
        "dateJsonPaths": [],
        "mainDir": None,
        "params": {}
    }

    def build_paths(node, folders):
        mainDir = os.path.join(local_base_path, node)
        wavs = [os.path.join(mainDir, f, audioFile) for f in folders]
        jsns = [os.path.join(mainDir, f, dataFile) for f in folders]
        return mainDir, wavs, jsns

    def list_date_folders(node):
        mainDir = os.path.join(local_base_path, node)
        dateFolders = os.listdir(mainDir)
        dateFolders.sort()
        dateFolders = [d for d in dateFolders if "." not in d]
        return mainDir, dateFolders

    # ---------- GUI ----------
    root = tk.Tk()
    root.title(title)
    root.geometry("900x520")
    root.attributes("-topmost", True)

    # ---------- Parameter bar ----------
    param_frame = ttk.LabelFrame(root, text="Processing Parameters")
    param_frame.pack(fill="x", padx=12, pady=(10, 6))

    def make_entry(label, default, col):
        ttk.Label(param_frame, text=label).grid(row=0, column=col*2, padx=6, pady=6)
        var = tk.StringVar(value=str(default))
        ent = ttk.Entry(param_frame, textvariable=var, width=8)
        ent.grid(row=0, column=col*2+1, padx=6, pady=6)
        return var

    f0_low_var  = make_entry("f0 low (Hz)", 100, 0)
    f0_high_var = make_entry("f0 high (Hz)", 200, 1)
    low_cut_var = make_entry("low_cut (Hz)", 200, 2)
    mid_cut_var = make_entry("mid_cut (Hz)", 500, 3)
    high_cut_var= make_entry("high_cut (Hz)", 1000, 4)

    # ---------- Main panels ----------
    split = ttk.Frame(root)
    split.pack(fill="both", expand=True, padx=12, pady=8)

    split.columnconfigure(0, weight=1)
    split.columnconfigure(1, weight=2)
    split.rowconfigure(0, weight=1)

    # Left panel — Nodes
    nodes_panel = ttk.Labelframe(split, text="Nodes")
    nodes_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
    nodes_panel.rowconfigure(0, weight=1)
    nodes_panel.columnconfigure(0, weight=1)

    node_listbox = tk.Listbox(nodes_panel, selectmode="browse")
    node_listbox.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    # Right panel — Folders
    folders_panel = ttk.Labelframe(split, text="Folders (multi-select)")
    folders_panel.grid(row=0, column=1, sticky="nsew")
    folders_panel.rowconfigure(0, weight=1)
    folders_panel.columnconfigure(0, weight=1)

    folder_listbox = tk.Listbox(folders_panel, selectmode="extended")
    folder_listbox.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    # ---------- Buttons ----------
    btn_row = ttk.Frame(root)
    btn_row.pack(fill="x", padx=12, pady=(0, 12))

    def select_all():
        folder_listbox.select_set(0, tk.END)

    def clear_sel():
        folder_listbox.selection_clear(0, tk.END)

    ttk.Button(btn_row, text="Select All Folders", command=select_all).pack(side="left")
    ttk.Button(btn_row, text="Clear Folder Selection", command=clear_sel).pack(side="left", padx=8)

    # ---------- Behavior ----------
    current_node = {"value": None}

    def fill_nodes():
        for n in local_node_list:
            node_listbox.insert(tk.END, n)

    def on_node_select(evt=None):
        sel = node_listbox.curselection()
        if not sel:
            return
        node = local_node_list[sel[0]]
        current_node["value"] = node

        mainDir, folders = list_date_folders(node)
        folder_listbox.delete(0, tk.END)
        for f in folders:
            folder_listbox.insert(tk.END, f)

    def validate_float(val, name):
        try:
            return float(val)
        except ValueError:
            messagebox.showerror("Invalid number", f"{name} must be a number.")
            return None

    def finish():
        node = current_node["value"]
        if node is None:
            messagebox.showinfo("Missing selection", "Please select a node.")
            return

        idxs = folder_listbox.curselection()
        if not idxs:
            messagebox.showinfo("Missing selection", "Please select at least one folder.")
            return

        folders = [folder_listbox.get(i) for i in idxs]

        # Validate parameters
        params = {
            "f0_low":  validate_float(f0_low_var.get(), "f0 low"),
            "f0_high": validate_float(f0_high_var.get(), "f0 high"),
            "low_cut": validate_float(low_cut_var.get(), "low_cut"),
            "mid_cut": validate_float(mid_cut_var.get(), "mid_cut"),
            "high_cut":validate_float(high_cut_var.get(), "high_cut"),
        }

        if any(v is None for v in params.values()):
            return

        mainDir, wavs, jsns = build_paths(node, folders)

        out["selected_node"] = node
        out["selected_folders"] = folders
        out["mainDir"] = mainDir
        out["dateWavPaths"] = wavs
        out["dateJsonPaths"] = jsns
        out["params"] = params

        root.quit()

    ttk.Button(btn_row, text="Finish", command=finish).pack(side="right")
    ttk.Button(btn_row, text="Cancel", command=root.quit).pack(side="right", padx=8)

    # Bindings
    node_listbox.bind("<<ListboxSelect>>", on_node_select)

    fill_nodes()

    root.mainloop()
    root.destroy()

    return out


# ------------------ usage ------------------
import datetime
local_base_path = "/Volumes/Case_portable/ocellus/hives_acs/"   # path to local drive containing data
today = datetime.date.today()                                   # get today's datetime
today_str2 = datetime.datetime.strftime(today, '%Y%m%d') # format datetime [year, month, day]

# Find local nodes
print('Checking local nodes...')
local_node_list = os.listdir(local_base_path)
local_node_list = [node for node in local_node_list if not node.startswith('.')]

result = node_folder_two_panel_selector(local_node_list, local_base_path)
selected_node = result["selected_node"]
dateFolders = result["selected_folders"]
dateWavPaths = result["dateWavPaths"]
dateJsonPaths = result["dateJsonPaths"]
print(selected_node, len(dateFolders))

#TODO add in actual processing, export to hdf5 file, gui to read in hdf5 file and export results