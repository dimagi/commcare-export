import tkinter as tk
from tkinter import filedialog as fd
from tkinter import messagebox
from dataclasses import dataclass

from commcare_export.cli import main_with_args

WINDOW_TITLE = "Data Export Tool"
WINDOW_GEOMETRY = "350x550"

DEFAULT_URL = "https://commcarehq.org"

SUPPORTED_AUTH_MODES = [
    "password",
    "apikey",
]

SUPPORTED_EXPORT_FORMATS = [
    "sql",
    "xlsx",
    "markdown",
]

SUPPORTED_DB_TYPES = [
    "postgresql",
]


@dataclass
class DETArguments:
    output_format: str
    project: str
    commcare_hq: str
    auth_mode: str
    password: str
    username: str
    query: str
    output: str
    # Assume empty
    strict_types: str = ''
    version: str = ''
    dump_query: str = ''
    api_version: str = ''
    since: str = ''
    until: str = ''
    start_over: str = ''
    profile: str = ''
    missing_value: str = ''
    batch_size: str = ''
    checkpoint_key: str = ''
    users: str = ''
    locations: str = ''
    with_organization: str = ''
    export_root_if_no_subdocument: str = ''


class WindowManager:
    frame_row = 0

    remote_url_var = None
    domain_var = None
    auth_mode_var = None
    username_var = None
    password_var = None
    query_file_var = None
    export_format_var = None

    db_type_var = None
    db_username_var = None
    db_password_var = None
    db_host_var = None
    db_name_var = None

    def __init__(self):
        self.window = tk.Tk()
        self.window.title(WINDOW_TITLE)
        self.window.geometry(WINDOW_GEOMETRY)

        self.remote_url_var = tk.StringVar()
        self.domain_var = tk.StringVar()
        self.auth_mode_var = tk.StringVar()
        self.username_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.query_file_var = tk.StringVar()
        self.export_format_var = tk.StringVar()

        self.db_type_var = tk.StringVar()
        self.db_username_var = tk.StringVar()
        self.db_password_var = tk.StringVar()
        self.db_host_var = tk.StringVar()
        self.db_password_var = tk.StringVar()
        self.db_name_var = tk.StringVar()

        self.construct_window_frames()

    def construct_window_frames(self):
        self._build_info_frame(
            self._get_new_frame()
        )

        remote_details_frame = self._get_new_frame(relief=tk.RIDGE)
        self._build_remote_hq_frame(remote_details_frame, row=0)
        self._build_domain_frame(remote_details_frame, row=1)
        self._build_auth_mode_frame(remote_details_frame, row=2)
        self._build_username_frame(remote_details_frame, row=3)
        self._build_password_frame(remote_details_frame, row=4)

        export_details_frame = self._get_new_frame()
        self._build_query_file_frame(export_details_frame, row=0)
        self._build_export_format_frame(export_details_frame, row=2)

        self._build_db_connection_frame(
            self._get_new_frame(relief=tk.RIDGE)
        )
        self._build_submit_button_frame(self._get_new_frame())

    def run(self):
        self.window.mainloop()

    def _get_new_frame(self, relief=None):
        relief = relief if relief else tk.FLAT

        frame = tk.Frame(master=self.window, relief=relief, border=1)
        frame.grid(row=self.frame_row, column=0, padx=10, pady=10)
        self.frame_row += 1
        return frame

    def _build_info_frame(self, frame, row=None):
        row = row if row else 0
        label = tk.Label(text="Please enter the relevant details below", master=frame)
        label.grid(row=row, column=0, sticky="w")

    def _build_remote_hq_frame(self, frame, row=None):
        row = row if row else 0

        label = tk.Label(text="Remote URL", master=frame)
        entry = tk.Entry(master=frame, textvariable=self.remote_url_var)
        self.remote_url_var.set(DEFAULT_URL)

        label.grid(row=row, column=0, sticky="w")
        entry.grid(row=row, column=1)

    def _build_domain_frame(self, frame, row=None):
        row = row if row else 0

        label = tk.Label(text="Remote domain", master=frame)
        entry = tk.Entry(master=frame, textvariable=self.domain_var)

        label.grid(row=row, column=0, sticky="w")
        entry.grid(row=row, column=1, sticky="ew")

    def _build_username_frame(self, frame, row=None):
        row = row if row else 0

        label = tk.Label(text="Username", master=frame)
        entry = tk.Entry(master=frame, textvariable=self.username_var)

        label.grid(row=row, column=0, sticky="w")
        entry.grid(row=row, column=1, sticky="ew")

    def _build_password_frame(self, frame, row=None):
        row = row if row else 0

        label = tk.Label(text="Password", master=frame)
        entry = tk.Entry(master=frame, textvariable=self.password_var)

        label.grid(row=row, column=0, sticky="w")
        entry.grid(row=row, column=1, sticky="ew")

    def _build_auth_mode_frame(self, frame, row=None):
        row = row if row else 0

        label = tk.Label(text="Auth mode", master=frame)

        self.auth_mode_var.set(SUPPORTED_AUTH_MODES[0])
        options_menu = tk.OptionMenu(frame, self.auth_mode_var, *SUPPORTED_AUTH_MODES)

        label.grid(row=row, column=0, sticky="w")
        options_menu.grid(row=row, column=1, sticky="ew")

    def _build_query_file_frame(self, frame, row=None):
        row = row if row else 0

        self.query_file_var.set("No file selected")
        query_file_lbl = tk.Label(textvariable=self.query_file_var, master=frame, width=20)
        select_file_btn = tk.Button(text="Select query file", master=frame, command=self._select_file)

        select_file_btn.grid(row=row, column=0, sticky="w")
        query_file_lbl.grid(row=row+1, column=0, sticky="w")

    def _build_export_format_frame(self, frame, row=None):
        row = row if row else 0

        label = tk.Label(text="Export format", master=frame)

        self.export_format_var.set(SUPPORTED_EXPORT_FORMATS[0])
        options_menu = tk.OptionMenu(frame, self.export_format_var, *SUPPORTED_EXPORT_FORMATS)

        label.grid(row=row, column=0, sticky="w")
        options_menu.grid(row=row, column=1, sticky="ew")

    def _build_db_connection_frame(self, frame, row=None):
        row = row if row else 0

        label = tk.Label(text="DATABASE SETTINGS", master=frame)

        self.db_type_var.set(SUPPORTED_DB_TYPES[0])
        db_options_menu = tk.OptionMenu(frame, self.db_type_var, *SUPPORTED_DB_TYPES)

        db_username_label = tk.Label(text="Username", master=frame)
        db_username_ent = tk.Entry(master=frame, textvariable=self.db_username_var)

        db_password_label = tk.Label(text="Password", master=frame)
        db_password_ent = tk.Entry(master=frame, textvariable=self.db_password_var)

        db_host_label = tk.Label(text="Host", master=frame)
        db_host_ent = tk.Entry(master=frame, textvariable=self.db_host_var)

        db_name_label = tk.Label(text="Database name", master=frame)
        db_name_ent = tk.Entry(master=frame, textvariable=self.db_name_var)

        label.grid(row=row, column=0, sticky="w")
        db_options_menu.grid(row=row+1, column=1, sticky="w")

        db_username_label.grid(row=row+2, column=0, sticky="w")
        db_username_ent.grid(row=row+2, column=1, sticky="w")
        db_password_label.grid(row=row+3, column=0, sticky="w")
        db_password_ent.grid(row=row+3, column=1, sticky="w")

        db_host_label.grid(row=row+4, column=0, sticky="w")
        db_host_ent.grid(row=row+4, column=1, sticky="w")
        db_name_label.grid(row=row+5, column=0, sticky="w")
        db_name_ent.grid(row=row+5, column=1, sticky="w")

    def _build_submit_button_frame(self, frame, row=None):
        row = row if row else 0

        run_det_btn = tk.Button(text="Run export", master=frame, command=self._run_export_tool)
        run_det_btn.grid(row=row, column=0, sticky="ew")

    def _select_file(self):
        filetypes = (
            ('text files', '*.xlsx'),
            ('All files', '*.*')
        )

        file_path = fd.askopenfilename(
            title='Open a file',
            initialdir='/',
            filetypes=filetypes)
        self.query_file_var.set(file_path)

    def _get_output_string(self):
        return "{type}://{username}:{password}@{host}/{db_name}".format(
            type=self.db_type_var.get(),
            username=self.db_username_var.get(),
            password=self.db_password_var.get(),
            host=self.db_host_var.get(),
            db_name=self.db_name_var.get()
        )

    def _notify_result(self, result_str, error=False):
        if error:
            messagebox.showerror("Error occurred!", result_str)
        else:
            messagebox.showinfo("All done!", result_str)

    def _run_export_tool(self):
        args_obj = DETArguments(
            commcare_hq=self.remote_url_var.get(),
            project=self.domain_var.get(),
            auth_mode=self.auth_mode_var.get(),
            username=self.username_var.get(),
            password=self.password_var.get(),
            output_format=self.export_format_var.get(),
            query=self.query_file_var.get(),
            output=self._get_output_string(),
        )
        try:
            main_with_args(args_obj, is_gui=True)
        except Exception as e:
            self._notify_result(str(e), error=True)
        else:
            self._notify_result("All done!")


if __name__ == '__main__':
    manager = WindowManager()
    manager.run()
