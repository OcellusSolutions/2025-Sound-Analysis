# 2025-Sound-Analysis
python code, api, plus for analyzing the sound files from our 2025 data collection

"BeeSoundAnalysis_<ver date>" is AI-assisted python code that takes one individual sound file from our curated library of 2025 Ocellus Solutions research project, randomly selects 58 5-second segments for analysis, performs acoustic analysis and generates a number of variables (below), then outputs it to one Excel file.

The most recent version as of the date of this writing (01/19/2026) cannot process more than one sound (wav) file at a time nor does it append the existing exported Excel file ('analysis.xlsx').

WE SHOULD MODIFY THE PROGRAM TO PROCESS MULTIPLE FILES WITHIN THE SAME APIARY, AND APPEND THE EXCEL FILE

Sound Files
Sound files must be formated in the form of: Apiary Name_Colony_year_month_day.  The original file format must be changed for the .py to work properly

Variable Output
f0 - fundamental frequency
f1 - first harmonic
f2 - second harmonic
f3 - third harmonic
bp1 — band power proxy, 80–250 Hz															
bp2 — band power proxy, 250–450 Hz															
bp3 — band power proxy, 450–650 Hz															
bp4 — band power proxy, 650–1200 Hz																								
h2re — harmonic-to-residual energy proxy (higher = more tonal, less broadband noise)								
f1vf0 — relative 2nd harmonic strength													
f2vf0 — relative 3rd harmonic strength
f3vf0 - relative 4th harmonic strength													
nihv1 — broadband/high-band vs low-band ratio (higher = “hissier”)									
nihvlm — high-band vs low+mid ratio (often more stable)	
interpretation - 




KJ NEEDS TO UPDATE ....

1) Primary: HNR proxy (dB)																	
What it captures: how much of the energy sits in harmonic, tone-like structure (F0 + harmonics) versus everything else in your analysis bands.	
How to interpret:																		
Higher HNR → more tonal/organized (less broadband noise)													
Lower HNR → more broadband/noisy (disturbance, turbulence, many unstructured components)							
2) Secondary: Broadband/noise index from bandpowers													
Because bandpowers are absolute, use ratios (they’re more robust to overall loudness differences).							
Two useful ones from your existing bp1–bp4:															
A. High/Low power ratio													
	
Higher → proportionally more energy in 650–1200 Hz relative to the low hum band → “hissier / more broadband.”	
B. High/(Low+Mid) ratio													
Often more stable than bp4/bp1 alone.															
If two hives have similar F0, the hive with lower HNR and higher bp4/(bp1+bp2) is the “noisier” hive in the sense you mean.	
	
Methods (AI generated)													
“Momentary hive noisiness was quantified using a harmonic-to-noise proxy (HNR, dB) computed as the log ratio of energy in narrow bands around F0 and its harmonics to residual band-limited energy, supplemented by a broadband noise index computed as the ratio of high-band (650–1200 Hz) power to low/mid-band power.”	
“For auditory inspection only, each recording was duplicated at the track level, and the duplicate was subjected to band-pass filtering and dynamic range compression using an automated Audacity macro; all quantitative feature extraction was performed on the original, unprocessed audio



