import os
import re
import sys
import threading
import time
from tkinter import *
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk
import requests
from io import BytesIO
from pytubefix import YouTube, Playlist
from urllib.parse import urlparse, parse_qs

# --- Constants for Styling and Configuration ---
class AppConstants:
    APP_NAME = "BY=>Downloader"
    DEFAULT_DOWNLOAD_PATH = "downloads"
    THUMBNAIL_SIZE = (200, 150)  # Standard 16:9 aspect ratio
    AUTO_FETCH_DELAY = 1500  # milliseconds delay after typing before auto-fetch
    
    # Color Palette (Dark Theme)
    BG_PRIMARY = '#1e1e1e'  # Dark Grey
    BG_SECONDARY = '#2d2d2d'  # Slightly Lighter Grey for frames
    BG_TERTIARY = '#3c3c3c'  # For entry fields, comboboxes
    TEXT_PRIMARY = '#e0e0e0'  # Light Grey for main text
    TEXT_SECONDARY = '#b0b0b0'  # Muted Grey for less important text
    ACCENT_COLOR = '#ff6347'  # Tomato Red for buttons, progress
    ACCENT_HOVER = "#0da519"  # Slightly darker for hover
    BORDER_COLOR = '#4a4a4a'
    ERROR_COLOR = '#ff3333'
    SUCCESS_COLOR = '#33cc33'
    ENTRY_FIELD_COLOR = '#4a4a4a'  # Custom color for text fields

    # Fonts
    FONT_TITLE = ('Segoe UI', 22, 'bold')
    FONT_HEADING = ('Segoe UI', 12, 'bold')
    FONT_NORMAL = ('Segoe UI', 10)
    FONT_MONO = ('Consolas', 9)  # For progress details


class YouTubeDownloaderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(AppConstants.APP_NAME)
        self.root.geometry("600x600")
      
        self.root.resizable(False, True) 
        self.root.configure(bg=AppConstants.BG_PRIMARY)
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

        # Download path
        self.download_path = self._load_download_path()
        self._create_download_directory()

        # State variables
        self.current_yt_object = None  # Stores YouTube or Playlist object
        self.current_video_info = None
        self.current_streams = []  # List of stream objects from pytubefix
        self.current_download_thread = None
        self.download_canceled = False
        self.is_playlist_mode = False
        self.auto_fetch_job = None  # For scheduling auto-fetch

        self._setup_styles()
        self._setup_ui()
        self._clear_info()  # Initialize with clear info

    def _setup_styles(self):
        """Configures ttk styles for a modern dark theme."""
        self.style = ttk.Style()
        self.style.theme_use('clam')

        # General background and foreground
        self.style.configure('.', font=AppConstants.FONT_NORMAL, 
                           background=AppConstants.BG_PRIMARY, 
                           foreground=AppConstants.TEXT_PRIMARY)

        # Frames
        self.style.configure('TFrame', background=AppConstants.BG_PRIMARY)
        self.style.configure('Dark.TFrame', background=AppConstants.BG_SECONDARY, 
                           relief='flat', borderwidth=0)
        self.style.configure('DarkLabelframe.TLabelframe', 
                           background=AppConstants.BG_SECONDARY, 
                           foreground=AppConstants.TEXT_PRIMARY, 
                           bordercolor=AppConstants.BORDER_COLOR)
        self.style.configure('DarkLabelframe.TLabelframe.Label', 
                           background=AppConstants.BG_SECONDARY, 
                           foreground=AppConstants.TEXT_PRIMARY, 
                           font=AppConstants.FONT_HEADING)

        # Labels
        self.style.configure('TLabel', background=AppConstants.BG_PRIMARY, 
                           foreground=AppConstants.TEXT_PRIMARY)
        self.style.configure('Secondary.TLabel', background=AppConstants.BG_SECONDARY, 
                           foreground=AppConstants.TEXT_PRIMARY)
        self.style.configure('Heading.TLabel', font=AppConstants.FONT_HEADING, 
                           background=AppConstants.BG_SECONDARY, 
                           foreground=AppConstants.TEXT_PRIMARY)
        self.style.configure('Error.TLabel', foreground=AppConstants.ERROR_COLOR, 
                           background=AppConstants.BG_PRIMARY)

        # Entry - Custom colors for text fields
        self.style.configure('Custom.TEntry', 
                           fieldbackground=AppConstants.ENTRY_FIELD_COLOR,
                           foreground=AppConstants.TEXT_PRIMARY,
                           insertcolor=AppConstants.TEXT_PRIMARY,
                           borderwidth=1, 
                           relief='flat', 
                           padding=5)
        self.style.map('Custom.TEntry',
                      fieldbackground=[('focus', AppConstants.ENTRY_FIELD_COLOR),
                                     ('!focus', AppConstants.ENTRY_FIELD_COLOR)],
                      foreground=[('!disabled', AppConstants.TEXT_PRIMARY)],
                      bordercolor=[('focus', AppConstants.ACCENT_COLOR)])

        # Buttons
        self.style.configure('TButton',
                           background=AppConstants.ACCENT_COLOR,
                           foreground=AppConstants.TEXT_PRIMARY,
                           font=AppConstants.FONT_NORMAL,
                           relief='flat',
                           borderwidth=0,
                           padding=(10, 5))
        self.style.map('TButton',
                      background=[('active', AppConstants.ACCENT_HOVER), 
                                ('!disabled', AppConstants.ACCENT_COLOR)],
                      foreground=[('disabled', AppConstants.TEXT_SECONDARY)],
                      highlightbackground=[('focus', AppConstants.ACCENT_HOVER)],
                      highlightcolor=[('focus', AppConstants.ACCENT_HOVER)])
        
        self.style.configure('Outline.TButton', 
                           background=AppConstants.BG_SECONDARY, 
                           foreground=AppConstants.ACCENT_COLOR, 
                           borderwidth=1, 
                           relief='solid', 
                           bordercolor=AppConstants.ACCENT_COLOR)
        self.style.map('Outline.TButton', 
                      background=[('active', AppConstants.BG_TERTIARY), 
                                ('!disabled', AppConstants.BG_SECONDARY)],
                      foreground=[('active', AppConstants.ACCENT_HOVER), 
                                ('!disabled', AppConstants.ACCENT_COLOR)])

        # Progressbar with percentage text
        self.style.configure('Horizontal.TProgressbar', 
                           background=AppConstants.ACCENT_COLOR, 
                           troughcolor=AppConstants.BG_TERTIARY, 
                           thickness=12,
                           borderwidth=0)
        self.style.layout('Text.Horizontal.TProgressbar',
                         [('Horizontal.Progressbar.trough',
                           {'children': [('Horizontal.Progressbar.pbar',
                                          {'side': 'left', 'sticky': 'ns'})],
                            'sticky': 'nswe'}),
                          ('Horizontal.Progressbar.label', {'sticky': ''})])
        self.style.configure('Text.Horizontal.TProgressbar', 
                           text='0%',
                           background=AppConstants.ACCENT_COLOR,
                           troughcolor=AppConstants.BG_TERTIARY,
                           foreground=AppConstants.TEXT_PRIMARY,
                           font=('Segoe UI', 9, 'bold'))

        # Treeview
        self.style.configure('Treeview', 
                           background=AppConstants.BG_TERTIARY, 
                           foreground=AppConstants.TEXT_PRIMARY,
                           fieldbackground=AppConstants.BG_TERTIARY, 
                           borderwidth=0, 
                           relief='flat', 
                           rowheight=24)
        self.style.map('Treeview', 
                      background=[('selected', AppConstants.ACCENT_COLOR)],
                      foreground=[('selected', AppConstants.TEXT_PRIMARY)])

    def _setup_ui(self):
        """Sets up the main graphical user interface elements with scrolling."""
        # Create a canvas and scrollbar for scrolling
        self.canvas = Canvas(self.root, bg=AppConstants.BG_PRIMARY, 
                        highlightthickness=0, borderwidth=0)
        self.scrollbar = ttk.Scrollbar(self.root, orient="vertical", 
                                    command=self.canvas.yview)
        
        # Create a frame inside the canvas to hold all content
        self.scrollable_frame = ttk.Frame(self.canvas, style='Dark.TFrame')
        self.scrollable_frame.bind("<Configure>", 
                                lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        
        # Create window in canvas
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw", width=580)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Pack canvas and scrollbar
        self.canvas.pack(side="left", fill="both", expand=True, padx=(0, 0))
        self.scrollbar.pack(side="right", fill="y")
        
        # Bind mouse wheel for scrolling
        self._bind_mousewheel()
        
        # Now create all UI elements inside scrollable_frame
        main_frame = self.scrollable_frame
        
        # Configure grid weights for responsiveness
        main_frame.columnconfigure(0, weight=1)

        # --- Title ---
        title_label = Label(main_frame, text=f"🎵 {AppConstants.APP_NAME}",
                        font=AppConstants.FONT_TITLE,
                        fg=AppConstants.ACCENT_COLOR,
                        bg=AppConstants.BG_PRIMARY)
        title_label.grid(row=0, column=0, pady=(0, 20), sticky=W, padx=15)
        
        # --- URL Input Section ---
        url_frame = ttk.LabelFrame(main_frame, text=" YouTube URL ", 
                                style='DarkLabelframe.TLabelframe', 
                                padding="15 10")
        url_frame.grid(row=1, column=0, sticky=(E, W), pady=(0, 15), padx=15)
        url_frame.columnconfigure(1, weight=1)

        ttk.Label(url_frame, text="Video/Playlist URL:", 
                style='Secondary.TLabel').grid(row=0, column=0, sticky=W, padx=(0, 10))
        
        # Create a frame to hold the entry and paste button
        url_entry_frame = ttk.Frame(url_frame, style='Dark.TFrame')
        url_entry_frame.grid(row=0, column=1, sticky=(E, W), padx=(0, 10))
        url_entry_frame.columnconfigure(0, weight=1)
        
        # Use custom styled entry for URL
        self.url_entry = ttk.Entry(url_entry_frame, style='Custom.TEntry')
        self.url_entry.grid(row=0, column=0, sticky=(E, W))
        
        # Paste button
        self.paste_btn = ttk.Button(url_entry_frame, text="Paste", 
                                command=self._paste_url, 
                                style='Outline.TButton', width=8)
        self.paste_btn.grid(row=0, column=1, padx=(5, 0))
        
        self.url_entry.bind('<KeyRelease>', self._on_url_change)  # Auto-fetch on typing
        self.url_entry.bind('<<Paste>>', self._on_paste_event)  # Handle paste events
        
        # Status indicator for auto-fetch
        self.fetch_status_label = ttk.Label(url_frame, text="", style='Secondary.TLabel')
        self.fetch_status_label.grid(row=1, column=1, sticky=W, pady=(5, 0))

        # --- Video/Playlist Information Section ---
        self.info_frame = ttk.LabelFrame(main_frame, text=" Information ", 
                                    style='DarkLabelframe.TLabelframe', 
                                    padding="15 10")
        self.info_frame.grid(row=2, column=0, sticky=(E, W), pady=(0, 15), padx=15)
        self.info_frame.columnconfigure(0, weight=0)  # Thumbnail column - no expand
        self.info_frame.columnconfigure(1, weight=1)  # Info column - expands
        
        # Create a frame for thumbnail to ensure it stays fixed
        thumbnail_container = Frame(self.info_frame, bg=AppConstants.BG_SECONDARY,
                                width=170, height=100)
        thumbnail_container.grid(row=0, column=0, rowspan=5, padx=(0, 15), 
                            pady=(0,5), sticky="nw")
        thumbnail_container.grid_propagate(False)
        
        # Thumbnail - Use regular Label inside the container
        self.thumbnail_label = Label(thumbnail_container, text="Thumbnail\nNo image", 
                                bg=AppConstants.BG_SECONDARY, 
                                fg=AppConstants.TEXT_SECONDARY, 
                                relief='solid', borderwidth=1, 
                                anchor=CENTER)
        self.thumbnail_label.pack(fill=BOTH, expand=True)

        # Create a frame for text info to control layout better
        info_text_frame = Frame(self.info_frame, bg=AppConstants.BG_SECONDARY)
        info_text_frame.grid(row=0, column=1, rowspan=5, sticky="nsew", pady=2)
        info_text_frame.columnconfigure(0, weight=1)
        
        # Video info labels with proper wrapping and positioning
        self.title_label = Label(info_text_frame, text="Title: ", 
                            font=AppConstants.FONT_HEADING,
                            bg=AppConstants.BG_SECONDARY,
                            fg=AppConstants.TEXT_PRIMARY,
                            anchor="w", justify=LEFT, wraplength=320)
        self.title_label.grid(row=0, column=0, sticky="ew", pady=1)
        
        self.author_label = Label(info_text_frame, text="Author: ", 
                                bg=AppConstants.BG_SECONDARY,
                                fg=AppConstants.TEXT_PRIMARY,
                                anchor="w", justify=LEFT, wraplength=320)
        self.author_label.grid(row=1, column=0, sticky="ew", pady=1)
        
        self.duration_label = Label(info_text_frame, text="Duration: ", 
                                bg=AppConstants.BG_SECONDARY,
                                fg=AppConstants.TEXT_PRIMARY,
                                anchor="w", justify=LEFT)
        self.duration_label.grid(row=2, column=0, sticky="w", pady=1)
        
        self.views_label = Label(info_text_frame, text="Views: ", 
                            bg=AppConstants.BG_SECONDARY,
                            fg=AppConstants.TEXT_PRIMARY,
                            anchor="w", justify=LEFT)
        self.views_label.grid(row=3, column=0, sticky="w", pady=1)

        self.playlist_count_label = Label(info_text_frame, 
                                        text="Videos in playlist: ", 
                                        bg=AppConstants.BG_SECONDARY,
                                        fg=AppConstants.TEXT_PRIMARY,
                                        anchor="w", justify=LEFT)
        self.playlist_count_label.grid(row=4, column=0, sticky="w", pady=1)
        self.playlist_count_label.grid_remove()
        
        # --- Download Options Section ---
        options_frame = ttk.LabelFrame(main_frame, text=" Download Options ", 
                                    style='DarkLabelframe.TLabelframe', 
                                    padding="15 10")
        options_frame.grid(row=3, column=0, sticky=(E, W), pady=(0, 15), padx=15)
        options_frame.columnconfigure(1, weight=1)

        # Download type
        ttk.Label(options_frame, text="Type:", 
                style='Secondary.TLabel').grid(row=0, column=0, sticky=W, padx=(0, 10))
        self.download_type = StringVar(value="video")
        ttk.Radiobutton(options_frame, text="Video", variable=self.download_type, 
                    value="video").grid(row=0, column=1, sticky=W)
        ttk.Radiobutton(options_frame, text="Audio Only", variable=self.download_type, 
                    value="audio").grid(row=0, column=2, sticky=W)
        self.download_type.trace_add('write', self._on_download_type_change)
        
        # Quality selection
        ttk.Label(options_frame, text="Quality:", 
                style='Secondary.TLabel').grid(row=1, column=0, sticky=W, 
                                            padx=(0, 10), pady=(10, 0))
        self.quality_var = StringVar(value="highest")
        self.quality_combo = ttk.Combobox(options_frame, textvariable=self.quality_var, 
                                        state="readonly", width=15)
        self.quality_combo['values'] = ('highest', '720p', '480p', '360p', 'lowest', 'list_streams')
        self.quality_combo.grid(row=1, column=1, sticky=W, pady=(10, 0))
        self.quality_combo.bind("<<ComboboxSelected>>", self._on_quality_change)
        
        # Custom filename - using custom styled entry
        ttk.Label(options_frame, text="Custom Name:", 
                style='Secondary.TLabel').grid(row=2, column=0, sticky=W, 
                                            padx=(0, 10), pady=(10, 0))
        self.filename_entry = ttk.Entry(options_frame, style='Custom.TEntry')
        self.filename_entry.grid(row=2, column=1, columnspan=2, sticky=(E, W), 
                            pady=(10, 0))

        # Download directory - using custom styled entry
        ttk.Label(options_frame, text="Download Directory:", 
                style='Secondary.TLabel').grid(row=3, column=0, sticky=W, 
                                            padx=(0, 10), pady=(10, 0))
        
        dir_frame = ttk.Frame(options_frame, style='Dark.TFrame')
        dir_frame.grid(row=3, column=1, columnspan=2, sticky=(E, W), pady=(10, 0))
        dir_frame.columnconfigure(0, weight=1)
        
        self.directory_entry = ttk.Entry(dir_frame, style='Custom.TEntry')
        self.directory_entry.insert(0, self.download_path)
        self.directory_entry.grid(row=0, column=0, sticky=(E, W), padx=(0, 10))
        
        ttk.Button(dir_frame, text="Browse", 
                command=self._browse_download_directory, 
                style='Outline.TButton').grid(row=0, column=1)

        # Playlist options
        self.playlist_options_frame = ttk.Frame(options_frame, style='Dark.TFrame')
        self.playlist_options_frame.grid(row=4, column=0, columnspan=3, 
                                    sticky=(E, W), pady=(10,0))
        self.playlist_options_frame.columnconfigure(1, weight=1)
        self.playlist_options_frame.grid_remove()

        self.download_range_var = StringVar(value="all")
        ttk.Label(self.playlist_options_frame, text="Download Range:", 
                style='Secondary.TLabel').grid(row=0, column=0, sticky=W, padx=(0, 10))
        ttk.Radiobutton(self.playlist_options_frame, text="All Videos", 
                    variable=self.download_range_var, value="all").grid(row=0, column=1, sticky=W)
        ttk.Radiobutton(self.playlist_options_frame, text="Custom Range", 
                    variable=self.download_range_var, value="custom").grid(row=0, column=2, sticky=W)
        self.download_range_var.trace_add('write', self._on_playlist_range_change)

        self.custom_range_frame = ttk.Frame(self.playlist_options_frame, style='Dark.TFrame')
        self.custom_range_frame.grid(row=1, column=1, columnspan=2, sticky=(E,W), padx=(0,10))
        self.start_index_var = StringVar(value="1")
        self.end_index_var = StringVar(value="")
        ttk.Label(self.custom_range_frame, text="From:", 
                style='Secondary.TLabel').pack(side=LEFT, padx=(0,5))
        ttk.Entry(self.custom_range_frame, textvariable=self.start_index_var, 
                width=5, style='Custom.TEntry').pack(side=LEFT, padx=(0,10))
        ttk.Label(self.custom_range_frame, text="To:", 
                style='Secondary.TLabel').pack(side=LEFT, padx=(0,5))
        ttk.Entry(self.custom_range_frame, textvariable=self.end_index_var, 
                width=5, style='Custom.TEntry').pack(side=LEFT)
        self.custom_range_frame.grid_remove()

        # --- Stream Selection (Treeview) ---
        self.stream_frame = ttk.LabelFrame(main_frame, text=" Available Streams ", 
                                        style='DarkLabelframe.TLabelframe', 
                                        padding="15 10")
        self.stream_frame.grid(row=4, column=0, sticky=(E, W), pady=(0, 15), padx=15)
        self.stream_frame.columnconfigure(0, weight=1)
        self.stream_frame.rowconfigure(0, weight=1)

        # Create a frame for treeview with scrollbar
        tree_frame = ttk.Frame(self.stream_frame, style='Dark.TFrame')
        tree_frame.grid(row=0, column=0, sticky=(N, S, E, W))
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        self.stream_tree = ttk.Treeview(tree_frame, 
                                    columns=('type', 'resolution', 'size', 'codec'), 
                                    show='headings', height=5)  # Reduced height for smaller screen
        self.stream_tree.heading('type', text='Type', anchor=W)
        self.stream_tree.heading('resolution', text='Resolution/Quality', anchor=W)
        self.stream_tree.heading('size', text='Size', anchor=W)
        self.stream_tree.heading('codec', text='Codec', anchor=W)
        
        self.stream_tree.column('type', width=80, anchor=W)
        self.stream_tree.column('resolution', width=120, anchor=W)
        self.stream_tree.column('size', width=70, anchor=W)
        self.stream_tree.column('codec', width=90, anchor=W)
        
        self.stream_tree.grid(row=0, column=0, sticky=(N, S, E, W))
        self.stream_tree.bind('<<TreeviewSelect>>', self._on_stream_select)

        # Scrollbar for treeview
        scrollbar = ttk.Scrollbar(tree_frame, orient=VERTICAL, 
                                command=self.stream_tree.yview)
        scrollbar.grid(row=0, column=1, sticky=(N, S))
        self.stream_tree.configure(yscrollcommand=scrollbar.set)
        
        self.stream_frame.grid_remove()

        # --- Progress Section ---
        progress_frame = ttk.LabelFrame(main_frame, text=" Download Progress ", 
                                    style='DarkLabelframe.TLabelframe', 
                                    padding="15 5")
        progress_frame.grid(row=5, column=0, sticky=(E, W), pady=(0, 15), padx=15)
        progress_frame.columnconfigure(0, weight=1)
        
        # Custom progress bar with percentage text
        self.progress_bar = ttk.Progressbar(progress_frame, orient=HORIZONTAL, 
                                        length=100, mode='determinate', 
                                        style='Text.Horizontal.TProgressbar')
        self.progress_bar.grid(row=0, column=0, sticky=(E, W), pady=(0, 8))
        
        self.progress_label = ttk.Label(progress_frame, text="Ready to download", 
                                    style='Secondary.TLabel', 
                                    font=AppConstants.FONT_MONO)
        self.progress_label.grid(row=1, column=0, sticky=W, pady=2)
        
        self.status_label = ttk.Label(progress_frame, text="", 
                                    style='Secondary.TLabel', 
                                    foreground=AppConstants.TEXT_SECONDARY)
        self.status_label.grid(row=1, column=2, sticky=W, pady=2)
        
        # --- Control Buttons Section ---
        button_frame = ttk.Frame(main_frame, style='Dark.TFrame', padding="15 10")
        button_frame.grid(row=6, column=0, sticky=E, padx=15)
        
        self.download_btn = ttk.Button(button_frame, text="Start Download", 
                                    command=self._start_download)
        self.download_btn.pack(side=LEFT, padx=5)

        self.cancel_btn = ttk.Button(button_frame, text="Cancel Download", 
                                command=self._cancel_download, 
                                state='disabled', style='Outline.TButton')
        self.cancel_btn.pack(side=LEFT, padx=5)

        ttk.Button(button_frame, text="Clear", 
                command=self._clear_all, style='Outline.TButton').pack(side=LEFT, padx=5)
        ttk.Button(button_frame, text="Open Folder", 
                command=self._browse_files, style='Outline.TButton').pack(side=LEFT, padx=5)
        
        # --- Status bar ---
        self.status_var = StringVar(value="Ready")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=SUNKEN, 
                            anchor=W, background=AppConstants.BG_SECONDARY, 
                            foreground=AppConstants.TEXT_SECONDARY, padding=(5,2))
        status_bar.grid(row=7, column=0, sticky=(E, W), pady=(0, 15), padx=15)

        # Add bottom padding
        ttk.Frame(main_frame, style='Dark.TFrame', height=10).grid(row=8, column=0)
    def _bind_mousewheel(self):
        """Bind mouse wheel for scrolling."""
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def _on_enter(event):
            self.canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        def _on_leave(event):
            self.canvas.unbind_all("<MouseWheel>")
        
        self.canvas.bind('<Enter>', _on_enter)
        self.canvas.bind('<Leave>', _on_leave)

    def _paste_url(self):
        """Paste URL from clipboard into the URL entry field."""
        try:
            # Get clipboard content
            clipboard_text = self.root.clipboard_get()
            
            # Check if it's a valid URL (basic check)
            if clipboard_text and ('youtube.com' in clipboard_text or 'youtu.be' in clipboard_text):
                self.url_entry.delete(0, END)
                self.url_entry.insert(0, clipboard_text.strip())
                self._update_paste_button_visibility()
                # Trigger URL change to auto-fetch
                self._on_url_change()
            else:
                # Still paste but show a warning
                self.url_entry.delete(0, END)
                self.url_entry.insert(0, clipboard_text.strip())
                self._update_paste_button_visibility()
                self._on_url_change()
                self.fetch_status_label.config(text="Pasted text may not be a valid YouTube URL", 
                                             foreground=AppConstants.ERROR_COLOR)
        except Exception as e:
            messagebox.showerror("Paste Error", f"Could not paste from clipboard:\n{e}")

    def _on_paste_event(self, event=None):
        """Handle paste events (Ctrl+V or right-click paste)."""
        # Use after_idle to let the paste complete first, then check
        self.root.after(100, self._update_paste_button_visibility)
        self.root.after(100, self._on_url_change)

    def _update_paste_button_visibility(self):
        """Show or hide the paste button based on URL entry content."""
        url_content = self.url_entry.get().strip()
        if url_content:
            self.paste_btn.grid_remove()
        else:
            self.paste_btn.grid()

    def _browse_download_directory(self):
        """Browse and set download directory."""
        directory = filedialog.askdirectory(initialdir=self.download_path)
        if directory:
            self.download_path = directory
            self.directory_entry.delete(0, END)
            self.directory_entry.insert(0, directory)
            self._save_download_path(directory)
            self._create_download_directory()

    def _on_url_change(self, event=None):
        """Handles URL entry changes and schedules auto-fetch."""
        url = self.url_entry.get().strip()
        
        # Update paste button visibility
        self._update_paste_button_visibility()
        
        # Cancel any pending auto-fetch
        if self.auto_fetch_job:
            self.root.after_cancel(self.auto_fetch_job)
        
        # Clear current info if URL is empty
        if not url:
            self._clear_info()
            self.fetch_status_label.config(text="")
            return
        
        # Show fetching status
        self.fetch_status_label.config(text="Fetching info...", 
                                     foreground=AppConstants.TEXT_SECONDARY)
        
        # Schedule auto-fetch after delay
        self.auto_fetch_job = self.root.after(AppConstants.AUTO_FETCH_DELAY, 
                                            self._auto_fetch_info)

    def _auto_fetch_info(self):
        """Automatically fetches info for the entered URL."""
        url = self.url_entry.get().strip()
        
        if not url:
            self.fetch_status_label.config(text="")
            return
        
        is_valid, is_playlist = self._is_valid_youtube_url(url)
        if not is_valid:
            self.fetch_status_label.config(text="Invalid YouTube URL", 
                                         foreground=AppConstants.ERROR_COLOR)
            return
        
        # Reset UI for new fetch
        self._clear_info()
        self.download_btn.config(state='disabled')
        self.status_var.set("Fetching information, please wait...")
        self.is_playlist_mode = is_playlist
        
        # Show/hide playlist options
        if self.is_playlist_mode:
            self.playlist_options_frame.grid()
        else:
            self.playlist_options_frame.grid_remove()

        # Run in a separate thread to prevent GUI freeze
        threading.Thread(target=self._fetch_info_thread, args=(url,), daemon=True).start()

    def _create_download_directory(self):
        """Ensures the download directory exists."""
        try:
            os.makedirs(self.download_path, exist_ok=True)
        except OSError as e:
            messagebox.showerror("Directory Error", 
                               f"Could not create download directory {self.download_path}:\n{e}")
            sys.exit(1)

    def _load_download_path(self):
        """Loads the download path from a config file or returns default."""
        config_file = "config.ini"
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    path = f.read().strip()
                    if os.path.isdir(path):
                        return path
            except IOError:
                pass
        return AppConstants.DEFAULT_DOWNLOAD_PATH

    def _save_download_path(self, path):
        """Saves the download path to a config file."""
        config_file = "config.ini"
        try:
            with open(config_file, 'w') as f:
                f.write(path)
        except IOError as e:
            messagebox.showwarning("Save Error", 
                                 f"Could not save download path to config file:\n{e}")

    def _is_valid_youtube_url(self, url):
        """Checks if the URL is a valid YouTube video or playlist URL."""
        youtube_regex_video = r'(https?://)?(www\.)?(youtube|youtu)\.(com|be)/(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})'
        youtube_regex_playlist = r'(https?://)?(www\.)?(youtube)\.com/playlist\?list=([a-zA-Z0-9_-]+)'
        
        is_video = re.match(youtube_regex_video, url) is not None
        is_playlist = re.match(youtube_regex_playlist, url) is not None
        
        if is_video and 'list=' in url:
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            if 'list' in query_params:
                is_playlist = True
        
        return is_video or is_playlist, is_playlist

    def _fetch_info_thread(self, url):
        """Worker thread to fetch YouTube video/playlist metadata."""
        try:
            if self.is_playlist_mode:
                yt_obj = Playlist(url)
                # Ensure videos are loaded for count, etc.
                # Accessing yt_obj.videos will trigger loading if not already done.
                _ = yt_obj.video_urls 
                video_count = len(yt_obj.video_urls)
                info = {
                    'title': yt_obj.title,
                    'uploader': "Playlist",
                    'duration': None,
                    'views': None,
                    'thumbnail': None,
                    'age_restricted': False,
                    'video_id': None,
                    'video_count': video_count
                }
                streams = [] # Playlists don't have a single stream list
                
            else:
                yt_obj = YouTube(url)
                # Removed prefetch() call as it's not needed in newer pytubefix versions
                
                info = {
                    'title': yt_obj.title,
                    'duration': yt_obj.length,
                    'uploader': yt_obj.author,
                    'views': yt_obj.views,
                    'publish_date': yt_obj.publish_date,
                    'thumbnail': yt_obj.thumbnail_url,
                    'age_restricted': yt_obj.age_restricted,
                    'video_id': yt_obj.video_id,
                    'video_count': 1
                }
                
                # Optimized stream filtering with new attributes
                streams_all = yt_obj.streams
                streams = []
                
                for stream in streams_all:
                    stream_type = "Unknown"
                    if stream.includes_video_track and stream.includes_audio_track and stream.is_progressive:
                        stream_type = "Video+Audio"
                    elif stream.includes_video_track and not stream.includes_audio_track:
                        stream_type = "Video Only"
                    elif stream.includes_audio_track and not stream.includes_video_track:
                        stream_type = "Audio Only"
                    else:
                        continue # Skip streams that are neither pure audio, pure video, nor progressive

                    size = stream.filesize if stream.filesize is not None else "Calculating..."
                    
                    streams.append({
                        'type': stream_type,
                        'resolution': stream.resolution or stream.abr, # Use abr for audio streams
                        'size': size,
                        'codec': stream.mime_type.split('/')[-1] if stream.mime_type else 'N/A',
                        'stream_obj': stream
                    })
                
                # Sort streams by type and then resolution/quality for better display
                streams.sort(key=lambda x: (
                    0 if x['type'] == "Video+Audio" else 
                    1 if x['type'] == "Video Only" else 
                    2 if x['type'] == "Audio Only" else 3,
                    self._get_resolution_value(x['resolution'])
                ), reverse=True)
            
            self.current_yt_object = yt_obj
            self.root.after(0, self._update_info_gui, info, streams)
            
        except Exception as e:
            self.root.after(0, self._fetch_info_error, str(e))

    def _get_resolution_value(self, resolution):
        """Convert resolution string to numeric value for sorting."""
        if resolution is None:
            return 0
        # Handle 'p' for video resolutions
        if isinstance(resolution, str) and resolution.endswith('p'):
            try:
                return int(resolution[:-1])
            except ValueError:
                return 0
        # Handle audio bitrates (e.g., '128kbps')
        elif isinstance(resolution, str) and resolution.endswith('bps'):
            try:
                # Convert to integer kbps for sorting
                return int(re.search(r'(\d+)', resolution).group(1)) if re.search(r'(\d+)', resolution) else 0
            except ValueError:
                return 0
        return 0

    def _update_info_gui(self, video_info, streams):
        """Updates the GUI with fetched video/playlist information."""
        self.current_video_info = video_info
        self.current_streams = streams
        
        # Update labels - using config instead of direct text assignment for better wrapping
        self.title_label.config(text=f"Title: {video_info['title'] or 'N/A'}")
        self.author_label.config(text=f"Author: {video_info['uploader'] or 'N/A'}")
        self.duration_label.config(text=f"Duration: {self._format_duration(video_info['duration']) or 'N/A'}")
        
        # Format views with commas
        views_text = f"Views: {video_info['views']:,}" if video_info['views'] else 'Views: N/A'
        self.views_label.config(text=views_text)

        if self.is_playlist_mode:
            self.playlist_count_label.config(text=f"Videos in playlist: {video_info['video_count']}")
            self.playlist_count_label.grid()
            self.duration_label.grid_remove()
            self.views_label.grid_remove()
            # Disable quality/stream selection for playlists as it's handled per video
            self.quality_combo.config(state='disabled')
            self.stream_frame.grid_remove() 
        else:
            self.playlist_count_label.grid_remove()
            self.duration_label.grid()
            self.views_label.grid()
            self.quality_combo.config(state='readonly')
        
        # Set default filename
        if not self.filename_entry.get().strip() and not self.is_playlist_mode:
            safe_title = self._get_safe_filename(video_info['title'] or 'downloaded_video')
            self.filename_entry.delete(0, END)
            self.filename_entry.insert(0, safe_title)
        
        # Load thumbnail
        if video_info['thumbnail']:
            threading.Thread(target=self._load_thumbnail_thread, 
                        args=(video_info['thumbnail'],), daemon=True).start()
        else:
            self.thumbnail_label.config(image='', text="No Thumbnail\nAvailable")

        # Populate streams tree (only if not playlist and 'list_streams' is selected)
        if not self.is_playlist_mode:
            self._populate_streams_tree(streams)
        
        # Enable download button
        self.download_btn.config(state='normal')
        self.status_var.set("Information fetched. Ready to download.")
        self.status_label.config(text="")
        self.fetch_status_label.config(text="Info fetched successfully", 
                                    foreground=AppConstants.SUCCESS_COLOR)

        # Show/hide stream frame based on quality selection
        self._on_quality_change()

    def _fetch_info_error(self, error_msg):
        """Handles errors during fetching video/playlist information."""
        self.fetch_status_label.config(text=f"Error: {error_msg[:50]}...", 
                                     foreground=AppConstants.ERROR_COLOR)
        self._clear_info()
        self.download_btn.config(state='disabled')
        self.status_var.set("Error fetching info.")
        self.status_label.config(text=f"Error: {error_msg[:100]}...", 
                               foreground=AppConstants.ERROR_COLOR)

    def _load_thumbnail_thread(self, thumbnail_url):
        """Worker thread to load and resize thumbnail image."""
        try:
            response = requests.get(thumbnail_url, timeout=5)
            response.raise_for_status()
            image = Image.open(BytesIO(response.content))
            image.thumbnail(AppConstants.THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(image)
            self.root.after(0, lambda: self._update_thumbnail_gui(photo))
        except Exception:
            self.root.after(0, lambda: self.thumbnail_label.config(text="Thumbnail Failed", image=''))

    def _update_thumbnail_gui(self, photo):
        """Updates the thumbnail label in the GUI."""
        self.thumbnail_label.config(image=photo, text="")
        self.thumbnail_label.image = photo

    def _populate_streams_tree(self, streams):
        """Populates the Treeview with available streams."""
        for item in self.stream_tree.get_children():
            self.stream_tree.delete(item)
        
        if not streams:
            self.stream_tree.insert('', 'end', values=('No streams found', '', '', ''))
            return

        for i, stream_data in enumerate(streams):
            size_str = (self._format_bytes(stream_data['size']) 
                       if stream_data['size'] != "Calculating..." 
                       else stream_data['size'])
            self.stream_tree.insert('', 'end', iid=str(i), values=(
                stream_data['type'],
                stream_data['resolution'],
                size_str,
                stream_data['codec']
            ))

    def _on_stream_select(self, event=None):
        """Handles selection of a stream in the Treeview."""
        selected_item_id = self.stream_tree.focus()
        if not selected_item_id:
            return

        try:
            stream_index = int(selected_item_id)
            if stream_index < len(self.current_streams):
                selected_stream_data = self.current_streams[stream_index]
                
                if selected_stream_data['size'] == "Calculating...":
                    stream_obj = selected_stream_data['stream_obj']
                    threading.Thread(target=self._calculate_filesize_thread, 
                                   args=(stream_index, stream_obj), daemon=True).start()
        except (ValueError, IndexError):
            pass

    def _calculate_filesize_thread(self, stream_index, stream_obj):
        """Calculates filesize for a specific stream in a thread."""
        try:
            filesize = stream_obj.filesize
            self.root.after(0, self._update_stream_filesize_gui, stream_index, filesize)
        except Exception:
            self.root.after(0, self._update_stream_filesize_gui, stream_index, "N/A")

    def _update_stream_filesize_gui(self, stream_index, filesize):
        """Updates the Treeview with calculated filesize."""
        try:
            if stream_index < len(self.current_streams):
                self.current_streams[stream_index]['size'] = filesize
                item_id = str(stream_index)
                current_values = list(self.stream_tree.item(item_id, 'values'))
                current_values[2] = self._format_bytes(filesize) if filesize is not None else "N/A"
                self.stream_tree.item(item_id, values=tuple(current_values))
        except (ValueError, IndexError):
            pass

    def _on_download_type_change(self, *args):
        """Adjusts quality options and stream view based on download type."""
        download_type = self.download_type.get()
        if download_type == "audio":
            self.quality_combo['values'] = ('highest', '192kbps', '128kbps', 'lowest', 'list_streams')
            if self.quality_var.get() not in ('highest', '192kbps', '128kbps', 'lowest', 'list_streams'):
                self.quality_var.set("highest")
        else: # video
            self.quality_combo['values'] = ('highest', '1080p', '720p', '480p', '360p', 'lowest', 'list_streams')
            if self.quality_var.get() not in ('highest', '1080p', '720p', '480p', '360p', 'lowest', 'list_streams'):
                self.quality_var.set("highest")
        self._on_quality_change()

    def _on_quality_change(self, event=None):
        """Shows/hides the stream selection treeview based on quality choice."""
        # Only show stream frame if not in playlist mode and 'list_streams' is chosen
        if not self.is_playlist_mode and self.quality_var.get() == 'list_streams':
            self.stream_frame.grid()
        else:
            self.stream_frame.grid_remove()

    def _on_playlist_range_change(self, *args):
        """Shows/hides custom range entry for playlists."""
        if self.download_range_var.get() == "custom":
            self.custom_range_frame.grid()
        else:
            self.custom_range_frame.grid_remove()

    def _start_download(self):
        """Initiates the download process in a new thread."""
        if not self.current_yt_object:
            messagebox.showerror("Download Error", 
                               "Please fetch video/playlist information first.")
            return
        
        filename = self.filename_entry.get().strip()
        if not filename and not self.is_playlist_mode: # Filename not required for playlist directly
            messagebox.showerror("Input Error", 
                               "Please enter a filename for single video download.")
            return

        if self.is_playlist_mode and self.download_range_var.get() == "custom":
            try:
                start_index_str = self.start_index_var.get()
                end_index_str = self.end_index_var.get()

                start_index = int(start_index_str) if start_index_str else 1
                end_index = (int(end_index_str) 
                           if end_index_str 
                           else self.current_video_info['video_count'])
                
                if not (1 <= start_index <= end_index <= self.current_video_info['video_count']):
                    messagebox.showerror("Input Error", 
                                       f"Invalid playlist range. Please enter valid numbers within 1 and {self.current_video_info['video_count']}.")
                    return
            except ValueError:
                messagebox.showerror("Input Error", 
                                   "Invalid playlist range. Please enter numbers for start and end.")
                return

        self.download_btn.config(state='disabled')
        self.cancel_btn.config(state='normal')
        self.progress_bar['value'] = 0
        self.progress_label.config(text="Initializing download...")
        self.status_var.set("Starting download...")
        self.status_label.config(text="", foreground=AppConstants.TEXT_SECONDARY)
        self.download_canceled = False
        self.downloaded_file_path = None

        self.current_download_thread = threading.Thread(
            target=self._download_thread_manager, 
            daemon=True
        )
        self.current_download_thread.start()

    def _download_thread_manager(self):
        """Manages the download process, handling single videos or playlists."""
        try:
            if self.is_playlist_mode:
                self._download_playlist()
            else:
                self._download_single_video()
        except Exception as e:
            if not self.download_canceled:
                self.root.after(0, self._download_error, str(e))
        finally:
            self.root.after(0, self._download_finished)

    def _download_single_video(self):
        """Downloads a single YouTube video based on current settings."""
        if self.download_canceled:
            return False

        download_type = self.download_type.get()
        quality = self.quality_var.get()
        filename_base = self._get_safe_filename(self.filename_entry.get().strip())
        
        selected_stream_obj = None
        
        try: # Wrap stream selection in try-except for more specific errors
            if quality == 'list_streams':
                selection = self.stream_tree.selection()
                if not selection:
                    self.root.after(0, lambda: messagebox.showerror("Selection Error", 
                                                                  "Please select a stream from the list."))
                    return False
                
                try:
                    stream_index = int(selection[0])
                    if stream_index < len(self.current_streams):
                        selected_stream_obj = self.current_streams[stream_index]['stream_obj']
                    else:
                        self.root.after(0, lambda: messagebox.showerror("Error", 
                                                                      "Selected stream not found. Please re-fetch info."))
                        return False
                except (ValueError, IndexError):
                    self.root.after(0, lambda: messagebox.showerror("Error", 
                                                                  "Invalid stream selection."))
                    return False
            else:
                if download_type == 'audio':
                    # Filter for audio-only streams
                    streams_filtered = self.current_yt_object.streams.filter(only_audio=True, mime_type="audio/mp4")
                    
                    if quality == 'highest':
                        selected_stream_obj = streams_filtered.order_by('abr').desc().first()
                    elif quality == 'lowest':
                        selected_stream_obj = streams_filtered.order_by('abr').asc().first()
                    elif quality.endswith('kbps'):
                        abr_value = re.match(r'(\d+)kbps', quality)
                        if abr_value:
                            selected_stream_obj = streams_filtered.filter(abr=f"{abr_value.group(1)}kbps").first()
                    
                    # Fallback if specific quality not found or generic 'highest'
                    if not selected_stream_obj:
                         selected_stream_obj = self.current_yt_object.streams.get_audio_only() # Gets highest abr audio
                    
                    file_extension = 'mp3' # Default for audio
                    
                else: # video
                    # Filter for progressive (video+audio) streams
                    streams_filtered = self.current_yt_object.streams.filter(progressive=True, mime_type="video/mp4")
                    
                    if quality == 'highest':
                        selected_stream_obj = streams_filtered.order_by('resolution').desc().first()
                    elif quality == 'lowest':
                        selected_stream_obj = streams_filtered.order_by('resolution').asc().first()
                    elif quality.endswith('p'):
                        selected_stream_obj = streams_filtered.filter(res=quality).first()

                    # Fallback if specific quality not found or generic 'highest'
                    if not selected_stream_obj:
                        selected_stream_obj = self.current_yt_object.streams.get_highest_resolution() # Gets highest res progressive
                    
                    file_extension = 'mp4' # Default for video
        
            if not selected_stream_obj:
                self.root.after(0, lambda: messagebox.showerror("Download Error", 
                                                              "No suitable stream found for download. Try 'List Streams' or different quality."))
                return False

            self.current_yt_object.register_on_progress_callback(self._on_progress)
            
            # Ensure filename doesn't have multiple extensions
            if filename_base.endswith(f".{file_extension}"):
                final_filename = filename_base
            else:
                final_filename = f"{filename_base}.{file_extension}"
            
            self.root.after(0, lambda: self.status_label.config(
                text=f"Downloading: {selected_stream_obj.resolution or selected_stream_obj.abr} ({selected_stream_obj.mime_type})", 
                foreground=AppConstants.TEXT_PRIMARY))
            
            file_path = selected_stream_obj.download(
                output_path=self.download_path,
                filename=final_filename
            )
            self.downloaded_file_path = file_path
            self.root.after(0, self._download_success)
            return True
            
        except Exception as e:
            if not self.download_canceled:
                self.root.after(0, self._download_error, f"Error during stream selection or download: {e}")
            return False

    def _download_playlist(self):
        """Downloads videos from a playlist."""
        if not self.current_yt_object or not self.is_playlist_mode:
            self.root.after(0, lambda: messagebox.showerror("Download Error", 
                                                          "Playlist object not available."))
            return False
        
        download_type = self.download_type.get()
        quality = self.quality_var.get() # Quality selected for single video, apply to all in playlist

        playlist_title = self._get_safe_filename(self.current_yt_object.title or "playlist_downloads")
        playlist_download_path = os.path.join(self.download_path, playlist_title)
        try:
            os.makedirs(playlist_download_path, exist_ok=True)
        except OSError as e:
            self.root.after(0, lambda: self._download_error(f"Could not create playlist directory: {e}"))
            return False

        start_index = 0
        end_index = len(self.current_yt_object.video_urls) - 1
        
        if self.download_range_var.get() == "custom":
            try:
                start_index_input = self.start_index_var.get()
                end_index_input = self.end_index_var.get()
                
                start_index = (int(start_index_input) - 1) if start_index_input else 0
                end_index = (int(end_index_input) - 1 
                           if end_index_input 
                           else len(self.current_yt_object.video_urls) - 1)
                           
                if not (0 <= start_index <= end_index < len(self.current_yt_object.video_urls)):
                     raise ValueError("Invalid range.")
            except ValueError:
                self.root.after(0, lambda: self._download_error("Invalid playlist range specified."))
                return False

        videos_to_download = self.current_yt_object.videos[start_index : end_index + 1]
        total_videos = len(videos_to_download)
        
        self.root.after(0, lambda: self.status_label.config(
            text=f"Downloading playlist '{playlist_title}'. Total videos: {total_videos}", 
            foreground=AppConstants.TEXT_PRIMARY))

        downloaded_count = 0
        for i, video in enumerate(videos_to_download):
            if self.download_canceled:
                self.root.after(0, lambda: self.status_label.config(
                    text="Playlist download canceled.", 
                    foreground=AppConstants.ERROR_COLOR))
                return False
            
            try:
                video.register_on_progress_callback(self._on_progress)
                
                self.root.after(0, lambda v_title=video.title, idx=i: 
                              self.progress_label.config(
                                  text=f"Video {idx+1}/{total_videos}: {v_title[:50]}..."))
                
                stream = None
                file_extension = 'mp4' # Default
                
                if download_type == 'audio':
                    # Get highest quality audio for each video in playlist
                    stream = video.streams.filter(only_audio=True, mime_type="audio/mp4").order_by('abr').desc().first()
                    if not stream: # Fallback
                        stream = video.streams.get_audio_only()
                    file_extension = 'mp3'
                else: # video
                    # Get highest quality progressive video for each video in playlist
                    stream = video.streams.filter(progressive=True, mime_type="video/mp4").order_by('resolution').desc().first()
                    if not stream: # Fallback
                        stream = video.streams.get_highest_resolution()

                if not stream:
                    self.root.after(0, lambda v_title=video.title: 
                                  self.status_label.config(
                                      text=f"Skipping '{v_title}' - no suitable stream found.", 
                                      foreground=AppConstants.ERROR_COLOR))
                    continue

                safe_video_title = self._get_safe_filename(video.title)
                file_path = stream.download(
                    output_path=playlist_download_path,
                    filename=f"{safe_video_title}.{file_extension}"
                )
                downloaded_count += 1
                self.root.after(0, lambda: self.progress_bar.config(
                    value=((i + 1) / total_videos) * 100))

            except Exception as e:
                if not self.download_canceled:
                    self.root.after(0, lambda v_title=video.title, err=e: 
                                  self.status_label.config(
                                      text=f"Error downloading '{v_title}': {err}", 
                                      foreground=AppConstants.ERROR_COLOR))
                continue
        
        if not self.download_canceled:
            self.downloaded_file_path = playlist_download_path
            self.root.after(0, lambda: self._download_success(
                is_playlist=True, 
                downloaded_count=downloaded_count, 
                total_count=total_videos))
        return True

    def _cancel_download(self):
        """Sets the flag to cancel the current download."""
        if messagebox.askyesno("Cancel Download", 
                             "Are you sure you want to cancel the current download?"):
            self.download_canceled = True
            self.status_var.set("Download cancellation requested...")
            self.progress_label.config(text="Canceling...")

    def _on_progress(self, stream, chunk, bytes_remaining):
        """Callback for pytubefix to update progress bar."""
        if self.download_canceled:

            raise Exception("Download canceled by user.") 
            
        total_size = stream.filesize
        if total_size:
            bytes_downloaded = total_size - bytes_remaining
            percentage = (bytes_downloaded / total_size) * 100
            
            self.root.after(0, self._update_progress_gui, percentage, bytes_downloaded, total_size)
    
    def _update_progress_gui(self, percentage, downloaded, total):
        """Updates the progress bar and labels on the GUI thread."""
        self.progress_bar['value'] = percentage
        # Update the progress bar text with percentage
        self.style.configure('Text.Horizontal.TProgressbar', text=f'{percentage:.1f}%')
        downloaded_str = self._format_bytes(downloaded)
        total_str = self._format_bytes(total)
        self.progress_label.config(text=f"Progress: {percentage:.1f}% ({downloaded_str}/{total_str})")
    
    def _download_success(self, is_playlist=False, downloaded_count=0, total_count=0):
        """Handles a successful download completion."""
        self.progress_bar['value'] = 100
        self.style.configure('Text.Horizontal.TProgressbar', text='100%')
        self.status_var.set("Download completed successfully!")
        self.status_label.config(text="Download finished.", 
                               foreground=AppConstants.SUCCESS_COLOR)

        if is_playlist:
            msg = (f"Playlist download completed!\n\n"
                   f"Downloaded {downloaded_count} out of {total_count} videos.\n"
                   f"Location: {self.downloaded_file_path}")
        else:
            try:
                file_size = (os.path.getsize(self.downloaded_file_path) 
                           if self.downloaded_file_path and os.path.exists(self.downloaded_file_path) 
                           else 0)
                size_str = self._format_bytes(file_size)
                msg = (f"Download completed!\n\n"
                       f"File: {os.path.basename(self.downloaded_file_path) if self.downloaded_file_path else 'N/A'}\n"
                       f"Size: {size_str}\n"
                       f"Location: {os.path.dirname(self.downloaded_file_path) if self.downloaded_file_path else 'N/A'}")
            except Exception:
                msg = "Download completed successfully, but file details could not be retrieved."
        
        self.progress_label.config(text="Download completed!")
        messagebox.showinfo("Success", msg)
        self._download_finished()
    
    def _download_error(self, error_msg):
        """Handles download errors."""
        if not self.download_canceled:
            messagebox.showerror("Download Error", f"Download failed:\n{error_msg}")
            self.status_var.set("Download failed.")
            self.status_label.config(text=f"Error: {error_msg[:100]}...", 
                                   foreground=AppConstants.ERROR_COLOR)
        self._download_finished()
    
    def _download_finished(self):
        """Resets UI elements after a download (success or failure)."""
        self.download_btn.config(state='normal')
        self.cancel_btn.config(state='disabled')
        if self.progress_bar['value'] != 100:
            self.progress_bar['value'] = 0
            self.style.configure('Text.Horizontal.TProgressbar', text='0%')
            self.progress_label.config(text="Ready to download")
        self.download_canceled = False
        self.current_download_thread = None

    def _clear_all(self):
        """Clears all input fields and video information."""
        self.url_entry.delete(0, END)
        self.filename_entry.delete(0, END)
        self.download_type.set("video")
        self.quality_var.set("highest")
        self.download_range_var.set("all")
        self.start_index_var.set("1")
        self.end_index_var.set("")
        self._clear_info()
        self.progress_bar['value'] = 0
        self.style.configure('Text.Horizontal.TProgressbar', text='0%')
        self.progress_label.config(text="Ready to download")
        self.status_var.set("Ready")
        self.status_label.config(text="", foreground=AppConstants.TEXT_SECONDARY)
        self.stream_frame.grid_remove()
        self.playlist_options_frame.grid_remove()
        self.custom_range_frame.grid_remove()
        self.download_btn.config(state='disabled')
        self.fetch_status_label.config(text="")
        self.quality_combo.config(state='readonly') # Re-enable quality combo
        # Show paste button again
        self._update_paste_button_visibility()

    def _clear_info(self):
        """Clears displayed video information."""
        self.current_yt_object = None
        self.current_video_info = None
        self.current_streams = []
        self.is_playlist_mode = False # Reset playlist mode
        
        self.title_label.config(text="Title: ")
        self.author_label.config(text="Author: ")
        self.duration_label.config(text="Duration: ")
        self.views_label.config(text="Views: ")
        self.playlist_count_label.config(text="Videos in playlist: ")
        self.playlist_count_label.grid_remove()
        self.duration_label.grid()
        self.views_label.grid()
        
        self.thumbnail_label.config(text="No Image", image='')
        self.thumbnail_label.image = None

        for item in self.stream_tree.get_children():
            self.stream_tree.delete(item)

    def _browse_files(self):
        """Opens the download directory in the system's file explorer."""
        try:
            path = os.path.abspath(self.download_path)
            if not os.path.exists(path):
                messagebox.showwarning("Open Folder", 
                                     f"Download folder does not exist: {path}")
                return

            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                os.system(f'open "{path}"')
            else:
                os.system(f'xdg-open "{path}"')
        except Exception as e:
            messagebox.showerror("Error", f"Could not open download folder:\n{e}")

    def _get_safe_filename(self, title):
        """Removes invalid characters and shortens title for use as a filename."""
        if not title:
            return "downloaded_video"
            
        invalid_chars_regex = r'[<>:"/\\|?*\']'
        title = re.sub(invalid_chars_regex, '', title)
        title = title.replace('.', '')
        title = title.replace(' ', '_')
        title = re.sub(r'__+', '_', title)
        title = title.strip('_')
        return title[:100]
    
    def _format_bytes(self, bytes_val):
        """Formats byte count into a human-readable string (e.g., 1.2 GB)."""
        if bytes_val is None or not isinstance(bytes_val, (int, float)):
            return "Unknown"
        
        if bytes_val == 0:
            return "0 B"
        
        sizes = ['B', 'KB', 'MB', 'GB', 'TB']
        i = 0
        while bytes_val >= 1024 and i < len(sizes) - 1:
            bytes_val /= 1024.0
            i += 1
        
        return f"{bytes_val:.2f} {sizes[i]}"
    
    def _format_duration(self, seconds):
        """Formats duration in seconds to HH:MM:SS or MM:SS."""
        if not seconds or not isinstance(seconds, (int, float)) or seconds < 0:
            return "N/A"
        
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        
        if hours > 0:
            return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
        else:
            return f"{int(minutes):02d}:{int(seconds):02d}"

    def _on_closing(self):
        """Handles application closing, asking to confirm if download is active."""
        if self.current_download_thread and self.current_download_thread.is_alive():
            if messagebox.askyesno("Exit Application", 
                                 "A download is in progress. Do you want to cancel and exit?"):
                self.download_canceled = True 
                time.sleep(0.5) 
                self.root.destroy()
        else:
            self.root.destroy()


def main():
    """Main function to create and run the Tkinter application."""
    root = Tk()
    app = YouTubeDownloaderGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()