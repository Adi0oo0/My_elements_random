# folder_sorter

A small Python utility that sorts a folder's **direct children** into
clearly-named category subdirectories. Nothing is moved more than one
level deep.

## What it does

Pick a folder. The script:

1. Scans the folder's direct children (no recursion into subfolders).
2. Classifies each file by extension into a category.
3. Creates category subfolders (`Images/`, `Videos/`, `Audio/`,
   `Documents/`, `Code/`, `Archives/`, `Installers/`, `Fonts/`,
   `Other/`).
4. Moves each file into the matching subfolder. Name collisions get
   ` (n)` appended so nothing is overwritten.
5. Drops a `README.txt` into each new category folder explaining what
   goes there.

**Default mode is dry run.** Files are only moved after you confirm.

## Categories

| Folder | Holds |
| --- | --- |
| `Images/` | `.jpg .png .gif .webp .svg .heic .tiff .psd ...` |
| `Videos/` | `.mp4 .mov .avi .mkv .webm .m4v ...` |
| `Audio/`   | `.mp3 .wav .flac .aac .ogg .m4a .opus ...` |
| `Documents/` | `.pdf .docx .txt .md .xlsx .pptx .csv .epub ...` |
| `Code/`   | `.py .js .ts .html .css .json .yaml .sh .java ...` |
| `Archives/` | `.zip .rar .7z .tar .gz .iso .dmg ...` |
| `Installers/` | `.exe .msi .apk .deb .rpm .whl ...` |
| `Fonts/`  | `.ttf .otf .woff .woff2 ...` |
| `Other/`  | anything that didn't match the categories above |

The full extension list lives in `folder_sorter.py` under `CATEGORIES`.

## Usage

### Interactive (easiest)

```bash
python folder_sorter.py
```

You'll be prompted for a folder. On Windows you can drag-and-drop a
folder onto the terminal window to paste its full path (quotes will be
stripped automatically).

Then the script prints a plan (dry run) and asks:

```
Apply these moves now? [y/N]:
```

Type `y` to actually move files, `n` to quit without changes.

### Non-interactive

```bash
# Dry run, plan-only:
python folder_sorter.py --folder "C:\Users\You\Downloads"

# Actually move files:
python folder_sorter.py --folder "C:\Users\You\Downloads" --apply

# Move files but skip writing README.txt notes:
python folder_sorter.py --folder "C:\Users\You\Downloads" --apply --no-readme
```

## Important behavior notes

- **One level only.** Subfolders of the chosen folder are *not* opened
  or sorted. They stay where they are. The category folders created at
  the parent level are also untouched on subsequent runs (files already
  in them are not re-sorted).
- **Skip existing subfolders.** If `Images/` already exists from a
  prior run, the script will still move matching files into it and will
  *not* overwrite an existing `README.txt` there.
- **Name collisions** get a numeric suffix (`photo (1).jpg`).
- **README.txt** is written once into each new category folder. Delete
  it anytime; the script will recreate it on the next run that creates
  the folder.
- **Cancel safely.** Although the dry-run defaults protect you, hitting
  `Ctrl-C` mid-move prints a warning. If you cancel partway through,
  re-run the script -- already-moved files are in their category
  folders and will be skipped on the next pass.

## Requirements

- Python 3.8+ (uses `pathlib` and dataclasses). No third-party deps.

## Tested on

- Windows 10 / 11 (the primary target)
- macOS / Linux (works the same; paths just look different)
