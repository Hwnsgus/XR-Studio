import tkinter as tk
import unreal

def apply_location():
    actor_name = entry_name.get()
    try:
        x = float(entry_x.get())
        y = float(entry_y.get())
        z = float(entry_z.get())
    except ValueError:
        print("❌ 좌표 입력이 잘못되었습니다.")
        return

    cmd = f"SetActorLocationByName {actor_name} {x} {y} {z}"
    unreal.SystemLibrary.execute_console_command(
        unreal.EditorLevelLibrary.get_editor_world(),
        cmd
    )

root = tk.Tk()
root.title("Move Actor by Name")

tk.Label(root, text="Actor Name").grid(row=0, column=0)
entry_name = tk.Entry(root)
entry_name.grid(row=0, column=1)

tk.Label(root, text="X").grid(row=1, column=0)
entry_x = tk.Entry(root)
entry_x.grid(row=1, column=1)

tk.Label(root, text="Y").grid(row=2, column=0)
entry_y = tk.Entry(root)
entry_y.grid(row=2, column=1)

tk.Label(root, text="Z").grid(row=3, column=0)
entry_z = tk.Entry(root)
entry_z.grid(row=3, column=1)

tk.Button(root, text="Move", command=apply_location).grid(row=4, columnspan=2)

root.mainloop()
