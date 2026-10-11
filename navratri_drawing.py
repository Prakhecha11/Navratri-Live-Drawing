import os
import importlib

try:
    cv2 = importlib.import_module("cv2")
except ModuleNotFoundError as exc:
    if exc.name != "cv2":
        raise
    raise SystemExit("OpenCV is required. Install it with: python -m pip install opencv-python") from exc

try:
    np = importlib.import_module("numpy")
except ModuleNotFoundError as exc:
    if exc.name != "numpy":
        raise
    raise SystemExit("NumPy is required. Install it with: python -m pip install numpy") from exc


# ---------------------------------------------------------------- screen size
def get_screen_size():
    """Return the real screen size in pixels (falls back to 1366 x 768)."""
    try:
        import ctypes
        user32 = ctypes.windll.user32            # exists on Windows only
        try:
            user32.SetProcessDPIAware()          # real pixels, not scaled ones
        except Exception:
            pass
        width, height = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        if width > 0 and height > 0:
            return width, height
    except Exception:
        pass
    try:
        import tkinter
        root = tkinter.Tk()
        root.withdraw()
        width, height = root.winfo_screenwidth(), root.winfo_screenheight()
        root.destroy()
        if width > 0 and height > 0:
            return width, height
    except Exception:
        pass
    return 1366, 768


# ---------------------------------------------------------------- settings
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_PATH = os.path.join(BASE_DIR, "mataji.jpg")
OUTPUT_PATH = os.path.join(BASE_DIR, "mataji_sketch_output.png")
WINDOW_NAME = "Mata Ji Sketch"

# The canvas is exactly as big as your screen and is shown full-screen, so
# nothing is hidden behind the taskbar and no empty area is left at the sides.
WIDTH, HEIGHT = get_screen_size()

TITLE_BAND = int(HEIGHT * 0.18)       # space above the photo for "JAI MATA DI"
BOTTOM_MARGIN = int(HEIGHT * 0.04)    # small gap below the photo
IMAGE_SIZE = min(HEIGHT - TITLE_BAND - BOTTOM_MARGIN, WIDTH - 40)  # square photo
IMAGE_X = (WIDTH - IMAGE_SIZE) // 2   # photo is centred left-to-right
IMAGE_Y = TITLE_BAND                  # photo sits right under the title
PROCESS_SIZE = 800                    # outlines are detected at this size

# Drawing speed: how many outline points are drawn per animation frame.
# Higher = faster drawing. (Original was 5; 14 is roughly 3x faster.)
POINTS_PER_FRAME = 14

# Colours are in BGR order (OpenCV style)
PAPER = (235, 242, 248)     # warm off-white paper
PENCIL = (50, 50, 50)       # dark grey pencil
GOLD = (55, 175, 212)       # gold marker for mouse drawing
BG_TOP = (20, 60, 200)      # deep saffron-red at the top
BG_BOTTOM = (51, 153, 255)  # saffron at the bottom

# Closing text shown at the end (above the photo, centred)
TITLE_TEXT = "JAI MATA DI"
TITLE_FONT = cv2.FONT_HERSHEY_TRIPLEX | cv2.FONT_ITALIC  # bold italic style
TITLE_FILL = (0, 215, 255)      # bright gold letters
TITLE_OUTLINE = (10, 10, 100)   # deep maroon outline
TITLE_SHADOW = (0, 0, 40)       # dark drop shadow


# ---------------------------------------------------------------- helpers
def display_frame(frame, delay=1):
    """Show a frame (already screen-sized) and return the pressed key."""
    cv2.imshow(WINDOW_NAME, frame)
    return cv2.waitKey(delay) & 0xFF


def make_final_scene(photo):
    """Build the coloured final image: gradient background + framed photo."""
    gradient = np.linspace(BG_TOP, BG_BOTTOM, HEIGHT).astype(np.uint8)  # (HEIGHT, 3)
    scene = np.repeat(gradient[:, None, :], WIDTH, axis=1)               # (HEIGHT, WIDTH, 3)

    # Same square resize that was used for the outlines, so everything lines up.
    resized = cv2.resize(photo, (IMAGE_SIZE, IMAGE_SIZE), interpolation=cv2.INTER_AREA)
    scene[IMAGE_Y:IMAGE_Y + IMAGE_SIZE, IMAGE_X:IMAGE_X + IMAGE_SIZE] = resized

    # Thin gold frame around the photo
    cv2.rectangle(
        scene,
        (IMAGE_X - 4, IMAGE_Y - 4),
        (IMAGE_X + IMAGE_SIZE + 3, IMAGE_Y + IMAGE_SIZE + 3),
        GOLD,
        4,
        cv2.LINE_AA,
    )
    return scene


def draw_title(scene, text=TITLE_TEXT):
    """Draw bold, outlined text with a drop shadow, centred above the photo."""
    # Pick the largest font size that fits nicely inside the top band.
    scale = 5.0
    while True:
        thickness = max(2, int(scale * 2))
        (text_w, text_h), _ = cv2.getTextSize(text, TITLE_FONT, scale, thickness)
        if (text_w <= WIDTH * 0.75 and text_h <= TITLE_BAND * 0.55) or scale <= 0.5:
            break
        scale -= 0.05

    outline_extra = max(4, int(scale * 2.5))
    shadow_shift = max(3, int(scale * 1.5))

    x = (WIDTH - text_w) // 2             # horizontally centred
    y = (TITLE_BAND + text_h) // 2        # vertically centred in the top band

    # Shadow, then thick outline, then the gold letters on top.
    cv2.putText(scene, text, (x + shadow_shift, y + shadow_shift), TITLE_FONT, scale,
                TITLE_SHADOW, thickness + outline_extra, cv2.LINE_AA)
    cv2.putText(scene, text, (x, y), TITLE_FONT, scale,
                TITLE_OUTLINE, thickness + outline_extra, cv2.LINE_AA)
    cv2.putText(scene, text, (x, y), TITLE_FONT, scale,
                TITLE_FILL, thickness, cv2.LINE_AA)


# ---------------------------------------------------------------- main
def main():
    photo = cv2.imread(IMAGE_PATH)
    if photo is None:
        raise FileNotFoundError(
            f"Could not find mataji.jpg at:\n{IMAGE_PATH}\n"
            "Keep mataji.jpg in the same folder as this Python file."
        )

    # Resize for contour extraction; the full original image is kept for the final reveal.
    drawing_source = cv2.resize(photo, (PROCESS_SIZE, PROCESS_SIZE), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(drawing_source, cv2.COLOR_BGR2GRAY)
    smoothed = cv2.bilateralFilter(gray, 7, 50, 50)
    edges = cv2.Canny(smoothed, 55, 135)

    # Find the image's actual outlines: Mata Ji, lion, temple and visible details.
    # [-2] works for both OpenCV 3 and OpenCV 4 return formats.
    contours = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)[-2]
    ratio = IMAGE_SIZE / PROCESS_SIZE      # scale outlines to the on-screen photo size
    prepared = []
    for contour in contours:
        length = cv2.arcLength(contour, False)
        if length < 24:
            continue
        simplified = cv2.approxPolyDP(contour, 1.25, False)
        if len(simplified) >= 2:
            moved = np.rint(simplified.astype(np.float32) * ratio).astype(np.int32)
            moved[:, 0, 0] += IMAGE_X
            moved[:, 0, 1] += IMAGE_Y
            prepared.append((length, moved))

    # Longer structures (overall silhouette, lion, temple arches) appear first.
    prepared.sort(key=lambda item: item[0], reverse=True)
    prepared = prepared[:650]

    # Full-screen window: no taskbar overlap, no empty desktop area at the sides.
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    # Draw on paper. Only the artwork is shown; no stage labels.
    sketch = np.full((HEIGHT, WIDTH, 3), PAPER, dtype=np.uint8)
    display_frame(sketch, 250)

    # Progressive stroke animation: small consecutive segments are drawn at a time.
    stop_drawing_early = False
    for _length, contour in prepared:
        points = contour.reshape(-1, 2)
        if len(points) < 2:
            continue
        # Several connected points per frame gives a hand-drawn tracing effect.
        for end in range(2, len(points) + 1, POINTS_PER_FRAME):
            segment = points[max(0, end - POINTS_PER_FRAME - 1):end].reshape(-1, 1, 2)
            if len(segment) >= 2:
                cv2.polylines(sketch, [segment], False, PENCIL, 1, cv2.LINE_AA)
            key = display_frame(sketch, 1)
            if key in (ord('q'), 27):
                stop_drawing_early = True
                break
        if stop_drawing_early:
            break
        # Join any final points that did not fall on the per-frame rhythm.
        cv2.polylines(sketch, [contour], False, PENCIL, 1, cv2.LINE_AA)

    if stop_drawing_early:
        cv2.destroyAllWindows()
        return

    # Hold the finished sketch briefly before the colour reveal.
    if display_frame(sketch, 700) in (ord('q'), 27):
        cv2.destroyAllWindows()
        return

    final_scene = make_final_scene(photo)

    # Colour and background arrive only after the drawing is complete.
    # This avoids drawing noisy detected edges over Mata Ji's face in the final image.
    for step in range(1, 36):
        amount = step / 35.0
        transition = cv2.addWeighted(sketch, 1.0 - amount, final_scene, amount, 0)
        key = display_frame(transition, 18)
        if key in (ord('q'), 27):
            cv2.destroyAllWindows()
            return

    # Finally, fade in the "JAI MATA DI" text above the photo.
    titled_scene = final_scene.copy()
    draw_title(titled_scene)
    for step in range(1, 31):
        amount = step / 30.0
        fade = cv2.addWeighted(final_scene, 1.0 - amount, titled_scene, amount, 0)
        key = display_frame(fade, 25)
        if key in (ord('q'), 27):
            cv2.destroyAllWindows()
            return

    # The text stays on the canvas when you clear (C) or save (S) your own marks.
    base_canvas = titled_scene.copy()
    drawing_canvas = titled_scene.copy()
    drawing = False
    previous_point = None

    def mouse_callback(event, mouse_x, mouse_y, flags, param):
        nonlocal drawing, previous_point
        # The canvas is exactly screen-sized, so mouse position = canvas position.
        x = max(0, min(WIDTH - 1, int(mouse_x)))
        y = max(0, min(HEIGHT - 1, int(mouse_y)))
        point = (x, y)

        if event == cv2.EVENT_LBUTTONDOWN:
            drawing = True
            previous_point = point
        elif event == cv2.EVENT_MOUSEMOVE and drawing:
            if previous_point is not None:
                cv2.line(drawing_canvas, previous_point, point, GOLD, 3, cv2.LINE_AA)
            previous_point = point
        elif event == cv2.EVENT_LBUTTONUP:
            drawing = False
            previous_point = None

    cv2.setMouseCallback(WINDOW_NAME, mouse_callback)
    print("Animation finished. Drag mouse to draw | C: clear marks | S: save | Q/Esc: quit")

    while True:
        key = display_frame(drawing_canvas, 20)
        if key == ord('c'):
            drawing_canvas = base_canvas.copy()
        elif key == ord('s'):
            if cv2.imwrite(OUTPUT_PATH, drawing_canvas):
                print(f"Saved as {OUTPUT_PATH}")
            else:
                print("Could not save the image.")
        elif key in (ord('q'), 27):
            break
        # Stop cleanly if the window is closed.
        if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()