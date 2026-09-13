#!/usr/bin/env python3

import os
import sys
import time
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox

from PIL import Image, ImageOps, ImageDraw

from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306


# ============================================================
# POP OLED MEDIA PLAYER
# Raspberry Pi Zero W
# SSD1306 128x64
# I2C 0x3C
# ============================================================

WIDTH = 128
HEIGHT = 64
ADDRESS = 0x3C


# ============================================================
# OLED
# ============================================================

serial = i2c(
    port=1,
    address=ADDRESS
)

oled = ssd1306(
    serial,
    width=WIDTH,
    height=HEIGHT
)


# ============================================================
# FILE TYPES
# ============================================================

IMAGE_EXTENSIONS = (
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".gif",
    ".webp",
    ".tif",
    ".tiff"
)

VIDEO_EXTENSIONS = (
    ".mp4",
    ".avi",
    ".mkv",
    ".mov",
    ".webm",
    ".mpeg",
    ".mpg"
)


# ============================================================
# OLED TEXT
# ============================================================

def oled_text(lines):

    image = Image.new(
        "1",
        (WIDTH, HEIGHT),
        0
    )

    draw = ImageDraw.Draw(image)

    y = 0

    for line in lines:

        draw.text(
            (2, y),
            str(line)[:21],
            fill=255
        )

        y += 11

        if y >= HEIGHT:
            break

    oled.display(image)


# ============================================================
# IMAGE ORIENTATION WINDOW
# ============================================================

def choose_orientation():

    result = {
        "value": "auto"
    }

    root = tk.Tk()

    root.title("POP - Orientation")

    root.geometry("330x150")

    root.resizable(False, False)

    root.attributes("-topmost", True)

    label = tk.Label(
        root,
        text="Choose image orientation",
        font=("Arial", 13)
    )

    label.pack(
        pady=15
    )

    frame = tk.Frame(root)

    frame.pack()

    def choose(value):

        result["value"] = value

        root.destroy()

    tk.Button(
        frame,
        text="AUTO",
        width=9,
        command=lambda: choose("auto")
    ).pack(
        side="left",
        padx=5
    )

    tk.Button(
        frame,
        text="LANDSCAPE",
        width=10,
        command=lambda: choose("landscape")
    ).pack(
        side="left",
        padx=5
    )

    tk.Button(
        frame,
        text="PORTRAIT",
        width=9,
        command=lambda: choose("portrait")
    ).pack(
        side="left",
        padx=5
    )

    root.mainloop()

    return result["value"]


# ============================================================
# FULL SCREEN IMAGE
# ============================================================

def prepare_image(filename, orientation):

    image = Image.open(filename)

    # --------------------------------------------------------
    # Transparency
    # --------------------------------------------------------

    if image.mode in ("RGBA", "LA"):

        background = Image.new(
            "RGB",
            image.size,
            "black"
        )

        alpha = image.getchannel("A")

        background.paste(
            image.convert("RGB"),
            mask=alpha
        )

        image = background

    else:

        image = image.convert("RGB")


    # --------------------------------------------------------
    # Orientation
    # --------------------------------------------------------

    if orientation == "portrait":

        image = image.rotate(
            90,
            expand=True
        )

    elif orientation == "landscape":

        # Rotate portrait source into landscape
        if image.height > image.width:

            image = image.rotate(
                90,
                expand=True
            )


    # --------------------------------------------------------
    # Grayscale
    # --------------------------------------------------------

    image = image.convert("L")


    # --------------------------------------------------------
    # FULL SCREEN FIT
    #
    # This crops excess area.
    # No black borders.
    # Entire 128x64 OLED is used.
    # --------------------------------------------------------

    image = ImageOps.fit(
        image,
        (WIDTH, HEIGHT),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5)
    )


    # --------------------------------------------------------
    # Contrast
    # --------------------------------------------------------

    image = ImageOps.autocontrast(
        image
    )


    # --------------------------------------------------------
    # 1-bit OLED
    # --------------------------------------------------------

    image = image.convert("1")

    return image


# ============================================================
# DISPLAY IMAGE
# ============================================================

def display_image(filename):

    orientation = choose_orientation()

    oled_text([
        "LOADING IMAGE...",
        "",
        os.path.basename(filename)
    ])

    time.sleep(0.2)

    try:

        image = prepare_image(
            filename,
            orientation
        )

        oled.display(image)

        print()
        print("IMAGE")
        print(filename)
        print("Orientation:", orientation)
        print("OLED: 128x64")
        print()

    except Exception as error:

        print("Image error:", error)

        oled_text([
            "IMAGE ERROR",
            "",
            str(error)[:20]
        ])


# ============================================================
# GET VIDEO FPS
# ============================================================

def get_video_fps(filename):

    try:

        command = [
            "ffprobe",
            "-v",
            "0",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=r_frame_rate",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            filename
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=5
        )

        value = result.stdout.strip()

        if "/" in value:

            a, b = value.split("/")

            fps = float(a) / float(b)

        else:

            fps = float(value)

        if fps <= 0 or fps > 60:

            fps = 15

        return fps

    except:

        return 15


# ============================================================
# VIDEO DISPLAY
# ============================================================

def play_video(filename):

    fps = get_video_fps(filename)

    print()
    print("VIDEO")
    print(filename)
    print("FPS:", fps)
    print("OLED: 128x64")
    print()

    oled_text([
        "VIDEO",
        "",
        "Loading...",
        "",
        "Press Ctrl+C"
    ])

    time.sleep(0.3)


    # --------------------------------------------------------
    # FFmpeg
    #
    # Convert video directly to 128x64 grayscale frames.
    # --------------------------------------------------------

    command = [
        "ffmpeg",
        "-loglevel",
        "error",
        "-i",
        filename,
        "-vf",
        (
            "scale=128:64:"
            "force_original_aspect_ratio=increase,"
            "crop=128:64"
        ),
        "-f",
        "rawvideo",
        "-pix_fmt",
        "gray",
        "-"
    ]


    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=1024 * 1024
    )


    frame_size = WIDTH * HEIGHT

    frame_time = 1.0 / fps

    frame_count = 0

    try:

        while True:

            start_time = time.perf_counter()

            data = process.stdout.read(
                frame_size
            )

            if len(data) != frame_size:

                break


            # ------------------------------------------------
            # Convert raw grayscale frame to PIL
            # ------------------------------------------------

            frame = Image.frombytes(
                "L",
                (WIDTH, HEIGHT),
                data
            )


            # ------------------------------------------------
            # Convert to 1-bit
            # ------------------------------------------------

            frame = frame.convert("1")


            # ------------------------------------------------
            # Display
            # ------------------------------------------------

            oled.display(frame)


            frame_count += 1


            # ------------------------------------------------
            # Timing
            # ------------------------------------------------

            elapsed = (
                time.perf_counter()
                - start_time
            )

            remaining = (
                frame_time
                - elapsed
            )

            if remaining > 0:

                time.sleep(
                    remaining
                )


    except KeyboardInterrupt:

        print()
        print("Video stopped by user.")

    finally:

        process.kill()

        process.wait()


    print(
        "Frames displayed:",
        frame_count
    )


# ============================================================
# FILE SELECTOR
# ============================================================

def select_media():

    root = tk.Tk()

    root.withdraw()

    root.attributes(
        "-topmost",
        True
    )

    filename = filedialog.askopenfilename(
        title="POP - Select Image or Video",
        initialdir="/",
        filetypes=[
            (
                "Images & Videos",
                "*.png *.jpg *.jpeg *.bmp *.gif *.webp "
                "*.tif *.tiff *.mp4 *.avi *.mkv *.mov "
                "*.webm *.mpeg *.mpg"
            ),
            (
                "Images",
                "*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tif *.tiff"
            ),
            (
                "Videos",
                "*.mp4 *.avi *.mkv *.mov *.webm *.mpeg *.mpg"
            ),
            (
                "All files",
                "*.*"
            )
        ]
    )

    root.destroy()

    return filename


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("================================")
    print("       POP MEDIA PLAYER")
    print("================================")
    print("Raspberry Pi Zero W")
    print("SSD1306 128x64")
    print("I2C Address: 0x3C")
    print("================================")
    print()


    oled_text([
        "POP MEDIA PLAYER",
        "",
        "Select image/video..."
    ])


    time.sleep(0.5)


    filename = select_media()


    if not filename:

        oled_text([
            "NO FILE",
            "",
            "Selection cancelled"
        ])

        time.sleep(2)

        oled.clear()

        return


    extension = os.path.splitext(
        filename
    )[1].lower()


    # --------------------------------------------------------
    # IMAGE
    # --------------------------------------------------------

    if extension in IMAGE_EXTENSIONS:

        display_image(
            filename
        )


    # --------------------------------------------------------
    # VIDEO
    # --------------------------------------------------------

    elif extension in VIDEO_EXTENSIONS:

        play_video(
            filename
        )


    # --------------------------------------------------------
    # UNKNOWN
    # --------------------------------------------------------

    else:

        oled_text([
            "UNSUPPORTED FILE",
            "",
            extension
        ])

        print(
            "Unsupported:",
            filename
        )


    # --------------------------------------------------------
    # Keep program alive
    # --------------------------------------------------------

    try:

        while True:

            time.sleep(1)

    except KeyboardInterrupt:

        print(
            "\nPOP stopped."
        )

        oled.clear()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()
