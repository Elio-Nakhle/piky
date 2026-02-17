import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import pikepdf
from PIL import Image
import os


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
        tk.Entry(root, textvariable=self.output_file).pack(fill="x")

    def add_pdfs(self):
        files = filedialog.askopenfilenames(filetypes=[("PDF files", "*.pdf")])
        self.pdf_files.extend(files)
        messagebox.showinfo("PDFs Added", f"Added {len(files)} PDFs.")

    def add_jpegs(self):
        files = filedialog.askopenfilenames(filetypes=[("JPEG files", "*.jpg;*.jpeg")])
        self.jpeg_files.extend(files)
        messagebox.showinfo("JPEGs Added", f"Added {len(files)} JPEGs.")

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
            "Pages", "Page numbers to rotate (comma separated):"
        )
        angle = simpledialog.askinteger("Angle", "Rotation angle (90, 180, 270):")
        output = self.output_file.get() or "rotated.pdf"
        pdf_in = pikepdf.Pdf.open(pdf)
        for num in map(int, page_nums.split(",")):
            pdf_in.pages[num - 1].rotate(angle)
        pdf_in.save(output)
        messagebox.showinfo("Done", f"Saved rotated PDF to {output}")

    def remove_pages(self):
        pdf = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if not pdf:
            return
        page_nums = simpledialog.askstring(
            "Pages", "Page numbers to remove (comma separated):"
        )
        output = self.output_file.get() or "removed.pdf"
        pdf_in = pikepdf.Pdf.open(pdf)
        to_remove = sorted([int(n) - 1 for n in page_nums.split(",")], reverse=True)
        for num in to_remove:
            del pdf_in.pages[num]
        pdf_in.save(output)
        messagebox.showinfo("Done", f"Saved PDF with pages removed to {output}")

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


if __name__ == "__main__":
    root = tk.Tk()
    app = PDFToolUI(root)
    root.mainloop()
