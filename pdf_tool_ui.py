import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import pikepdf
from PIL import Image
import os
from pdf2image import convert_from_path


class PDFToolUI:
    def __init__(self, root):
        self.root = root
        self.root.title("PDF Tools")
        self.pdf_files = []
        self.jpeg_files = []
        self.output_file = tk.StringVar()

        tk.Button(root, text="Add PDFs", command=self.add_pdfs).pack(fill="x")
        tk.Button(root, text="Add JPEGs", command=self.add_jpegs).pack(fill="x")
        tk.Button(root, text="Concatenate PDFs", command=self.concat_pdfs).pack(
            fill="x"
        )
        tk.Button(root, text="Rotate Pages", command=self.rotate_pages).pack(fill="x")
        tk.Button(root, text="Remove Pages", command=self.remove_pages).pack(fill="x")
        tk.Button(
            root, text="Add JPEGs as Pages", command=self.add_jpegs_as_pages
        ).pack(fill="x")
        tk.Label(root, text="Output file name:").pack(fill="x")
        tk.Entry(root, textvariable=self.output_file).pack(fill="x")
        self.pdf_listbox = tk.Listbox(root, selectmode=tk.SINGLE)
        self.pdf_listbox.pack(fill="x")
        tk.Button(root, text="Move Up", command=self.move_pdf_up).pack(fill="x")
        tk.Button(root, text="Move Down", command=self.move_pdf_down).pack(fill="x")
        self.preview_label = tk.Label(root)
        self.preview_label.pack(fill="both", expand=True)
        tk.Button(root, text="Preview Selected PDF", command=self.preview_pdf).pack(
            fill="x"
        )

    def add_pdfs(self):
        files = filedialog.askopenfilenames(filetypes=[("PDF files", "*.pdf")])
        self.pdf_files.extend(files)
        for f in files:
            self.pdf_listbox.insert(tk.END, f)
        messagebox.showinfo("PDFs Added", f"Added {len(files)} PDFs.")

    def move_pdf_up(self):
        sel = self.pdf_listbox.curselection()
        if not sel or sel[0] == 0:
            return
        idx = sel[0]
        self.pdf_files[idx - 1], self.pdf_files[idx] = (
            self.pdf_files[idx],
            self.pdf_files[idx - 1],
        )
        txt = self.pdf_listbox.get(idx)
        self.pdf_listbox.delete(idx)
        self.pdf_listbox.insert(idx - 1, txt)
        self.pdf_listbox.select_set(idx - 1)

    def move_pdf_down(self):
        sel = self.pdf_listbox.curselection()
        if not sel or sel[0] == self.pdf_listbox.size() - 1:
            return
        idx = sel[0]
        self.pdf_files[idx + 1], self.pdf_files[idx] = (
            self.pdf_files[idx],
            self.pdf_files[idx + 1],
        )
        txt = self.pdf_listbox.get(idx)
        self.pdf_listbox.delete(idx)
        self.pdf_listbox.insert(idx + 1, txt)
        self.pdf_listbox.select_set(idx + 1)

    def concat_pdfs(self):
        if not self.pdf_files:
            messagebox.showerror("Error", "No PDFs selected.")
            return
        output = self.output_file.get() or "output.pdf"
        pdf_out = pikepdf.Pdf.new()
        for pdf in self.pdf_files:
            src = pikepdf.Pdf.open(pdf)
            pdf_out.pages.extend(src.pages)
        pdf_out.save(output)
        messagebox.showinfo("Done", f"Saved concatenated PDF to {output}")

    def rotate_pages(self):
        pdf = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if not pdf:
            return
        page_nums = simpledialog.askstring(
            "Pages", "Page numbers/ranges to rotate (e.g. 1-3,5,7):"
        )
        angle = simpledialog.askinteger("Angle", "Rotation angle (90, 180, 270):")
        output = self.output_file.get() or "rotated.pdf"
        pdf_in = pikepdf.Pdf.open(pdf)
        pages_to_rotate = self._parse_page_ranges(page_nums)
        for num in pages_to_rotate:
            pdf_in.pages[num - 1].rotate(angle)
        pdf_in.save(output)
        messagebox.showinfo("Done", f"Saved rotated PDF to {output}")

    def remove_pages(self):
        pdf = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if not pdf:
            return
        page_nums = simpledialog.askstring(
            "Pages", "Page numbers/ranges to remove (e.g. 1-3,5,7):"
        )
        output = self.output_file.get() or "removed.pdf"
        pdf_in = pikepdf.Pdf.open(pdf)
        to_remove = sorted(
            [n - 1 for n in self._parse_page_ranges(page_nums)], reverse=True
        )
        for num in to_remove:
            del pdf_in.pages[num]
        pdf_in.save(output)
        messagebox.showinfo("Done", f"Saved PDF with pages removed to {output}")

    def _parse_page_ranges(self, page_str):
        """Parse a string like '1-3,5,7-9' into a list of ints."""
        pages = set()
        if not page_str:
            return []
        for part in page_str.split(","):
            part = part.strip()
            if "-" in part:
                start, end = part.split("-")
                pages.update(range(int(start), int(end) + 1))
            elif part.isdigit():
                pages.add(int(part))
        return sorted(pages)

    def add_jpegs(self):
        files = filedialog.askopenfilenames(filetypes=[("JPEG files", "*.jpg;*.jpeg")])
        self.jpeg_files.extend(files)
        messagebox.showinfo("JPEGs Added", f"Added {len(files)} JPEGs.")

    def add_jpegs_as_pages(self):
        pdf = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if not pdf:
            return
        output = self.output_file.get() or "jpeg_added.pdf"
        pdf_in = pikepdf.Pdf.open(pdf)
        for jpeg in self.jpeg_files:
            img = Image.open(jpeg)
            img_pdf_path = jpeg + ".pdf"
            img.save(img_pdf_path, "PDF")
            img_pdf = pikepdf.Pdf.open(img_pdf_path)
            pdf_in.pages.extend(img_pdf.pages)
            os.remove(img_pdf_path)
        pdf_in.save(output)
        messagebox.showinfo("Done", f"Saved PDF with JPEGs added to {output}")

    def preview_pdf(self):
        sel = self.pdf_listbox.curselection()
        if not sel:
            messagebox.showinfo(
                "No selection", "Select a PDF from the list to preview."
            )
            return
        pdf_path = self.pdf_files[sel[0]]
        try:
            images = convert_from_path(
                pdf_path, first_page=1, last_page=1, size=(400, 500)
            )
            img = images[0]
            img.thumbnail((400, 500))
            # Convert PIL image to Tkinter PhotoImage
            import io
            from PIL import ImageTk

            bio = io.BytesIO()
            img.save(bio, format="PNG")
            bio.seek(0)
            tk_img = ImageTk.PhotoImage(Image.open(bio))
            self.preview_label.config(image=tk_img)
            self.preview_label.image = tk_img  # Prevent garbage collection
        except Exception as e:
            messagebox.showerror("Preview Error", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    app = PDFToolUI(root)
    root.mainloop()
