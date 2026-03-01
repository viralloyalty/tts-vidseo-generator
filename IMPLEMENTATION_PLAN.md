# Bilingual Video Editor -- Implementation Plan

## Executive Summary

This document details the full architecture and implementation plan for transforming the existing Dual-Language TTS Subtitle Video Generator into a complete offline-capable video editor. The editor will allow users to generate bilingual (English/Spanish) subtitle videos, import external 1080p footage, arrange everything on a 3-track timeline, and export two final MP4 files -- one English, one Spanish -- each with the external video as background, language-specific subtitles, and language-specific TTS audio.

All project data (generated videos, imported footage, timeline state) will be stored in a user-chosen work order folder on the local file system. This folder is portable and can be shared via OneDrive so other team members can open it in their own copy of the app and make edits.

---

## Table of Contents

1. [Deployment Model](#1-deployment-model)
2. [Technology Stack](#2-technology-stack)
3. [Offline Strategy](#3-offline-strategy)
4. [Project Folder Structure](#4-project-folder-structure)
5. [Project File Format](#5-project-file-format)
6. [Application Architecture](#6-application-architecture)
7. [Feature Specifications](#7-feature-specifications)
8. [Database Schema (Supabase)](#8-database-schema-supabase)
9. [Timeline Editor Design](#9-timeline-editor-design)
10. [Video Import and Optimization](#10-video-import-and-optimization)
11. [Export Pipeline](#11-export-pipeline)
12. [Sharing and Portability](#12-sharing-and-portability)
13. [Build Order](#13-build-order)
14. [Corporate Environment Testing Checklist](#14-corporate-environment-testing-checklist)
15. [Performance Considerations](#15-performance-considerations)
16. [Sources and References](#16-sources-and-references)

---

## 1. Deployment Model

### Recommended Options (in order of preference)

#### Option A -- Python Local Server (Safest, Already Proven)

This is an enhanced version of what you already have. It works today in your corporate environment.

| Aspect | Details |
|--------|---------|
| How it works | User double-clicks a `.bat` file (or runs `python server.py`). Chrome opens to `localhost:8000`. |
| File system access | Uses the File System Access API (`showDirectoryPicker()`) to let users pick a work order folder. |
| Offline | All app files are local. TTS models download once on first run, cached in browser storage. |
| Distribution | Share the app folder (zip or OneDrive). Each person has a copy on their machine. |
| Pros | Already works in your environment. No special browser features needed beyond File System Access API. No install process. |
| Cons | Requires Python installed. User must start the server manually (or via `.bat` file). |

**Enhancement over current setup:** Add a `start.bat` file that launches the Python server and opens Chrome automatically:
```bat
@echo off
start chrome --new-window http://localhost:8000
python server.py
```

#### Option B -- Progressive Web App (PWA)

| Aspect | Details |
|--------|---------|
| How it works | User visits `localhost:8000` once, clicks "Install" in Chrome. App appears in Start Menu like a regular program. |
| File system access | Same File System Access API as Option A. |
| Offline | After install, works without the Python server running. All assets cached by service worker. |
| Pros | Feels like a native app. No server needed after install. Auto-updates when server is available. |
| Cons | PWA install may be blocked by corporate Chrome policy. Requires testing. |

#### Option C -- Electron App (Most Capable, Heaviest)

| Aspect | Details |
|--------|---------|
| How it works | Distribute as a `.exe` installer or portable `.exe`. Full desktop application. |
| File system access | Full Node.js `fs` module. No browser API restrictions. |
| Offline | Completely standalone. |
| Pros | Most reliable file system access. No browser policy concerns. Can bundle Python/FFmpeg. |
| Cons | ~150MB+ installer. Corporate IT may block `.exe` installs. Heavier to maintain and distribute. |

### What To Test At Work (for Option A and B)

Run this JavaScript snippet in Chrome DevTools console (`F12` > Console) at work:

```javascript
// Test 1: File System Access API (directory picker)
async function testDirectoryPicker() {
  try {
    const dir = await window.showDirectoryPicker({ mode: 'readwrite' });
    console.log('SUCCESS: Directory picker works. Selected:', dir.name);
    // Test writing a file
    const file = await dir.getFileHandle('test.txt', { create: true });
    const writable = await file.createWritable();
    await writable.write('test');
    await writable.close();
    console.log('SUCCESS: File writing works.');
    // Clean up
    await dir.removeEntry('test.txt');
    console.log('SUCCESS: File deletion works.');
  } catch (e) {
    console.error('FAILED:', e.message);
  }
}
testDirectoryPicker();

// Test 2: Check Chrome policies
// Navigate to chrome://policy in a new tab and look for:
// - DefaultFileSystemReadGuardSetting (should NOT be 2)
// - DefaultFileSystemWriteGuardSetting (should NOT be 2)
// - FileSystemWriteBlockedForUrls (should NOT include localhost)
```

```javascript
// Test 3: SharedArrayBuffer (needed for FFmpeg.wasm)
console.log('SharedArrayBuffer available:', typeof SharedArrayBuffer !== 'undefined');

// Test 4: WebCodecs (needed for Mediabunny video processing)
console.log('VideoDecoder available:', typeof VideoDecoder !== 'undefined');
console.log('VideoEncoder available:', typeof VideoEncoder !== 'undefined');
console.log('AudioDecoder available:', typeof AudioDecoder !== 'undefined');
console.log('AudioEncoder available:', typeof AudioEncoder !== 'undefined');
```

```javascript
// Test 5: PWA installability (for Option B)
// Navigate to localhost:8000 in Chrome, then check:
// - Is there an "Install" icon in the address bar?
// - Or open DevTools > Application > Manifest to see if install is available
```

**If Tests 1-4 pass:** Option A (Python server) will work perfectly.
**If Test 5 also passes:** Option B (PWA) is available as an upgrade.
**If Test 1 fails:** We need Option C (Electron) or a fallback using `<input type="file">` with manual save/load.

---

## 2. Technology Stack

### Current Stack (Keeping)
| Component | Technology | Notes |
|-----------|-----------|-------|
| TTS (English) | Kokoro-82M via kokoro-js | ~180MB, downloaded once |
| TTS (Spanish) | MMS-TTS-SPA via Transformers.js | Lightweight quantized model |
| Subtitle Video Gen | FFmpeg.wasm | Generates transparent .mov with burned-in subtitles |
| Service Worker | coi-serviceworker.js | Enables SharedArrayBuffer via COOP/COEP headers |
| Server | Python http.server | Serves files with required headers |

### New Stack (Adding)
| Component | Technology | Why |
|-----------|-----------|-----|
| Build tool | Vite | Bundles npm packages, dev server with HMR, produces single deployable folder |
| Video processing | Mediabunny | Hardware-accelerated via WebCodecs, microsecond-accurate trim/cut, H.264 encode/decode, zero dependencies |
| Timeline UI | Custom Canvas | Your 3-track paired layout is too specific for generic libraries. Canvas gives full control |
| CSS Framework | Tailwind CSS | Already using. Will install as npm package instead of CDN for offline use |
| ZIP Library | JSZip | Already using. Will install as npm package instead of CDN |
| File Storage | File System Access API | Read/write to user-chosen work order folder on local disk |
| Project State | JSON file | `project.json` in the work order folder. Portable, human-readable |
| App Metadata | Supabase | Recent projects list, user preferences, model cache status |

### Removing (CDN Dependencies)
| Dependency | Currently | Replacing With |
|-----------|-----------|---------------|
| Tailwind CSS | `cdn.tailwindcss.com` | `npm install tailwindcss` (bundled by Vite) |
| JSZip | `cdnjs.cloudflare.com` | `npm install jszip` (bundled by Vite) |
| Kokoro-js | `cdn.jsdelivr.net` | `npm install kokoro-js` (bundled, models cached locally) |
| Transformers.js | `cdn.jsdelivr.net` | `npm install @xenova/transformers` (bundled, models cached locally) |

After migration, the app loads zero resources from the internet during normal operation. TTS model weights are downloaded once on first use and cached in the browser's Cache Storage (or IndexedDB) permanently.

---

## 3. Offline Strategy

### First Run (Internet Required)
1. User downloads the app folder (from OneDrive, USB, or shared drive)
2. Runs `start.bat` which launches Python server + Chrome
3. App loads instantly from local files (HTML, JS, CSS all bundled)
4. On first TTS generation, models download from CDN and cache in browser storage
5. After models are cached, internet is never needed again

### Subsequent Runs (No Internet Needed)
1. User runs `start.bat`
2. App loads from local files
3. TTS models load from browser cache
4. All video processing happens locally via WebCodecs/FFmpeg.wasm
5. All project files read/write to the local work order folder

### Model Caching Details
| Model | Size | Cache Location | Cache Duration |
|-------|------|---------------|----------------|
| Kokoro-82M (English TTS) | ~180MB | Browser Cache Storage | Permanent until cleared |
| MMS-TTS-SPA (Spanish TTS) | ~50MB | Browser Cache Storage | Permanent until cleared |

The app will show a "Model Status" indicator:
- Green: "Models cached -- ready for offline use"
- Yellow: "Models not yet downloaded -- internet required for first generation"

---

## 4. Project Folder Structure

When a user creates a project and selects a work order folder, the app creates this structure:

```
WO-12345/                          <-- User-chosen folder (work order number)
|
|-- project.json                   <-- Timeline state, settings, all metadata
|
|-- generated/                     <-- TTS subtitle videos (auto-generated)
|   |-- en/
|   |   |-- en_01_safety_first.mov
|   |   |-- en_02_step_two.mov
|   |   +-- ...
|   +-- es/
|       |-- es_01_seguridad_primero.mov
|       |-- es_02_paso_dos.mov
|       +-- ...
|
|-- media/                         <-- Imported external videos (optimized copies)
|   |-- clip_001_original_name.mp4
|   |-- clip_002_another_clip.mp4
|   +-- ...
|
+-- thumbnails/                    <-- Auto-generated preview thumbnails
    |-- clip_001_strip.jpg         <-- Filmstrip thumbnails for timeline
    |-- clip_002_strip.jpg
    +-- ...
```

### What Is NOT In The Work Order Folder
- The app itself (each person has their own copy)
- TTS models (cached in each person's browser)
- Exported final videos (user chooses a separate download location)
- Temporary processing files

---

## 5. Project File Format

The `project.json` file stores the complete project state. This is what makes projects portable across computers.

```jsonc
{
  "version": "1.0",
  "name": "WO-12345",
  "created": "2026-03-01T10:00:00Z",
  "modified": "2026-03-01T14:30:00Z",

  "settings": {
    "fontStyle": "Arial",
    "dropShadowSize": 4,
    "resolution": { "width": 1920, "height": 1080 },
    "frameRate": 30
  },

  "scripts": {
    "en": "Full English script text...",
    "es": "Full Spanish script text..."
  },

  "pairs": [
    {
      "index": 1,
      "en": {
        "text": "Safety is our number one priority.",
        "videoFile": "generated/en/en_01_safety_is_our.mov",
        "durationMs": 3200,
        "status": "generated"
      },
      "es": {
        "text": "La seguridad es nuestra prioridad numero uno.",
        "videoFile": "generated/es/es_01_la_seguridad_es.mov",
        "durationMs": 3800,
        "status": "generated"
      },
      "pairDurationMs": 3800
    }
  ],

  "media": [
    {
      "id": "clip_001",
      "originalName": "safety_walkthrough.mp4",
      "file": "media/clip_001_safety_walkthrough.mp4",
      "durationMs": 45000,
      "width": 1920,
      "height": 1080,
      "thumbnailStrip": "thumbnails/clip_001_strip.jpg",
      "optimizationStatus": "complete"
    }
  ],

  "timeline": {
    "tracks": {
      "en": [
        { "pairIndex": 1, "startMs": 0, "endMs": 3200 },
        { "pairIndex": 2, "startMs": 3800, "endMs": 7100 }
      ],
      "es": [
        { "pairIndex": 1, "startMs": 0, "endMs": 3800 },
        { "pairIndex": 2, "startMs": 3800, "endMs": 7500 }
      ],
      "video": [
        {
          "mediaId": "clip_001",
          "startMs": 0,
          "endMs": 3800,
          "sourceInMs": 0,
          "sourceOutMs": 3800,
          "muted": true
        },
        {
          "mediaId": "clip_001",
          "startMs": 3800,
          "endMs": 7500,
          "sourceInMs": 3800,
          "sourceOutMs": 7500,
          "muted": true
        }
      ]
    }
  },

  "exportSettings": {
    "format": "mp4",
    "videoCodec": "h264",
    "audioCodec": "aac",
    "videoBitrate": "8M",
    "audioBitrate": "192k"
  }
}
```

### Why JSON (Not a Database File)

- Human-readable and debuggable (open in any text editor)
- No binary format lock-in
- Trivially portable across operating systems
- Small file size (typically < 50KB even for large projects)
- Works with version control (git diff-able)
- No database engine needed on the receiving computer
- OneDrive syncs it like any other file

---

## 6. Application Architecture

### View Structure

The app has two main views with tab navigation:

```
+----------------------------------------------------------+
|  [Generator]  [Editor]                    [Project: WO-12345]  |
+----------------------------------------------------------+
|                                                          |
|  (Active view content here)                              |
|                                                          |
+----------------------------------------------------------+
```

#### View 1: Generator (Enhanced Current UI)
- Script input textareas (EN/ES)
- Font and shadow settings
- "Split into Paragraph Blocks" button
- Paragraph block grid with Generate buttons
- Status indicators for each block
- All generated videos auto-save to `generated/en/` and `generated/es/` in the work order folder

#### View 2: Editor (New)
- Top section: Preview canvas (1920x1080 scaled to fit)
- Middle section: Playback controls (play, pause, seek, frame step)
- Bottom section: 3-track timeline with zoom and scroll
- Side panel: Properties of selected segment, layer visibility toggles

### Module Structure (After Vite Migration)

```
src/
|-- main.js                    <-- Entry point, view routing
|-- generator/
|   |-- generator-view.js      <-- Generator page UI
|   |-- tts-engine.js          <-- TTS model loading and audio generation
|   |-- subtitle-timing.js     <-- Subtitle sync algorithm (extracted from current code)
|   +-- video-renderer.js      <-- FFmpeg.wasm subtitle video generation
|
|-- editor/
|   |-- editor-view.js         <-- Editor page UI and layout
|   |-- timeline-canvas.js     <-- Canvas-based 3-track timeline component
|   |-- timeline-state.js      <-- Timeline data model and operations
|   |-- playback-engine.js     <-- Preview playback controller
|   +-- layer-controls.js      <-- Track visibility and audio toggles
|
|-- media/
|   |-- video-importer.js      <-- File import, validation, optimization
|   |-- video-optimizer.js     <-- Mediabunny transcode to optimized H.264
|   +-- thumbnail-generator.js <-- Extract filmstrip thumbnails
|
|-- export/
|   |-- export-pipeline.js     <-- Final MP4 export compositing
|   +-- export-settings.js     <-- Export configuration UI
|
|-- project/
|   |-- project-manager.js     <-- Create, open, save project folders
|   |-- project-file.js        <-- Read/write project.json
|   +-- file-system.js         <-- File System Access API wrapper
|
|-- shared/
|   |-- supabase-client.js     <-- Supabase singleton for app metadata
|   |-- ui-utils.js            <-- Shared UI helpers
|   +-- constants.js           <-- App-wide constants
|
+-- workers/
    |-- ffmpeg-worker.js       <-- FFmpeg.wasm web worker (existing)
    +-- optimize-worker.js     <-- Video optimization web worker (new)
```

---

## 7. Feature Specifications

### 7.1 Project Management

**Create Project:**
1. User clicks "Create Project" on the landing screen
2. `showDirectoryPicker()` opens -- user navigates to their desired location and creates/selects a folder (e.g., `WO-12345`)
3. App creates the subfolder structure (`generated/en/`, `generated/es/`, `media/`, `thumbnails/`)
4. App creates `project.json` with default settings
5. App saves the project reference in Supabase (recent projects list)
6. Generator view opens

**Open Existing Project:**
1. User clicks "Open Project" on the landing screen
2. `showDirectoryPicker()` opens -- user selects an existing work order folder
3. App reads `project.json` and restores full state
4. If generated videos exist, they appear in the timeline
5. If imported media exists, it appears on the video track

**Auto-Save:**
- `project.json` is saved automatically after every meaningful change (debounced, 2-second delay)
- Generated video files are written to the folder immediately after generation
- No "Save" button needed -- always up to date

### 7.2 TTS Video Generation (Enhanced Current Feature)

Same as current functionality with these additions:
- Generated `.mov` files are written directly to the work order folder (`generated/en/` or `generated/es/`)
- Duration metadata is extracted and stored in `project.json`
- After generation, the pair automatically appears on the timeline
- Regeneration overwrites the existing file and updates the timeline

### 7.3 Video Import

**Import Flow:**
1. User clicks "Import Video" in the Editor view (or drags files onto the timeline)
2. File picker opens (accepts `.mp4`, `.mov`, `.webm`, `.mkv`)
3. For each selected file:
   a. File is copied to `media/` folder in the work order directory
   b. Metadata is extracted (duration, resolution, codec, frame rate)
   c. A filmstrip thumbnail is generated and saved to `thumbnails/`
   d. Background optimization begins (see section 10)
   e. Video appears on the video track in the timeline

**Multiple Video Import:**
- Users can import multiple videos one at a time (click Import again for each)
- Each imported video appears as a separate clip on the video track
- Clips can be reordered on the timeline by dragging
- Each clip can be trimmed (in/out points) independently

**Import Status Indicator:**
- "Copying..." (writing to work order folder)
- "Generating thumbnails..." (extracting filmstrip)
- "Optimizing..." (background transcoding)
- "Ready" (fully processed)

### 7.4 Layer Visibility and Audio Controls

Each track has independent controls:

| Track | Visibility Toggle | Audio Toggle | Purpose |
|-------|------------------|-------------|---------|
| EN Subtitle | Show/Hide | Mute/Unmute EN TTS audio | Toggle for English export |
| ES Subtitle | Show/Hide | Mute/Unmute ES TTS audio | Toggle for Spanish export |
| External Video | Show/Hide | Mute/Unmute original audio | Always visible in export, audio usually muted |

**Export Presets:**
- "Export English Version" button: Enables EN track + Video track, disables ES track, mutes video audio
- "Export Spanish Version" button: Enables ES track + Video track, disables EN track, mutes video audio
- "Custom Export" button: Opens settings dialog with all toggles

### 7.5 Timeline Editing Operations

| Operation | Description |
|-----------|-------------|
| Scrub/Seek | Drag playhead to any position. Preview updates in real time. |
| Zoom | Mouse wheel or +/- buttons to zoom timeline in/out |
| Scroll | Horizontal scroll to navigate long timelines |
| Trim video clip | Drag left/right edges of a video segment to adjust in/out points |
| Move video clip | Drag a video segment to reposition it on the timeline |
| Split video clip | Position playhead, press S or click Split button to cut at that point |
| Delete segment | Select a video segment, press Delete to remove it |
| Reorder pairs | Drag paragraph pairs up/down to change their sequence |

Note: EN/ES pairs are always locked together (same start time). The pair duration is always `max(en_duration, es_duration)`.

---

## 8. Database Schema (Supabase)

Supabase is used for **app-level metadata only** -- not for project data (that lives in the work order folder as `project.json`).

### Table: `app_users`
Stores per-user preferences and settings.

| Column | Type | Description |
|--------|------|-------------|
| id | uuid (PK) | Auto-generated |
| machine_id | text | Browser fingerprint or user-chosen identifier |
| display_name | text | User's name for display |
| default_font | text | Default font preference |
| default_shadow_size | integer | Default shadow size |
| created_at | timestamptz | Auto-set |
| updated_at | timestamptz | Auto-updated |

### Table: `recent_projects`
Tracks recently opened projects for quick access on the landing page.

| Column | Type | Description |
|--------|------|-------------|
| id | uuid (PK) | Auto-generated |
| user_id | uuid (FK) | References app_users |
| project_name | text | Work order number / folder name |
| folder_path | text | Last known folder path (informational only) |
| last_opened | timestamptz | When it was last opened |
| pairs_count | integer | Number of paragraph pairs |
| media_count | integer | Number of imported videos |
| created_at | timestamptz | Auto-set |

### Table: `model_cache_status`
Tracks whether TTS models have been downloaded on this machine.

| Column | Type | Description |
|--------|------|-------------|
| id | uuid (PK) | Auto-generated |
| user_id | uuid (FK) | References app_users |
| model_name | text | e.g., "kokoro-82m", "mms-tts-spa" |
| cached | boolean | Whether the model is cached locally |
| cached_at | timestamptz | When it was cached |
| size_bytes | bigint | Model file size |

Note: These tables are optional -- the app works fully without Supabase. They enhance the user experience (recent projects list, model status across sessions) but are not required for core functionality.

---

## 9. Timeline Editor Design

### Visual Layout

```
+------------------------------------------------------------------+
|  [<< Prev Frame] [Play/Pause] [Next Frame >>]  00:00:15 / 01:23  |
+------------------------------------------------------------------+
|                                                                    |
|  +--------------------------------------------------------------+  |
|  |                    PREVIEW CANVAS                             |  |
|  |                    (1920x1080 scaled)                         |  |
|  |                                                               |  |
|  |    +--------------------------------------------------+       |  |
|  |    |          External Video Frame                     |       |  |
|  |    |                                                   |       |  |
|  |    |                                                   |       |  |
|  |    |     [EN Subtitle Text Overlay]                    |       |  |
|  |    |     [ES Subtitle Text Overlay]                    |       |  |
|  |    +--------------------------------------------------+       |  |
|  +--------------------------------------------------------------+  |
|                                                                    |
+------------------------------------------------------------------+
|  TIME RULER:  |0:00  |0:05  |0:10  |0:15  |0:20  |0:25  |0:30   |
+------------------------------------------------------------------+
|  EN  | [Pair 1: "Safety is..."] [Pair 2: "Next step..."]  [...]  |
+------------------------------------------------------------------+
|  ES  | [Pair 1: "La seguri..."] [Pair 2: "El siguien..."] [...]  |
+------------------------------------------------------------------+
|  VID | [====clip_001====][===clip_001===][==clip_002==]           |
+------------------------------------------------------------------+
|  [Zoom -] ====o======================== [Zoom +]  [Import Video] |
+------------------------------------------------------------------+
```

### Track Details

**EN Track (Blue):**
- Blocks represent generated English subtitle videos
- Each block shows: pair number, first few words, duration
- Blocks are auto-positioned sequentially
- Click to select, shows properties in side panel

**ES Track (Green):**
- Same as EN track but for Spanish
- Vertically aligned with EN pairs (same start times)
- ES block may be shorter or longer than its EN counterpart
- The pair boundary is determined by the longer of the two

**Video Track (Gray/Neutral):**
- Shows imported video clips as filmstrip thumbnail strips
- Clips can be trimmed (drag edges), moved (drag body), split (S key at playhead)
- Cut markers auto-appear at pair boundaries
- Each segment shows which portion of the source video it uses

### Canvas Rendering Strategy

The timeline is rendered on an HTML5 Canvas for performance. Key rendering elements:
- Time ruler with dynamic tick marks (adapts to zoom level)
- Track background lanes with labels
- Clip blocks with rounded corners and text labels
- Filmstrip thumbnails on the video track
- Playhead (vertical red line)
- Selection highlights
- Trim handles (visible on hover)

Mouse interaction is handled via hit-testing on canvas coordinates, mapped to timeline elements.

---

## 10. Video Import and Optimization

### Why Optimize Imported Videos

Raw camera footage (especially 1080p) can use inefficient codecs or high bitrates that waste storage space. When a video is imported:

1. The original file is immediately usable (copied as-is to `media/`)
2. A background optimization process converts it to an efficient H.264 MP4
3. The optimized version replaces the original in the folder
4. Timeline playback uses the optimized version

### Optimization Pipeline (Using Mediabunny + WebCodecs)

```
Import -> Copy to media/ -> Extract metadata -> Generate thumbnails
                |
                +-> Background Worker: Transcode to H.264 MP4
                    - Resolution: Keep original (1920x1080)
                    - Codec: H.264 (hardware accelerated)
                    - Bitrate: 4-6 Mbps (configurable)
                    - Audio: AAC 128kbps (or strip if not needed)
                    - Container: MP4 with fast-start
                    - Result: ~3-5MB per minute of video
```

### File Size Estimates

For typical 1080p video at 2 minutes:

| Quality | Bitrate | File Size (2 min) | Visual Quality |
|---------|---------|-------------------|----------------|
| High | 8 Mbps | ~120 MB | Near-original |
| Medium (Recommended) | 5 Mbps | ~75 MB | Excellent for subtitles |
| Low | 2 Mbps | ~30 MB | Acceptable, some artifacting |

Recommended default: **5 Mbps**. This produces good quality at reasonable file sizes. For a project with 3 clips of 2 minutes each, the media folder would be ~225 MB.

### Thumbnail Generation

For each imported video, extract 1 frame per second and compose them into a horizontal filmstrip image (JPEG, ~100px tall). This strip is used to render the video track on the timeline canvas. Stored in `thumbnails/` folder.

---

## 11. Export Pipeline

### Export Goal

Produce two separate MP4 files:
1. **English Version:** External video + English subtitles + English TTS audio
2. **Spanish Version:** External video + Spanish subtitles + Spanish TTS audio

### Export Process

```
User clicks "Export English Version"
    |
    v
For each pair in sequence:
    1. Read the external video segment (trimmed to pair duration)
    2. Read the EN subtitle video (.mov with transparency)
    3. Composite: external video as base, EN subtitle overlaid
    4. Read the EN TTS audio
    5. Mux video + audio into the output stream
    |
    v
Write final MP4 file to user-chosen location (separate from work order folder)
```

### Technical Approach

**Option A (Recommended): FFmpeg.wasm for final compositing**

FFmpeg.wasm can overlay transparent video on top of another video using filter graphs. This is the most reliable approach for compositing transparent .mov files onto external footage:

```
ffmpeg -i external_segment.mp4 -i en_subtitle.mov
       -filter_complex "[1:v]format=rgba[sub];[0:v][sub]overlay=0:0[out]"
       -map "[out]" -map 1:a -c:v libx264 -preset fast -crf 23
       -c:a aac -b:a 192k output_en.mp4
```

**Option B: Mediabunny + Canvas compositing**

Use Mediabunny to decode both video streams frame-by-frame, composite them on a Canvas, then re-encode with Mediabunny. More control but more complex.

**Recommendation:** Use FFmpeg.wasm for the final export since it already handles the overlay compositing well and is proven in this codebase. Use Mediabunny for import/optimization only.

### Export Settings (User Configurable)

| Setting | Default | Options |
|---------|---------|---------|
| Resolution | 1920x1080 | Match source |
| Video Codec | H.264 | H.264 |
| Video Bitrate | 8 Mbps | 4/6/8/12 Mbps |
| Audio Codec | AAC | AAC |
| Audio Bitrate | 192 kbps | 128/192/256 kbps |
| Format | MP4 | MP4 |

### Export Output Location

The exported MP4 is saved to a **separate location** chosen by the user (via `showSaveFilePicker()`), NOT inside the work order folder. This keeps the work order folder lean for OneDrive sharing.

---

## 12. Sharing and Portability

### How Sharing Works

1. Person A creates project in folder `WO-12345/`
2. Person A uploads `WO-12345/` folder to OneDrive (or any shared drive)
3. Person B downloads `WO-12345/` folder to their computer
4. Person B has the same app installed on their machine
5. Person B opens the app, clicks "Open Project", selects the downloaded `WO-12345/` folder
6. App reads `project.json` and restores full state -- timeline, generated videos, imported media, all settings
7. Person B can edit, regenerate, re-export

### What Transfers

| Content | Included in Folder | Typical Size |
|---------|-------------------|-------------|
| `project.json` | Yes | < 50 KB |
| Generated EN/ES videos | Yes | ~2-5 MB per pair |
| Imported media (optimized) | Yes | ~75 MB per 2-min clip |
| Thumbnails | Yes | ~500 KB per clip |
| Exported final videos | **No** | Saved separately |
| App files | **No** | Each person has own copy |
| TTS models | **No** | Cached in each person's browser |

### Estimated Folder Size

For a typical project (10 pairs, 3 imported clips of 2 min each):
- Generated videos: 10 pairs x 2 languages x 3 MB = ~60 MB
- Imported media: 3 clips x 75 MB = ~225 MB
- Thumbnails: 3 x 500 KB = ~1.5 MB
- project.json: < 50 KB
- **Total: ~287 MB**

This is well within OneDrive sync limits.

### Portability Guarantee

The project folder is fully self-contained:
- All file paths in `project.json` are **relative** (e.g., `generated/en/en_01.mov`, not `C:\Users\...`)
- No external dependencies -- every file needed is in the folder
- Works on any computer with the app installed, regardless of OS or folder location
- No database needed to open a project -- `project.json` has everything

---

## 13. Build Order

Implementation phases in dependency order:

### Phase 1: Foundation
1. Set up Vite project with npm
2. Install all dependencies as npm packages (Tailwind, JSZip, kokoro-js, transformers, mediabunny)
3. Migrate existing `index.html` into Vite's module structure
4. Replace all CDN imports with npm imports
5. Verify existing TTS generation still works with bundled dependencies
6. Configure Vite to add COOP/COEP headers (replacing the need for `server.py` in development)

### Phase 2: Project System
7. Implement File System Access API wrapper (`file-system.js`)
8. Build project create/open flow with `showDirectoryPicker()`
9. Implement `project.json` read/write with auto-save
10. Create Supabase tables for app metadata (recent projects, user prefs)
11. Build landing page with "Create Project" and "Open Project" buttons + recent projects list
12. Build tab navigation between Generator and Editor views

### Phase 3: Generator Enhancement
13. Refactor existing generation code into modules
14. Wire generated videos to save directly to work order folder
15. Update `project.json` after each generation with duration metadata
16. Add "generate all" with sequential processing and progress tracking

### Phase 4: Video Import
17. Build video import UI (button + drag-drop zone)
18. Implement file copy to `media/` folder
19. Implement metadata extraction with Mediabunny
20. Build thumbnail filmstrip generator (Web Worker)
21. Build background video optimizer (Web Worker + Mediabunny)
22. Show import progress and optimization status

### Phase 5: Timeline Core
23. Build canvas-based timeline renderer (time ruler, track lanes, playhead)
24. Render EN/ES pair blocks from `project.json` data
25. Render video track with filmstrip thumbnails
26. Implement playhead dragging and time display
27. Implement zoom and horizontal scroll
28. Implement click-to-select on timeline elements

### Phase 6: Timeline Editing
29. Implement video clip trimming (drag edges)
30. Implement video clip moving (drag body)
31. Implement video clip splitting (at playhead)
32. Implement video segment deletion
33. Implement pair reordering (drag to rearrange)
34. Auto-sync timeline state to `project.json`

### Phase 7: Preview Playback
35. Build preview canvas with composite rendering
36. Implement play/pause/seek controls
37. Render external video frame at playhead position
38. Render EN/ES subtitle overlays at playhead position
39. Implement layer visibility toggles
40. Implement frame-step controls (prev/next frame)

### Phase 8: Export
41. Build export settings dialog
42. Implement "Export English Version" pipeline
43. Implement "Export Spanish Version" pipeline
44. Implement "Custom Export" with user-selected layers
45. Add progress bar during export
46. Save exported MP4 to user-chosen location (separate from work order folder)

### Phase 9: Polish
47. Add keyboard shortcuts (Space=play/pause, S=split, Delete=remove, etc.)
48. Add undo/redo for timeline operations
49. Add model cache status indicator
50. Create `start.bat` and `start.sh` launcher scripts
51. Build production bundle with Vite
52. Test full workflow end-to-end

---

## 14. Corporate Environment Testing Checklist

Run these tests at work before development begins:

### Test 1: File System Access API
```
Open Chrome > F12 > Console > Run the test script from Section 1
Expected: "SUCCESS" for directory picker, file writing, and file deletion
```

### Test 2: Chrome Policies
```
Open Chrome > Navigate to chrome://policy
Look for: DefaultFileSystemReadGuardSetting, DefaultFileSystemWriteGuardSetting
Expected: Not present, or set to 3 (Allow), NOT 2 (Block)
```

### Test 3: SharedArrayBuffer
```
Open the current app (python server.py + localhost:8000)
Open Chrome > F12 > Console > Type: typeof SharedArrayBuffer
Expected: "function" (not "undefined")
```

### Test 4: WebCodecs
```
Open Chrome > F12 > Console > Run:
console.log('VideoDecoder:', typeof VideoDecoder);
console.log('VideoEncoder:', typeof VideoEncoder);
console.log('AudioDecoder:', typeof AudioDecoder);
console.log('AudioEncoder:', typeof AudioEncoder);
Expected: All should print "function"
```

### Test 5: Current App Still Works
```
Run the current app and generate a test video
Expected: Video generates successfully
This confirms SharedArrayBuffer, COOP/COEP, and FFmpeg.wasm all work
```

### Fallback Plans

| If This Fails | Fallback |
|---------------|----------|
| File System Access API blocked | Use `<input type="file">` for import, `<a download>` for export. Lose live folder access but still functional. |
| WebCodecs not available | Use FFmpeg.wasm for all video processing (slower but works) |
| SharedArrayBuffer blocked | This would break the current app too -- escalate to IT |
| PWA install blocked | Stay with Python server approach (Option A) |

---

## 15. Performance Considerations

### Expected Workload

| Metric | Typical | Maximum |
|--------|---------|---------|
| Paragraph pairs | 7 | 20 |
| Imported videos | 3 | 10 |
| Video duration (each) | 1 min | 2 min |
| Total timeline duration | 30 sec | 3 min |
| Work order folder size | 150 MB | 500 MB |

### Memory Budget

| Operation | Est. Memory | Duration |
|-----------|------------|----------|
| App idle | ~50 MB | Persistent |
| TTS model loaded (Kokoro) | ~300 MB | Persistent while generating |
| TTS model loaded (MMS-TTS) | ~100 MB | Persistent while generating |
| Video optimization (1 clip) | ~200 MB | During optimization |
| Timeline rendering | ~30 MB | Persistent in Editor view |
| Export processing | ~400 MB | During export |
| **Peak (generation + optimization)** | **~650 MB** | Temporary |

### Strategies to Stay Within Limits

1. **Unload TTS models** after all pairs are generated (free ~400MB)
2. **Process imports one at a time** -- never optimize two videos simultaneously
3. **Use streaming pipeline** in Mediabunny -- process video frame-by-frame, never load entire file into memory
4. **Generate thumbnails at low resolution** (100px tall filmstrip)
5. **Limit preview resolution** -- render preview at 960x540 and upscale, not full 1920x1080

### If the System Struggles

For projects with many videos or very long clips:
- Import videos one at a time (the UI enforces this by default)
- Close and reopen the app between heavy operations (clears memory)
- Use lower optimization bitrate (2 Mbps instead of 5 Mbps)
- Split long videos into shorter parts before importing

---

## 16. Sources and References

### Core Technologies
- [Mediabunny -- Official Documentation](https://mediabunny.dev/)
- [Mediabunny -- GitHub Repository](https://github.com/Vanilagy/mediabunny)
- [WebCodecs API -- MDN Web Docs](https://developer.mozilla.org/en-US/docs/Web/API/WebCodecs_API)
- [File System Access API -- Chrome for Developers](https://developer.chrome.com/docs/capabilities/web-apis/file-system-access)
- [Persistent Permissions for File System Access API -- Chrome Blog](https://developer.chrome.com/blog/persistent-permissions-for-the-file-system-access-api)

### Chrome Enterprise Policies
- [Chrome Enterprise Policy List](https://chromeenterprise.google/policies/)
- [DefaultFileSystemWriteGuardSetting Policy](https://chromeenterprise.google/policies/?policy=DefaultFileSystemWriteGuardSetting)
- [FileSystemWriteBlockedForUrls Policy](https://chromeenterprise.google/policies/file-system-write-blocked-for-urls/)

### Video Processing in Browser
- [Video Processing with WebCodecs -- SitePoint](https://www.sitepoint.com/video-processing-in-browser-with-Web-Codecs/)
- [Remotion WebCodecs Documentation](https://www.remotion.dev/docs/webcodecs/)
- [Mediabunny: Supported Formats and Codecs](https://mediabunny.dev/guide/supported-formats-and-codecs)

### Timeline and Editor References
- [animation-timeline-control -- GitHub](https://github.com/ievgennaida/animation-timeline-control)
- [Twick React SDK for Video Editing](https://ncounterspecialist.github.io/twick/)
- [React Video Editor -- Timeline Features](https://www.reactvideoeditor.com/features/timeline)
- [IMG.LY Timeline Editor (Vanilla JS)](https://img.ly/docs/cesdk/js/create-video/timeline-editor-912252/)

### Video Optimization
- [Optimizing Video Uploads with WebCodecs -- Medium](https://medium.com/@sahilwadhwa.5454/optimizing-video-uploads-client-side-using-webcodecs-and-the-mediarecorder-api-87586aa77e52)
- [Mediabunny Blog Post -- Nidhin.dev](https://blog.nidhin.dev/mediabunny-mediatoolkit-for-modern-web)
