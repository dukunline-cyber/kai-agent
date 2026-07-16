"""Split from telegram_agent monolith — behavior preserved."""
from __future__ import annotations

from kai_core.config import *  # noqa: F401,F403


def extract_pdf_text(file_path: str, max_chars: int = 50000) -> str:
    if not PDF_AVAILABLE:
        return "[PDF library not available]"
    try:
        reader = PyPDF2.PdfReader(file_path)
        texts = []
        for i, page in enumerate(reader.pages):
            t = page.extract_text() or ""
            texts.append(f"[Page {i+1}]\n{t}")
            if sum(len(x) for x in texts) > max_chars:
                break
        result = "\n\n".join(texts)
        if len(result) > max_chars:
            result = result[:max_chars] + f"\n\n[...truncated, {len(reader.pages)} pages total]"
        return result or "[PDF has no extractable text]"
    except Exception as e:
        return f"[Error reading PDF: {e}]"

def extract_docx_text(file_path: str, max_chars: int = 50000) -> str:
    if not DOCX_AVAILABLE:
        return "[DOCX library not available]"
    try:
        doc = DocxDocument(file_path)
        texts = []
        for para in doc.paragraphs:
            texts.append(para.text)
        # Also extract from tables
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text for cell in row.cells)
                texts.append(row_text)
        result = "\n".join(texts)
        if len(result) > max_chars:
            result = result[:max_chars] + "\n\n[...truncated]"
        return result or "[DOCX is empty]"
    except Exception as e:
        return f"[Error reading DOCX: {e}]"

def extract_xlsx_text(file_path: str, max_chars: int = 50000) -> str:
    if not XLSX_AVAILABLE:
        return "[XLSX library not available]"
    try:
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        texts = []
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            texts.append(f"[Sheet: {sheet_name}]")
            row_count = 0
            for row in ws.iter_rows(values_only=True):
                cells = [str(c) if c is not None else "" for c in row]
                texts.append(" | ".join(cells))
                row_count += 1
                if sum(len(x) for x in texts) > max_chars:
                    texts.append(f"[...truncated after {row_count} rows]")
                    break
        wb.close()
        result = "\n".join(texts)
        return result or "[XLSX is empty]"
    except Exception as e:
        return f"[Error reading XLSX: {e}]"

def extract_pptx_text(file_path: str, max_chars: int = 50000) -> str:
    if not PPTX_AVAILABLE:
        return "[PPTX library not available]"
    try:
        prs = PptxPresentation(file_path)
        texts = []
        for i, slide in enumerate(prs.slides):
            texts.append(f"[Slide {i+1}]")
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for para in shape.text_frame.paragraphs:
                        texts.append(para.text)
                if hasattr(shape, "table"):
                    for row in shape.table.rows:
                        row_text = " | ".join(cell.text for cell in row.cells)
                        texts.append(row_text)
        result = "\n".join(texts)
        if len(result) > max_chars:
            result = result[:max_chars] + "\n\n[...truncated]"
        return result or "[PPTX is empty]"
    except Exception as e:
        return f"[Error reading PPTX: {e}]"

def extract_file_content(file_path: str, mime_type: str = "", max_chars: int = 50000) -> str:
    """Unified file content extractor supporting PDF, DOCX, XLSX, PPTX, and text files."""
    path = Path(file_path)
    suffix = path.suffix.lower()

    # PDF
    if suffix == ".pdf" or "pdf" in mime_type:
        return extract_pdf_text(file_path, max_chars)

    # DOCX
    if suffix == ".docx" or "wordprocessingml" in mime_type:
        return extract_docx_text(file_path, max_chars)

    # XLSX
    if suffix == ".xlsx" or "spreadsheetml" in mime_type:
        return extract_xlsx_text(file_path, max_chars)

    # PPTX
    if suffix == ".pptx" or "presentationml" in mime_type:
        return extract_pptx_text(file_path, max_chars)

    # DOC (old format) - try antiword or textract
    if suffix == ".doc":
        try:
            result = subprocess.run(["antiword", file_path], capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and result.stdout:
                text = result.stdout
                if len(text) > max_chars:
                    text = text[:max_chars] + "\n\n[...truncated]"
                return text
        except Exception:
            pass
        return "[.doc format - install antiword to read, or convert to .docx]"

    # XLS (old format)
    if suffix == ".xls":
        return "[.xls format - convert to .xlsx for reading]"

    # CSV
    if suffix == ".csv":
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            if len(text) > max_chars:
                text = text[:max_chars] + "\n\n[...truncated]"
            return text
        except Exception as e:
            return f"[Error reading CSV: {e}]"

    # Image files sent as documents
    image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".svg"}
    if suffix in image_extensions or mime_type.startswith("image/"):
        return "__IMAGE__"  # Signal to caller to use vision model

    # Text-based files
    text_extensions = {".txt", ".md", ".py", ".js", ".ts", ".json", ".yaml", ".yml",
                       ".toml", ".cfg", ".ini", ".sh", ".bash", ".csv", ".xml", ".html",
                       ".css", ".sql", ".env", ".log", ".conf", ".rst", ".tex",
                       ".sol", ".rs", ".go", ".java", ".c", ".cpp", ".h", ".hpp",
                       ".rb", ".php", ".swift", ".kt", ".r", ".m", ".pl", ".jsx", ".tsx"}
    text_mimes = {"text/", "application/json", "application/xml", "application/javascript",
                  "application/x-yaml", "application/toml", "application/x-sh"}

    is_text = (suffix in text_extensions or any(mime_type.startswith(tm) for tm in text_mimes))

    if is_text:
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
            if len(raw) > max_chars:
                return raw[:max_chars] + f"\n\n[...truncated, total {len(raw)} chars. Full file saved at {file_path}]"
            return raw
        except Exception:
            return f"[Could not read file as text. Saved at {file_path}]"

    return f"__BINARY__"  # Binary file, not readable as text


# ========================
# TYPING INDICATOR
# ========================

class TypingIndicator:
    """Continuously sends typing action while processing."""
    def __init__(self, bot, chat_id, interval=4):
        self.bot = bot
        self.chat_id = chat_id
        self.interval = interval
        self._task = None
        self._running = False

    async def _loop(self):
        while self._running:
            try:
                await self.bot.send_chat_action(chat_id=self.chat_id, action=ChatAction.TYPING)
            except Exception:
                pass
            await asyncio.sleep(self.interval)

    async def __aenter__(self):
        self._running = True
        self._task = asyncio.create_task(self._loop())
        return self

    async def __aexit__(self, *args):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


# ========================
# IMAGE GENERATION
# ========================

def generate_image_pollinations(prompt: str, width: int = 1024, height: int = 1024) -> str:
    """Generate image using pollinations.ai free API. Returns path to saved image."""
    try:
        encoded_prompt = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&nologo=true"
        save_dir = Path.home() / "ai-agent" / "generated"
        save_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = save_dir / f"img_{timestamp}.jpg"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            with open(save_path, "wb") as f:
                f.write(resp.read())
        if save_path.stat().st_size < 1000:
            return ""
        return str(save_path)
    except Exception as e:
        logging.error(f"Image generation error: {e}")
        return ""

def should_generate_image(text: str) -> bool:
    """Check if user is asking to generate/create an image."""
    t = text.lower()
    gen_words = ["generate", "buat", "bikin", "create", "gambar", "foto", "image",
                 "buatin", "buatkan", "bikinin", "bikinkan", "tolong buat", "tolong bikin",
                 "gambarkan", "gambarin", "draw", "ilustrasi", "desain", "design"]
    img_words = ["gambar", "foto", "image", "picture", "pic", "ilustrasi", "wallpaper",
                 "poster", "banner", "icon", "logo", "meme", "artwork", "art"]
    has_gen = any(w in t for w in gen_words)
    has_img = any(w in t for w in img_words)
    return has_gen and has_img


# ========================
# DOCUMENT GENERATION
# ========================

def generate_pdf_content(title: str, content: str, save_dir: str = None) -> str:
    """Generate a PDF file from text content. Returns path to saved file."""
    if not REPORTLAB_AVAILABLE:
        return ""
    try:
        if save_dir is None:
            save_dir = str(Path.home() / "ai-agent" / "generated")
        Path(save_dir).mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = re.sub(r'[^\w\s-]', '', title)[:50].strip().replace(' ', '_')
        filename = f"{safe_title}_{timestamp}.pdf"
        filepath = os.path.join(save_dir, filename)

        doc = SimpleDocTemplate(filepath, pagesize=A4,
                                leftMargin=20*mm, rightMargin=20*mm,
                                topMargin=20*mm, bottomMargin=20*mm)
        styles = getSampleStyleSheet()
        title_style = styles['Title']
        body_style = ParagraphStyle('Body', parent=styles['Normal'],
                                    fontSize=11, leading=14, spaceAfter=6,
                                    alignment=TA_LEFT)
        story = []
        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 12))
        for line in content.split('\n'):
            if line.strip():
                safe_line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                story.append(Paragraph(safe_line, body_style))
            else:
                story.append(Spacer(1, 6))
        doc.build(story)
        return filepath
    except Exception as e:
        logging.error(f"PDF generation error: {e}")
        return ""

def generate_docx_content(title: str, content: str, save_dir: str = None) -> str:
    """Generate a DOCX file from text content. Returns path to saved file."""
    if not DOCX_AVAILABLE:
        return ""
    try:
        if save_dir is None:
            save_dir = str(Path.home() / "ai-agent" / "generated")
        Path(save_dir).mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = re.sub(r'[^\w\s-]', '', title)[:50].strip().replace(' ', '_')
        filename = f"{safe_title}_{timestamp}.docx"
        filepath = os.path.join(save_dir, filename)

        doc = DocxDocument()
        doc.add_heading(title, level=1)
        for line in content.split('\n'):
            if line.strip():
                doc.add_paragraph(line)
        doc.save(filepath)
        return filepath
    except Exception as e:
        logging.error(f"DOCX generation error: {e}")
        return ""

def should_generate_document(text: str) -> bool:
    """Check if user is asking to generate a document/file."""
    t = text.lower()
    gen_words = ["generate", "buat", "bikin", "create", "buatin", "buatkan",
                 "bikinin", "bikinkan", "tolong buat", "tolong bikin"]
    doc_words = ["pdf", "dokumen", "document", "docx", "word", "file", "surat",
                 "laporan", "report", "resume", "cv"]
    has_gen = any(w in t for w in gen_words)
    has_doc = any(w in t for w in doc_words)
    return has_gen and has_doc


# ========================
# VIDEO FRAME EXTRACTION
# ========================

def extract_video_frames(video_path: str, num_frames: int = 4) -> list:
    """Extract frames from video using ffmpeg. Returns list of frame file paths."""
    try:
        # Get video duration
        probe_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", video_path]
        result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=15)
        duration = float(result.stdout.strip()) if result.stdout.strip() else 10.0

        frame_dir = Path.home() / "ai-agent" / "temp_frames"
        frame_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        frames = []
        for i in range(num_frames):
            t = duration * (i + 1) / (num_frames + 1)
            frame_path = frame_dir / f"frame_{timestamp}_{i}.jpg"
            cmd = ["ffmpeg", "-y", "-ss", str(t), "-i", video_path,
                   "-frames:v", "1", "-q:v", "2", str(frame_path)]
            subprocess.run(cmd, capture_output=True, timeout=15)
            if frame_path.exists() and frame_path.stat().st_size > 100:
                frames.append(str(frame_path))

        return frames
    except Exception as e:
        logging.error(f"Video frame extraction error: {e}")
        return []

def cleanup_frames(frame_paths: list):
    """Remove temporary frame files."""
    for p in frame_paths:
        try:
            os.unlink(p)
        except Exception:
            pass


# ========================
# MAIN MESSAGE HANDLER
# ========================


