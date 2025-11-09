import tkinter as tk
from tkinter import messagebox, ttk
import requests
from dotenv import load_dotenv
import os
import threading
import time
from PIL import Image, ImageTk
from io import BytesIO

# Load API key
load_dotenv()
API_KEY = os.getenv("TMDB_API_KEY")
BASE_URL = "https://api.themoviedb.org/3"
IMG_BASE = "https://image.tmdb.org/t/p/w342"  # medium poster size

if not API_KEY:
    raise SystemExit("TMDB_API_KEY not found in .env — add TMDB_API_KEY=your_key")

# ----- New Color Scheme -----
BG = "#f8f9fa"              # Light gray background
CARD_BG = "#ffffff"         # White card background
ACCENT = "#4361ee"          # Vibrant blue
ACCENT_HOVER = "#3a56d4"    # Darker blue for hover
SECONDARY = "#7209b7"       # Purple for secondary elements
TEXT_PRIMARY = "#212529"    # Dark gray for text
TEXT_SECONDARY = "#6c757d"  # Medium gray for secondary text
BORDER = "#dee2e6"          # Light border
SUCCESS = "#38b000"         # Green for positive indicators

# Create a session for connection pooling
session = requests.Session()

# ----- Helper: fetch recommendations (background thread) -----
def fetch_and_show(query):
    try:
        update_status("Searching for movies...")
        
        # search
        s_url = f"{BASE_URL}/search/movie"
        s_params = {"api_key": API_KEY, "query": query}
        
        try:
            s_res = session.get(s_url, params=s_params, timeout=15).json()
        except requests.exceptions.ConnectionError as e:
            root.after(0, lambda: update_status("Connection error. Retrying..."))
            time.sleep(2)  # Wait before retry
            s_res = session.get(s_url, params=s_params, timeout=15).json()
        
        results = s_res.get("results", [])
        if not results:
            root.after(0, lambda: update_status("No movies found. Try a different search."))
            root.after(0, lambda: messagebox.showinfo("No results", "No movie found with that name."))
            root.after(0, clear_list_and_card)
            return

        update_status(f"Found '{results[0]['title']}'. Getting recommendations...")
        
        # choose first result's id
        movie_id = results[0]["id"]

        # recommendations
        r_url = f"{BASE_URL}/movie/{movie_id}/recommendations"
        r_params = {"api_key": API_KEY}
        
        try:
            r_res = session.get(r_url, params=r_params, timeout=15).json()
        except requests.exceptions.ConnectionError as e:
            root.after(0, lambda: update_status("Connection error. Retrying..."))
            time.sleep(2)  # Wait before retry
            r_res = session.get(r_url, params=r_params, timeout=15).json()
        
        recs = r_res.get("results", [])[:15]  # increased to 15 recs

        # prepare items: title, overview, poster_path, rating
        items = []
        for r in recs:
            rating = r.get("vote_average", 0)
            items.append({
                "title": r.get("title", "Unknown"),
                "overview": r.get("overview", "No overview available."),
                "poster": r.get("poster_path"),
                "rating": rating,
                "release_date": r.get("release_date", "Unknown")
            })

        # update UI on main thread
        root.after(0, lambda: populate_list(items, query))
    except Exception as e:
        root.after(0, lambda: messagebox.showerror("Error", f"Network error:\n{str(e)}"))
        root.after(0, clear_list_and_card)
        root.after(0, lambda: update_status("Error fetching data. Check connection."))
    finally:
        root.after(0, lambda: set_busy(False))

# ----- UI update helpers -----
def set_busy(flag: bool):
    if flag:
        search_btn.config(state="disabled", bg="#adb5bd")
        clear_btn.config(state="disabled", bg="#adb5bd")
        entry.config(state="disabled")
        progress_bar.start()
    else:
        search_btn.config(state="normal", bg=ACCENT)
        clear_btn.config(state="normal", bg=SECONDARY)
        entry.config(state="normal")
        progress_bar.stop()

def clear_list_and_card():
    listbox.delete(0, tk.END)
    show_card(None)
    update_status("Enter a movie name to get recommendations")

def populate_list(items, query):
    listbox.delete(0, tk.END)
    listbox.items = items  # attach to listbox for access
    
    if not items:
        listbox.insert(tk.END, "No recommendations found")
        update_status(f"No recommendations found for '{query}'")
        show_card(None)
    else:
        # Sort by rating (highest first)
        items.sort(key=lambda x: x.get("rating", 0), reverse=True)
        
        for i, it in enumerate(items):
            rating = it.get("rating", 0)
            rating_str = f"⭐ {rating:.1f}" if rating > 0 else "No rating"
            # Truncate long titles
            title = it['title']
            if len(title) > 35:
                title = title[:32] + "..."
            listbox.insert(tk.END, f"{title} ({rating_str})")
        
        update_status(f"Found {len(items)} recommendations for '{query}'")
        listbox.selection_clear(0, tk.END)
        listbox.selection_set(0)
        on_select(None)  # show first item

def show_card(item):
    # clear previous
    for widget in card_frame.winfo_children():
        widget.destroy()
    card_frame.image_ref = None

    if not item:
        # Show placeholder
        placeholder = tk.Frame(card_frame, bg=CARD_BG, relief="flat", bd=1)
        placeholder.pack(fill="both", expand=True, padx=10, pady=10)
        
        tk.Label(placeholder, text="🎬", bg=CARD_BG, fg=BORDER, font=("Helvetica", 48)).pack(expand=True, pady=20)
        tk.Label(placeholder, text="Select a movie", bg=CARD_BG, fg=TEXT_SECONDARY, 
                font=("Helvetica", 14, "bold")).pack(pady=10)
        tk.Label(placeholder, text="Choose a movie from the list to see details", 
                bg=CARD_BG, fg=TEXT_SECONDARY, font=("Helvetica", 10), wraplength=300).pack(pady=5)
        return

    # Main card container - SIMPLIFIED LAYOUT
    main_container = tk.Frame(card_frame, bg=CARD_BG)
    main_container.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Create a scrollable frame for the entire card
    canvas = tk.Canvas(main_container, bg=CARD_BG, highlightthickness=0)
    scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
    scrollable_frame = tk.Frame(canvas, bg=CARD_BG)
    
    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    
    # Mouse wheel binding for scrolling
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    
    canvas.bind("<MouseWheel>", _on_mousewheel)
    scrollable_frame.bind("<MouseWheel>", _on_mousewheel)
    
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    
    # Content inside scrollable frame - SIMPLIFIED LAYOUT
    content_frame = scrollable_frame
    
    # Movie Title - FULL WIDTH AT TOP
    title_frame = tk.Frame(content_frame, bg=CARD_BG)
    title_frame.pack(fill="x", padx=10, pady=(10, 5))
    
    title_text = item["title"]
    title_label = tk.Label(title_frame, text=title_text, bg=CARD_BG, fg=TEXT_PRIMARY, 
                          font=("Helvetica", 18, "bold"), wraplength=400, justify="center")
    title_label.pack(fill="x", pady=5)
    
    # Rating and year below title
    details_frame = tk.Frame(content_frame, bg=CARD_BG)
    details_frame.pack(fill="x", padx=10, pady=(0, 15))
    
    rating = item.get("rating", 0)
    release_date = item.get("release_date", "Unknown")
    
    if rating > 0:
        rating_color = SUCCESS if rating >= 7.0 else TEXT_PRIMARY
        rating_text = f"⭐ {rating:.1f}/10"
    else:
        rating_text = "No rating"
    
    year = release_date.split("-")[0] if release_date != "Unknown" and "-" in release_date else release_date
    
    details_text = f"{rating_text}"
    if year != "Unknown":
        details_text += f" • {year}"
    
    details_label = tk.Label(details_frame, text=details_text, bg=CARD_BG, fg=TEXT_SECONDARY,
                           font=("Helvetica", 12))
    details_label.pack(pady=5)
    
    # Poster - CENTERED
    poster_path = item.get("poster")
    if poster_path:
        try:
            poster_frame = tk.Frame(content_frame, bg=CARD_BG)
            poster_frame.pack(fill="x", pady=10)
            
            img_url = IMG_BASE + poster_path
            resp = session.get(img_url, timeout=15)
            img = Image.open(BytesIO(resp.content))
            img.thumbnail((220, 330))
            photo = ImageTk.PhotoImage(img)
            poster_lbl = tk.Label(poster_frame, image=photo, bg=CARD_BG)
            poster_lbl.image = photo
            poster_lbl.pack(pady=10)
            card_frame.image_ref = photo
        except Exception as e:
            # fallback if image fails
            poster_placeholder = tk.Frame(content_frame, bg=CARD_BG)
            poster_placeholder.pack(fill="x", pady=10)
            tk.Label(poster_placeholder, text="No Image Available", bg=BORDER, fg=TEXT_SECONDARY, 
                   width=30, height=15, font=("Helvetica", 10)).pack(pady=10)
    
    # Overview section
    ov_section = tk.Frame(content_frame, bg=CARD_BG)
    ov_section.pack(fill="both", expand=True, padx=10, pady=10)
    
    tk.Label(ov_section, text="Overview", bg=CARD_BG, fg=TEXT_PRIMARY, 
            font=("Helvetica", 14, "bold")).pack(anchor="w", pady=(0, 8))
    
    # Text widget for overview with proper scrolling
    ov_text_frame = tk.Frame(ov_section, bg=CARD_BG)
    ov_text_frame.pack(fill="both", expand=True)
    
    ov_text = tk.Text(ov_text_frame, wrap="word", bg=CARD_BG, fg=TEXT_PRIMARY, 
                     relief="flat", font=("Helvetica", 11), padx=10, pady=10,
                     highlightthickness=1, highlightcolor=BORDER, highlightbackground=BORDER,
                     height=8)
    ov_text.insert("1.0", item["overview"] or "No overview available.")
    ov_text.config(state="disabled")
    
    # Add scrollbar to text widget
    text_scrollbar = ttk.Scrollbar(ov_text_frame, orient="vertical", command=ov_text.yview)
    ov_text.configure(yscrollcommand=text_scrollbar.set)
    
    ov_text.pack(side="left", fill="both", expand=True)
    text_scrollbar.pack(side="right", fill="y")
    
    # Bind mouse wheel to text widget
    def _on_text_mousewheel(event):
        ov_text.yview_scroll(int(-1*(event.delta/120)), "units")
    
    ov_text.bind("<MouseWheel>", _on_text_mousewheel)

def update_status(message):
    status_bar.config(text=message)

# ----- Event handlers -----
def start_search(event=None):
    q = entry.get().strip()
    if not q:
        messagebox.showwarning("Input Needed", "Please enter a movie name")
        entry.focus_set()
        return
    set_busy(True)
    update_status("Searching...")
    # start background thread
    t = threading.Thread(target=fetch_and_show, args=(q,), daemon=True)
    t.start()

def on_select(event):
    sel = listbox.curselection()
    if not sel:
        return
    idx = sel[0]
    items = getattr(listbox, "items", [])
    if idx < 0 or idx >= len(items):
        return
    show_card(items[idx])

def clear_search():
    entry.delete(0, tk.END)
    entry.focus_set()
    clear_list_and_card()

def on_enter(event):
    search_btn.config(bg=ACCENT_HOVER)

def on_leave(event):
    search_btn.config(bg=ACCENT)

def on_clear_enter(event):
    clear_btn.config(bg="#5a189a")

def on_clear_leave(event):
    clear_btn.config(bg=SECONDARY)

# ----- UI -----
root = tk.Tk()
root.title("Movie Recommendation Finder")
root.geometry("1000x650")
root.configure(bg=BG)
root.minsize(900, 600)

# Apply a modern theme
style = ttk.Style()
style.theme_use('clam')

# Configure styles
style.configure("TFrame", background=BG)
style.configure("TLabel", background=BG, foreground=TEXT_PRIMARY)
style.configure("TButton", font=("Helvetica", 10))

# Header
header = tk.Frame(root, bg=ACCENT, height=80)
header.pack(fill="x", padx=0, pady=0)
header.pack_propagate(False)

header_content = tk.Frame(header, bg=ACCENT)
header_content.pack(fill="both", padx=20, pady=15)

tk.Label(header_content, text="🎬 Movie Recommendation Finder", bg=ACCENT, fg="white", 
        font=("Helvetica", 20, "bold")).pack(side="left")

# Search section
search_section = tk.Frame(root, bg=BG)
search_section.pack(fill="x", padx=20, pady=15)

search_container = tk.Frame(search_section, bg=BG)
search_container.pack(fill="x")

tk.Label(search_container, text="Find similar movies:", bg=BG, fg=TEXT_PRIMARY, 
        font=("Helvetica", 12, "bold")).pack(anchor="w", pady=(0, 8))

search_frame = tk.Frame(search_container, bg=BG)
search_frame.pack(fill="x")

# Search entry with a modern look
entry = tk.Entry(search_frame, font=("Helvetica", 12), bg="white", fg=TEXT_PRIMARY, 
                relief="solid", bd=1, highlightcolor=ACCENT, highlightthickness=1)
entry.pack(side="left", fill="x", expand=True, ipady=8)
entry.bind("<Return>", start_search)
entry.focus_set()

# Clear button
clear_btn = tk.Button(search_frame, text="✕", command=clear_search, bg=SECONDARY, fg="white", 
                     relief="flat", font=("Helvetica", 10), width=3, cursor="hand2")
clear_btn.pack(side="right", padx=(5, 0), ipady=4)
clear_btn.bind("<Enter>", on_clear_enter)
clear_btn.bind("<Leave>", on_clear_leave)

# Search button
search_btn = tk.Button(search_frame, text="Get Recommendations", command=start_search, 
                      bg=ACCENT, fg="white", relief="flat", font=("Helvetica", 11, "bold"), 
                      padx=20, cursor="hand2")
search_btn.pack(side="right", padx=(10, 0), ipady=8)
search_btn.bind("<Enter>", on_enter)
search_btn.bind("<Leave>", on_leave)

# Progress bar
progress_bar = ttk.Progressbar(search_container, mode='indeterminate', length=100)
progress_bar.pack(fill="x", pady=(10, 0))

# Main content area
content = tk.Frame(root, bg=BG)
content.pack(fill="both", expand=True, padx=20, pady=(0, 10))

# Left: listbox with label
left = tk.Frame(content, bg=BG)
left.pack(side="left", fill="both", padx=(0, 15))

tk.Label(left, text="Recommendations", bg=BG, fg=TEXT_PRIMARY, 
        font=("Helvetica", 12, "bold")).pack(anchor="w", pady=(0, 5))

list_container = tk.Frame(left, bg=BG)
list_container.pack(fill="both", expand=True)

# Make listbox wider
listbox = tk.Listbox(list_container, font=("Helvetica", 11), bg="white", fg=TEXT_PRIMARY, 
                    selectbackground=ACCENT, selectforeground="white", relief="solid", bd=1,
                    highlightcolor=ACCENT, highlightthickness=1, width=45)
listbox.pack(side="left", fill="both", expand=True)
listbox.bind("<<ListboxSelect>>", on_select)

list_scroll = ttk.Scrollbar(list_container, orient="vertical", command=listbox.yview)
list_scroll.pack(side="left", fill="y")
listbox.config(yscrollcommand=list_scroll.set)

# Bind mouse wheel to listbox
def on_listbox_mousewheel(event):
    listbox.yview_scroll(int(-1*(event.delta/120)), "units")

listbox.bind("<MouseWheel>", on_listbox_mousewheel)

# Right: card frame with label
right = tk.Frame(content, bg=BG)
right.pack(side="left", fill="both", expand=True)

tk.Label(right, text="Movie Details", bg=BG, fg=TEXT_PRIMARY, 
        font=("Helvetica", 12, "bold")).pack(anchor="w", pady=(0, 5))

# Make card frame wider
card_frame = tk.Frame(right, bg=BG, relief="flat", width=450)
card_frame.pack(fill="both", expand=True)
card_frame.pack_propagate(False)

# Status bar
status_bar = tk.Label(root, text="Enter a movie name to get recommendations", 
                     bg=BORDER, fg=TEXT_SECONDARY, font=("Helvetica", 9), anchor="w", padx=10)
status_bar.pack(side="bottom", fill="x", pady=0)

# Footer - Fixed footer text
footer = tk.Label(root, text="Data provided by TMDb • Made with ❤️ By Puspraj", bg=BG, fg=TEXT_SECONDARY, 
                font=("Helvetica", 9))
footer.pack(side="bottom", fill="x", pady=5)

# Initial state
clear_list_and_card()

root.mainloop()