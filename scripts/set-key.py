import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from credentials import save_key
import tkinter as tk
from tkinter import messagebox

root = tk.Tk()
root.title("Jev API 密钥 — 仅保存到 Windows 凭据管理器")
root.geometry("620x230")
root.resizable(False, False)
tk.Label(root, text="请输入 TypeSafe API key（输入隐藏，不会进入聊天或日志）。", pady=18).pack()
value = tk.Entry(root, show="●", width=68)
value.pack(pady=8)
def save():
    try:
        save_key(value.get().strip())
    except Exception:
        messagebox.showerror("未保存", "密钥为空、含空白字符，或凭据管理器不可用。")
        return
    value.delete(0, tk.END)
    messagebox.showinfo("已保存", "已保存在当前 Windows 用户的凭据管理器。\n可以返回 Codex，继续验收。")
    root.destroy()
tk.Button(root, text="保存密钥", command=save, width=20).pack(pady=10)
tk.Label(root, text="尚无密钥：在 console.typesafe.ai 登录后创建。此窗口不会登录或充值。").pack()
value.focus_set()
root.mainloop()
