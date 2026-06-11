"""Adobe-style Fill & Sign editor for PDFs."""

from __future__ import annotations

import io
import os
from datetime import date
from tkinter import filedialog, messagebox, simpledialog, ttk

import pikepdf
import tkinter as tk
from pdf2image import convert_from_path
from PIL import Image, ImageDraw, ImageFont, ImageTk
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as rl_canvas

RENDER_DPI = 150
DEFAULT_TEXT_SIZE = 14
DEFAULT_SIG_WIDTH_PT = 150
DEFAULT_SIG_HEIGHT_PT = 50
MARK_SIZE_PT = 14

SCRIPT_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Brush Script.ttf",
    "/System/Library/Fonts/Supplemental/SnellRoundhand.ttc",
    "/Library/Fonts/Bradley Hand Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
    "C:/Windows/Fonts/segoesc.ttf",
    "C:/Windows/Fonts/BRUSHSCI.TTF",
]


def _find_script_font(size: int = 48) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in SCRIPT_FONT_CANDIDATES:
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _text_to_image(text: str, font_size: int = 48) -> Image.Image:
    font = _find_script_font(font_size)
    bbox = font.getbbox(text)
    w = max(bbox[2] - bbox[0] + 8, 1)
    h = max(bbox[3] - bbox[1] + 8, 1)
    img = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    draw.text((4 - bbox[0], 4 - bbox[1]), text, fill=(0, 0, 0, 255), font=font)
    return img


def _remove_white_background(img: Image.Image, threshold: int = 240) -> Image.Image:
    img = img.convert("RGBA")
    pixels = img.load()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = pixels[x, y]
            if r >= threshold and g >= threshold and b >= threshold:
                pixels[x, y] = (r, g, b, 0)
    return img


class SignatureDialog(tk.Toplevel):
    """Dialog to create a signature via type, draw, or upload."""

    def __init__(self, parent: tk.Misc, on_done):
        super().__init__(parent)
        self.title("Create Signature")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.on_done = on_done
        self.result: Image.Image | None = None

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        type_frame = ttk.Frame(notebook)
        draw_frame = ttk.Frame(notebook)
        upload_frame = ttk.Frame(notebook)
        notebook.add(type_frame, text="Type")
        notebook.add(draw_frame, text="Draw")
        notebook.add(upload_frame, text="Upload")

        self._build_type_tab(type_frame)
        self._build_draw_tab(draw_frame)
        self._build_upload_tab(upload_frame)

        btn_row = ttk.Frame(self)
        btn_row.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(btn_row, text="Cancel", command=self.destroy).pack(side="right", padx=4)
        ttk.Button(btn_row, text="Use Signature", command=self._accept).pack(side="right")

    def _build_type_tab(self, frame: ttk.Frame) -> None:
        ttk.Label(frame, text="Type your name:").pack(anchor="w", padx=8, pady=(8, 4))
        self.type_var = tk.StringVar()
        entry = ttk.Entry(frame, textvariable=self.type_var, width=40)
        entry.pack(padx=8, pady=4)
        entry.focus_set()
        self.type_preview = tk.Label(frame, bg="white", width=40, height=3, relief="sunken")
        self.type_preview.pack(padx=8, pady=8)
        self.type_var.trace_add("write", lambda *_: self._update_type_preview())

    def _update_type_preview(self) -> None:
        text = self.type_var.get().strip()
        if not text:
            self.type_preview.config(image="", text="")
            return
        img = _text_to_image(text, font_size=36)
        tk_img = ImageTk.PhotoImage(img)
        self.type_preview.config(image=tk_img, text="")
        self.type_preview.image = tk_img

    def _build_draw_tab(self, frame: ttk.Frame) -> None:
        ttk.Label(frame, text="Draw your signature:").pack(anchor="w", padx=8, pady=(8, 4))
        self.draw_canvas = tk.Canvas(frame, width=400, height=150, bg="white", cursor="crosshair")
        self.draw_canvas.pack(padx=8, pady=4)
        self._draw_strokes: list[list[tuple[int, int]]] = []
        self._current_stroke: list[tuple[int, int]] = []
        self.draw_canvas.bind("<Button-1>", self._draw_start)
        self.draw_canvas.bind("<B1-Motion>", self._draw_move)
        self.draw_canvas.bind("<ButtonRelease-1>", self._draw_end)
        ttk.Button(frame, text="Clear", command=self._draw_clear).pack(anchor="w", padx=8, pady=4)

    def _draw_start(self, event: tk.Event) -> None:
        self._current_stroke = [(event.x, event.y)]
        self._draw_strokes.append(self._current_stroke)

    def _draw_move(self, event: tk.Event) -> None:
        if not self._current_stroke:
            return
        x0, y0 = self._current_stroke[-1]
        self.draw_canvas.create_line(x0, y0, event.x, event.y, fill="black", width=2)
        self._current_stroke.append((event.x, event.y))

    def _draw_end(self, _event: tk.Event) -> None:
        self._current_stroke = []

    def _draw_clear(self) -> None:
        self.draw_canvas.delete("all")
        self._draw_strokes.clear()

    def _strokes_to_image(self) -> Image.Image | None:
        if not self._draw_strokes:
            return None
        img = Image.new("RGBA", (400, 150), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)
        for stroke in self._draw_strokes:
            if len(stroke) < 2:
                continue
            draw.line(stroke, fill=(0, 0, 0, 255), width=2)
        bbox = img.getbbox()
        if not bbox:
            return None
        return img.crop(bbox)

    def _build_upload_tab(self, frame: ttk.Frame) -> None:
        ttk.Label(frame, text="Upload a signature image (PNG/JPG):").pack(
            anchor="w", padx=8, pady=(8, 4)
        )
        self.upload_preview = tk.Label(frame, bg="white", width=40, height=6, relief="sunken")
        self.upload_preview.pack(padx=8, pady=4)
        self.upload_image: Image.Image | None = None
        self.remove_white_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            frame,
            text="Remove white background",
            variable=self.remove_white_var,
            command=self._refresh_upload_preview,
        ).pack(anchor="w", padx=8)
        ttk.Button(frame, text="Choose File...", command=self._choose_upload).pack(
            anchor="w", padx=8, pady=4
        )

    def _choose_upload(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.gif;*.bmp"), ("All files", "*.*")]
        )
        if not path:
            return
        self.upload_image = Image.open(path)
        self._refresh_upload_preview()

    def _refresh_upload_preview(self) -> None:
        if self.upload_image is None:
            return
        img = self.upload_image.copy()
        if self.remove_white_var.get():
            img = _remove_white_background(img)
        preview = img.copy()
        preview.thumbnail((320, 120))
        tk_img = ImageTk.PhotoImage(preview)
        self.upload_preview.config(image=tk_img, text="")
        self.upload_preview.image = tk_img

    def _accept(self) -> None:
        notebook = self.winfo_children()[0]
        tab = notebook.index(notebook.select())
        if tab == 0:
            text = self.type_var.get().strip()
            if not text:
                messagebox.showwarning("Signature", "Please type your name.", parent=self)
                return
            self.result = _text_to_image(text)
        elif tab == 1:
            self.result = self._strokes_to_image()
            if self.result is None:
                messagebox.showwarning("Signature", "Please draw a signature.", parent=self)
                return
        else:
            if self.upload_image is None:
                messagebox.showwarning("Signature", "Please choose an image.", parent=self)
                return
            self.result = self.upload_image.copy()
            if self.remove_white_var.get():
                self.result = _remove_white_background(self.result)
        self.on_done(self.result)
        self.destroy()


class FormFillerWindow(tk.Toplevel):
    """Interactive Fill & Sign editor."""

    TOOLS = ("select", "text", "check", "x", "date", "signature")

    def __init__(self, parent: tk.Misc, pdf_path: str | None = None):
        super().__init__(parent)
        self.title("Fill & Sign")
        self.geometry("900x700")
        self.minsize(640, 480)

        self.pdf_path = pdf_path
        self.pdf: pikepdf.Pdf | None = None
        self.page_count = 0
        self.current_page = 0
        self.zoom = 1.0
        self.tool = "select"
        self.items: list[dict] = []
        self._next_id = 1
        self.selected_id: int | None = None
        self.page_image: Image.Image | None = None
        self.tk_page_image: ImageTk.PhotoImage | None = None
        self._drag_item_id: int | None = None
        self._pending_signature: Image.Image | None = None

        self._build_ui()
        self.bind("<Delete>", self._on_delete_key)
        self.bind("<BackSpace>", self._on_delete_key)
        self.canvas.bind("<Delete>", self._on_delete_key)
        self.canvas.bind("<BackSpace>", self._on_delete_key)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        if pdf_path:
            self._load_pdf(pdf_path)
        else:
            self._open_pdf()

    def _build_ui(self) -> None:
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", padx=4, pady=4)

        ttk.Button(toolbar, text="Open PDF...", command=self._open_pdf).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Save PDF...", command=self._save_pdf).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Delete Selected", command=self._delete_selected).pack(
            side="left", padx=2
        )

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=6)

        self.tool_var = tk.StringVar(value="select")
        for label, value in (
            ("Select", "select"),
            ("Text", "text"),
            ("Check", "check"),
            ("X", "x"),
            ("Date", "date"),
            ("Signature", "signature"),
        ):
            ttk.Radiobutton(
                toolbar,
                text=label,
                value=value,
                variable=self.tool_var,
                command=self._on_tool_change,
            ).pack(side="left", padx=2)

        nav = ttk.Frame(self)
        nav.pack(fill="x", padx=4, pady=2)
        ttk.Button(nav, text="Prev", command=self._prev_page).pack(side="left", padx=2)
        self.page_label = ttk.Label(nav, text="Page 0 / 0")
        self.page_label.pack(side="left", padx=8)
        ttk.Button(nav, text="Next", command=self._next_page).pack(side="left", padx=2)
        ttk.Button(nav, text="Zoom -", command=lambda: self._set_zoom(self.zoom * 0.8)).pack(
            side="left", padx=(16, 2)
        )
        ttk.Button(nav, text="Zoom +", command=lambda: self._set_zoom(self.zoom * 1.25)).pack(
            side="left", padx=2
        )
        self.zoom_label = ttk.Label(nav, text="100%")
        self.zoom_label.pack(side="left", padx=8)

        canvas_frame = ttk.Frame(self)
        canvas_frame.pack(fill="both", expand=True, padx=4, pady=4)
        self.canvas = tk.Canvas(canvas_frame, bg="#808080", highlightthickness=0)
        vscroll = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        hscroll = ttk.Scrollbar(canvas_frame, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vscroll.set, xscrollcommand=hscroll.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vscroll.grid(row=0, column=1, sticky="ns")
        hscroll.grid(row=1, column=0, sticky="ew")
        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)

        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.canvas.bind("<Double-Button-1>", self._on_canvas_double_click)

        self.status_var = tk.StringVar(value="Open a PDF to begin.")
        ttk.Label(self, textvariable=self.status_var, relief="sunken").pack(
            fill="x", padx=4, pady=(0, 4)
        )

    def _on_close(self) -> None:
        self.destroy()

    def _switch_to_select(self) -> None:
        self.tool_var.set("select")
        self.tool = "select"
        self._pending_signature = None
        self.status_var.set(
            "Select: click an item to select, drag to move, Delete or button to remove."
        )

    def _on_tool_change(self) -> None:
        self.tool = self.tool_var.get()
        if self.tool != "signature":
            self._pending_signature = None
        if self.tool == "signature":
            self.status_var.set("Create a signature, then click on the page to place it.")
            SignatureDialog(self, self._on_signature_created)
        elif self.tool == "select":
            self.status_var.set(
                "Select: click an item to select, drag to move, Delete or button to remove."
            )
        else:
            self.status_var.set(f"Tool: {self.tool}. Click on the page to place.")

    def _on_signature_created(self, img: Image.Image) -> None:
        self._pending_signature = img
        self.status_var.set("Click on the page to place your signature.")

    def _open_pdf(self) -> None:
        path = filedialog.askopenfilename(
            parent=self, filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if path:
            self._load_pdf(path)

    def _load_pdf(self, path: str) -> None:
        try:
            if self.pdf is not None:
                self.pdf.close()
            self.pdf = pikepdf.Pdf.open(path)
            self.pdf_path = path
            self.page_count = len(self.pdf.pages)
            self.current_page = 0
            self.items.clear()
            self.selected_id = None
            self.title(f"Fill & Sign - {os.path.basename(path)}")
            self._render_current_page()
            self.status_var.set(f"Loaded {self.page_count} page(s).")
        except Exception as exc:
            messagebox.showerror("Open PDF Error", str(exc), parent=self)

    def _page_geometry(self, page_index: int) -> tuple[float, float, int]:
        page = self.pdf.pages[page_index]
        box = page.mediabox
        w_pt = float(box[2] - box[0])
        h_pt = float(box[3] - box[1])
        rotate = int(page.get("/Rotate", 0)) % 360
        return w_pt, h_pt, rotate

    def _render_current_page(self) -> None:
        if self.pdf is None or self.page_count == 0:
            return
        page_num = self.current_page + 1
        images = convert_from_path(
            self.pdf_path,
            dpi=RENDER_DPI,
            first_page=page_num,
            last_page=page_num,
        )
        self.page_image = images[0]
        self._redraw_canvas()
        self.page_label.config(text=f"Page {page_num} / {self.page_count}")

    def _set_zoom(self, zoom: float) -> None:
        self.zoom = max(0.25, min(zoom, 4.0))
        self.zoom_label.config(text=f"{int(self.zoom * 100)}%")
        self._redraw_canvas()

    def _prev_page(self) -> None:
        if self.current_page > 0:
            self.current_page -= 1
            self.selected_id = None
            self._render_current_page()

    def _next_page(self) -> None:
        if self.current_page < self.page_count - 1:
            self.current_page += 1
            self.selected_id = None
            self._render_current_page()

    def _canvas_to_pdf(self, canvas_x: float, canvas_y: float) -> tuple[float, float]:
        if self.page_image is None:
            return 0.0, 0.0
        img_x = canvas_x / self.zoom
        img_y = canvas_y / self.zoom
        img_w = self.page_image.width
        img_h = self.page_image.height
        w_pt, h_pt, rotate = self._page_geometry(self.current_page)
        nx = img_x / img_w
        ny = img_y / img_h
        if rotate == 0:
            x_pt = nx * w_pt
            y_pt = h_pt - ny * h_pt
        elif rotate == 90:
            x_pt = ny * w_pt
            y_pt = nx * h_pt
        elif rotate == 180:
            x_pt = w_pt - nx * w_pt
            y_pt = ny * h_pt
        elif rotate == 270:
            x_pt = w_pt - ny * w_pt
            y_pt = h_pt - nx * h_pt
        else:
            x_pt = nx * w_pt
            y_pt = h_pt - ny * h_pt
        return x_pt, y_pt

    def _pdf_to_canvas(self, x_pt: float, y_pt: float) -> tuple[float, float]:
        if self.page_image is None:
            return 0.0, 0.0
        img_w = self.page_image.width
        img_h = self.page_image.height
        w_pt, h_pt, rotate = self._page_geometry(self.current_page)
        if rotate == 0:
            nx = x_pt / w_pt
            ny = (h_pt - y_pt) / h_pt
        elif rotate == 90:
            nx = y_pt / h_pt
            ny = x_pt / w_pt
        elif rotate == 180:
            nx = (w_pt - x_pt) / w_pt
            ny = y_pt / h_pt
        elif rotate == 270:
            nx = (h_pt - y_pt) / h_pt
            ny = (w_pt - x_pt) / w_pt
        else:
            nx = x_pt / w_pt
            ny = (h_pt - y_pt) / h_pt
        img_x = nx * img_w
        img_y = ny * img_h
        return img_x * self.zoom, img_y * self.zoom

    def _redraw_canvas(self) -> None:
        self.canvas.delete("all")
        if self.page_image is None:
            return
        scaled_w = int(self.page_image.width * self.zoom)
        scaled_h = int(self.page_image.height * self.zoom)
        display = self.page_image.copy()
        if self.zoom != 1.0:
            display = display.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)
        self.tk_page_image = ImageTk.PhotoImage(display)
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_page_image, tags=("page",))
        self.canvas.config(scrollregion=(0, 0, scaled_w, scaled_h))
        for item in self.items:
            if item["page"] == self.current_page:
                self._draw_item_on_canvas(item)

    def _draw_item_on_canvas(self, item: dict) -> None:
        cx, cy = self._pdf_to_canvas(item["x_pt"], item["y_pt"])
        item["canvas_ids"] = []
        selected = item["id"] == self.selected_id
        outline = "#0066cc" if selected else None

        if item["type"] in ("text", "check", "x", "date"):
            canvas_y = cy
            cid = self.canvas.create_text(
                cx,
                canvas_y,
                text=item["text"],
                anchor="sw",
                fill="black",
                font=("Helvetica", int(item["size"] * self.zoom * RENDER_DPI / 72)),
                tags=("item", f"item_{item['id']}"),
            )
            item["canvas_ids"].append(cid)
            if outline:
                bbox = self.canvas.bbox(cid)
                if bbox:
                    rect = self.canvas.create_rectangle(
                        *bbox, outline=outline, width=1, tags=("item", f"item_{item['id']}")
                    )
                    item["canvas_ids"].insert(0, rect)
            bbox = self.canvas.bbox(cid)
            if bbox:
                item["_canvas_bbox"] = bbox
        elif item["type"] == "signature" and item.get("pil_image"):
            w_canvas = item["w_pt"] * self.zoom * RENDER_DPI / 72
            h_canvas = item["h_pt"] * self.zoom * RENDER_DPI / 72
            img = item["pil_image"].copy()
            img = img.resize(
                (max(1, int(w_canvas)), max(1, int(h_canvas))),
                Image.Resampling.LANCZOS,
            )
            tk_img = ImageTk.PhotoImage(img)
            item["_tk_image"] = tk_img
            cid = self.canvas.create_image(
                cx,
                cy,
                anchor="sw",
                image=tk_img,
                tags=("item", f"item_{item['id']}"),
            )
            item["canvas_ids"].append(cid)
            if outline:
                rect = self.canvas.create_rectangle(
                    cx,
                    cy - h_canvas,
                    cx + w_canvas,
                    cy,
                    outline=outline,
                    width=1,
                    tags=("item", f"item_{item['id']}"),
                )
                item["canvas_ids"].insert(0, rect)
            item["_canvas_bbox"] = (cx, cy - h_canvas, cx + w_canvas, cy)

    def _item_at_canvas(self, canvas_x: float, canvas_y: float) -> dict | None:
        padding = 6
        for item in reversed(self.items):
            if item["page"] != self.current_page:
                continue
            bbox = item.get("_canvas_bbox")
            if bbox is None:
                continue
            x1, y1, x2, y2 = bbox
            if (
                x1 - padding <= canvas_x <= x2 + padding
                and y1 - padding <= canvas_y <= y2 + padding
            ):
                return item
        return None

    def _on_canvas_click(self, event: tk.Event) -> None:
        self.canvas.focus_set()
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        hit = self._item_at_canvas(cx, cy)

        if self.tool != "select" and hit is not None:
            self.selected_id = hit["id"]
            self._drag_item_id = hit["id"]
            self._switch_to_select()
            self._redraw_canvas()
            return

        if self.tool == "select":
            self.selected_id = hit["id"] if hit else None
            if hit:
                self._drag_item_id = hit["id"]
            else:
                self._drag_item_id = None
            self._redraw_canvas()
            return

        if self.tool == "text":
            text = simpledialog.askstring("Text", "Enter text:", parent=self)
            if not text:
                return
            x_pt, y_pt = self._canvas_to_pdf(cx, cy)
            self._add_item(
                {
                    "type": "text",
                    "page": self.current_page,
                    "x_pt": x_pt,
                    "y_pt": y_pt,
                    "text": text,
                    "font": "Helvetica",
                    "size": DEFAULT_TEXT_SIZE,
                }
            )
        elif self.tool == "check":
            x_pt, y_pt = self._canvas_to_pdf(cx, cy)
            self._add_item(
                {
                    "type": "check",
                    "page": self.current_page,
                    "x_pt": x_pt,
                    "y_pt": y_pt,
                    "text": "\u2713",
                    "font": "Helvetica-Bold",
                    "size": MARK_SIZE_PT,
                }
            )
        elif self.tool == "x":
            x_pt, y_pt = self._canvas_to_pdf(cx, cy)
            self._add_item(
                {
                    "type": "x",
                    "page": self.current_page,
                    "x_pt": x_pt,
                    "y_pt": y_pt,
                    "text": "X",
                    "font": "Helvetica-Bold",
                    "size": MARK_SIZE_PT,
                }
            )
        elif self.tool == "date":
            x_pt, y_pt = self._canvas_to_pdf(cx, cy)
            today = date.today().strftime("%m/%d/%Y")
            self._add_item(
                {
                    "type": "date",
                    "page": self.current_page,
                    "x_pt": x_pt,
                    "y_pt": y_pt,
                    "text": today,
                    "font": "Helvetica",
                    "size": DEFAULT_TEXT_SIZE,
                }
            )
        elif self.tool == "signature" and self._pending_signature is not None:
            x_pt, y_pt = self._canvas_to_pdf(cx, cy)
            sig = self._pending_signature
            aspect = sig.width / max(sig.height, 1)
            h_pt = DEFAULT_SIG_HEIGHT_PT
            w_pt = h_pt * aspect
            self._add_item(
                {
                    "type": "signature",
                    "page": self.current_page,
                    "x_pt": x_pt,
                    "y_pt": y_pt,
                    "w_pt": w_pt,
                    "h_pt": h_pt,
                    "pil_image": sig.copy(),
                }
            )
            self._pending_signature = None
            self._switch_to_select()

    def _add_item(self, item: dict) -> None:
        item["id"] = self._next_id
        item["canvas_ids"] = []
        self._next_id += 1
        self.items.append(item)
        self.selected_id = item["id"]
        self._redraw_canvas()
        self._switch_to_select()

    def _on_canvas_drag(self, event: tk.Event) -> None:
        if self.tool != "select" or self._drag_item_id is None:
            return
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        item = next((it for it in self.items if it["id"] == self._drag_item_id), None)
        if item is None:
            return
        x_pt, y_pt = self._canvas_to_pdf(cx, cy)
        item["x_pt"] = x_pt
        item["y_pt"] = y_pt
        self._redraw_canvas()

    def _on_canvas_release(self, _event: tk.Event) -> None:
        self._drag_item_id = None

    def _on_canvas_double_click(self, event: tk.Event) -> None:
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        hit = self._item_at_canvas(cx, cy)
        if hit is None:
            return
        if hit["type"] in ("text", "date"):
            new_text = simpledialog.askstring(
                "Edit Text", "Update text:", initialvalue=hit["text"], parent=self
            )
            if new_text is not None:
                hit["text"] = new_text
                self._redraw_canvas()

    def _delete_selected(self) -> None:
        if self.selected_id is None:
            self.status_var.set("Nothing selected to delete.")
            return
        self.items = [it for it in self.items if it["id"] != self.selected_id]
        self.selected_id = None
        self._drag_item_id = None
        self._redraw_canvas()
        self.status_var.set("Item deleted.")

    def _on_delete_key(self, event: tk.Event) -> None:
        self._delete_selected()
        return "break"

    def _build_overlay_pdf(self, page_index: int) -> bytes:
        w_pt, h_pt, _rotate = self._page_geometry(page_index)
        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=(w_pt, h_pt))
        page_items = [it for it in self.items if it["page"] == page_index]
        for item in page_items:
            if item["type"] in ("text", "check", "x", "date"):
                font = item.get("font", "Helvetica")
                size = item.get("size", DEFAULT_TEXT_SIZE)
                c.setFont(font, size)
                c.drawString(item["x_pt"], item["y_pt"], item["text"])
            elif item["type"] == "signature" and item.get("pil_image"):
                c.drawImage(
                    ImageReader(item["pil_image"]),
                    item["x_pt"],
                    item["y_pt"],
                    item["w_pt"],
                    item["h_pt"],
                    mask="auto",
                )
        c.showPage()
        c.save()
        buf.seek(0)
        return buf.read()

    def _save_pdf(self) -> None:
        if self.pdf is None or self.pdf_path is None:
            messagebox.showwarning("Save", "No PDF loaded.", parent=self)
            return
        if not self.items:
            messagebox.showwarning("Save", "Nothing to save. Add text or a signature first.", parent=self)
            return
        default_name = os.path.splitext(os.path.basename(self.pdf_path))[0] + "_filled.pdf"
        output_path = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".pdf",
            initialfile=default_name,
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
        )
        if not output_path:
            return
        try:
            src = pikepdf.Pdf.open(self.pdf_path)
            for page_index in range(len(src.pages)):
                page_items = [it for it in self.items if it["page"] == page_index]
                if not page_items:
                    continue
                overlay_bytes = self._build_overlay_pdf(page_index)
                overlay_pdf = pikepdf.Pdf.open(io.BytesIO(overlay_bytes))
                src.pages[page_index].add_overlay(overlay_pdf.pages[0])
            src.save(output_path)
            src.close()
            messagebox.showinfo("Saved", f"Saved filled PDF to:\n{output_path}", parent=self)
            self.status_var.set(f"Saved to {output_path}")
        except Exception as exc:
            messagebox.showerror("Save Error", str(exc), parent=self)


def open_form_filler(parent: tk.Misc, pdf_path: str | None = None) -> FormFillerWindow:
    """Open the Fill & Sign editor."""
    return FormFillerWindow(parent, pdf_path=pdf_path)
