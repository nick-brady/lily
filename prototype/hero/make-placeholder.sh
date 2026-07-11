#!/usr/bin/env bash
# Generates placeholder.mp4 — a ~40.5s stand-in for the Seedance hero footage.
# Segments match the storyboard color script (Lily-Hero-Video-Plan.md §4): twelve
# scenes plus two phone-only interstitials (represented here as dark dips, since
# the real edit is a slow crossfade: A = bump photos flood in, B = contraction
# flood). Soft pulses mark the tap moments (2.7s Sarah's post, 7.5s timer start,
# 21.5s game time) and the birth light-bloom hits at 30.0s. Scene captions and
# timecode are NOT burned in — the prototype page renders them in the HTML layer,
# driven by the cue table.
set -euo pipefail
cd "$(dirname "$0")"

S=960x540
R=24

seg() { echo "gradients=size=$S:rate=$R:duration=$1:speed=0.015:c0=$2:c1=$3"; }

F1=$(seg 3.5 0xC98A3B 0x6E4520)   # 1 · bedroom, golden hour (20 weeks)
IA=$(seg 2   0x8A5E28 0x3E2A10)   # — · interstitial A: bump photos flood
F2=$(seg 4   0xD9A44E 0x9A6430)   # 2 · living room, bright + energetic
F3=$(seg 2.5 0x6E3E1E 0xA8703B)   # 3 · Janet's first look, Phoenix amber
IB=$(seg 2   0x2E1E14 0x1A100A)   # — · interstitial B: contraction flood
F4=$(seg 3   0x7A4A30 0x4E2E1E)   # 4 · the decision (bag/look/keys), home dusk
F5=$(seg 2   0x3E4E60 0x60758A)   # 5 · arrival (Sarah walking in), warm→cool
F6=$(seg 1   0x8A7040 0xB89A60)   # 6 · Lisa can't sit still, bright office
F7=$(seg 4   0x141F38 0x2C3B5E)   # 7 · game time, night blue
F8=$(seg 4   0x46565F 0x74848E)   # 8 · Emma, Seattle gray drizzle
F9=$(seg 1.5 0x2B3A47 0x4E6273)   # 9 · montage flicker (Lisa · Janet), slate
F10=$(seg 5  0xC98A9E 0xE8C2CE)   # 10 · she's here, blush
F11=$(seg 4  0x8A5A70 0x4E6273)   # 11 · split-screen finale, mixed warm/cool
F12=$(seg 2  0x241028 0x120818)   # 12 · keepsake, deep plum

ffmpeg -y -f lavfi -i "$F1" -f lavfi -i "$IA" -f lavfi -i "$F2" \
       -f lavfi -i "$F3" -f lavfi -i "$IB" -f lavfi -i "$F4" \
       -f lavfi -i "$F5" -f lavfi -i "$F6" -f lavfi -i "$F7" \
       -f lavfi -i "$F8" -f lavfi -i "$F9" -f lavfi -i "$F10" \
       -f lavfi -i "$F11" -f lavfi -i "$F12" \
  -filter_complex "[0][1][2][3][4][5][6][7][8][9][10][11][12][13]concat=n=14:v=1:a=0,\
drawbox=c=white@0.22:t=fill:enable='between(t,2.70,2.85)',\
drawbox=c=white@0.15:t=fill:enable='between(t,7.50,7.62)',\
drawbox=c=white@0.15:t=fill:enable='between(t,21.50,21.62)',\
drawbox=c=white@0.30:t=fill:enable='between(t,30.00,30.60)',\
format=yuv420p" \
  -c:v libx264 -crf 30 -preset medium -movflags +faststart placeholder.mp4

ls -lh placeholder.mp4