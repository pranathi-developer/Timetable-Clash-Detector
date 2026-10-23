# Timetable Clash Detector

## Run
    pip install -r requirements.txt
    streamlit run app.py

## CSV format
day (Mon..Sat), start/end (HH:MM, 24h), subject, faculty, room, class_group

## What it checks
- Room double-booked
- Faculty in two places
- Class group with two sessions at once

Overlap rule: `start1 < end2 and start2 < end1`
(back-to-back sessions, e.g. 09:00-10:00 then 10:00-11:00, are NOT clashes).

## Files
- clash_logic.py : detection + free-slot suggestions (rule-based)
- app.py         : Streamlit UI
- sample_timetable.csv : demo data with planted clashes

## Features
- Clash report with plain-English explanation and suggested fix
- Day view and weekly grid view (clashes in red)
- Free-slot finder for room / faculty / class
- CSV clash report download
