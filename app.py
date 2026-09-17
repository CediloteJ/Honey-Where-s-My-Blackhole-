from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import numpy as np
from astropy.coordinates import EarthLocation, SkyCoord, AltAz
from astropy.time import Time
import astropy.units as u
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

target_name = 'Sgr A*'
SGR_A = SkyCoord.from_name(target_name)
h_meters = 3.0
freq_hz = 20.1e6
c = 3.0e8

HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sgr A* Observation Planner</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background-color: #0d1117; color: #c9d1d9; font-family: sans-serif; }
        .card { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-bottom: 20px; }
        input[type="date"], input[type="time"] { background-color: #0d1117; color: #c9d1d9; border: 1px solid #30363d; padding: 8px; border-radius: 4px; color-scheme: dark; }
    </style>
</head>
<body class="p-6 max-w-4xl mx-auto space-y-6">

    <header class="text-center space-y-2 mb-8">
        <h1 class="text-3xl font-bold text-yellow-400">Sgr A* Optimal Wire Orientation & Track</h1>
        <p class="text-gray-400 text-sm">Enter your observing window to calculate optimal dipole angles.</p>
    </header>

    <div class="card flex flex-col md:flex-row items-center justify-between gap-4">
        <div class="flex items-center gap-2">
            <label>Date (UTC):</label>
            <input type="date" id="obsDate">
        </div>
        <div class="flex items-center gap-2">
            <label>Start (UTC):</label>
            <input type="time" id="startTime" value="00:00">
        </div>
        <div class="flex items-center gap-2">
            <label>End (UTC):</label>
            <input type="time" id="endTime" value="03:00">
        </div>
        <button onclick="fetchData()" class="bg-yellow-500 hover:bg-yellow-600 text-gray-900 font-bold py-2 px-6 rounded-lg transition">Calculate</button>
    </div>

    <div id="status-card" class="card font-mono text-green-400 text-sm whitespace-pre-wrap hidden"></div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-6 hidden" id="results-container">
        <div class="card text-center space-y-3">
            <h3 class="text-xl font-bold text-white mb-4">📡 Best Setup for Window</h3>
            <p class="text-lg">Wire 1: <strong id="w1" class="text-blue-400 text-2xl">--</strong>° from North</p>
            <p class="text-lg">Wire 2: <strong id="w2" class="text-blue-400 text-2xl">--</strong>° from North</p>
        </div>
        <div class="card text-center space-y-2">
            <h3 class="text-xl font-bold text-white mb-4">📈 Full Day Sky Path</h3>
            <p>Rises: <strong id="riseTime" class="text-gray-300">--</strong></p>
            <p>Peak: <strong id="peakAlt" class="text-gray-300">--</strong>° at <strong id="peakTime" class="text-green-400">--</strong></p>
            <p>Sets: <strong id="setTime" class="text-gray-300">--</strong></p>
        </div>
    </div>

    <div class="card hidden" id="plot-container">
        <div id="altitudePlot" style="width:100%; height:400px;"></div>
    </div>

    <script>
        document.getElementById('obsDate').valueAsDate = new Date();
        let userLat = 0, userLon = 0;

        window.onload = function() {
            document.getElementById('status-card').classList.remove('hidden');
            document.getElementById('status-card').innerText = "Detecting location...";
            
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(
                    (pos) => {
                        userLat = pos.coords.latitude;
                        userLon = pos.coords.longitude;
                        document.getElementById('status-card').innerText = `Location auto-detected: ${userLat.toFixed(2)}°, ${userLon.toFixed(2)}°\\nReady.`;
                    },
                    (err) => {
                        userLat = 34.20; 
                        userLon = -79.76;
                        document.getElementById('status-card').innerText = `Geolocation blocked, using Florence, SC default: ${userLat.toFixed(2)}°, ${userLon.toFixed(2)}°\\nReady.`;
                    }
                );
            }
        };

        async function fetchData() {
            const dateVal = document.getElementById('obsDate').value;
            const startVal = document.getElementById('startTime').value;
            const endVal = document.getElementById('endTime').value;
            
            document.getElementById('status-card').innerText = "Calculating sky track and optimizing dipole gains... Please wait.";

            const response = await fetch('/api/track', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ lat: userLat, lon: userLon, date: dateVal, start: startVal, end: endVal })
            });

            const data = await response.json();

            document.getElementById('status-card').innerText = `Observer Location: ${userLat.toFixed(2)}°, ${userLon.toFixed(2)}°\\nCalculation Complete.`;
            document.getElementById('results-container').classList.remove('hidden');
            document.getElementById('plot-container').classList.remove('hidden');

            document.getElementById('w1').innerText = data.best_wire1_deg;
            document.getElementById('w2').innerText = data.best_wire2_deg;
            document.getElementById('riseTime').innerText = data.rise_time;
            document.getElementById('peakTime').innerText = data.peak_time;
            document.getElementById('peakAlt').innerText = data.peak_altitude;
            document.getElementById('setTime').innerText = data.set_time;

            const traceCurve = { x: data.times, y: data.altitudes, mode: 'lines', name: 'Sgr A*', line: { color: '#58a6ff', width: 2 } };
            const traceHorizon = { x: [data.times[0], data.times[data.times.length - 1]], y: [0, 0], mode: 'lines', name: 'Horizon', line: { color: '#f85149', dash: 'dash' } };

            const layout = {
                title: 'Altitude vs. Time (UTC)',
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                font: { color: '#c9d1d9' },
                xaxis: { title: 'Time (UTC)', tickformat: '%H:%M', gridcolor: '#30363d' },
                yaxis: { title: 'Altitude (°)', range: [-90, 90], gridcolor: '#30363d' },
                shapes: [{
                    type: 'rect',
                    xref: 'x', yref: 'paper',
                    x0: data.window_start_iso, x1: data.window_end_iso,
                    y0: 0, y1: 1,
                    fillcolor: 'rgba(255, 165, 0, 0.15)',
                    line: { width: 0 }
                }],
                margin: { l: 50, r: 20, t: 50, b: 50 }
            };

            Plotly.newPlot('altitudePlot', [traceCurve, traceHorizon], layout);
        }
    </script>
</body>
</html>
"""

@app.route('/', methods=['GET'])
def home():
    return render_template_string(HTML_PAGE)

@app.route('/api/track', methods=['POST'])
def track_blackhole():
    data = request.json
    lat = float(data.get('lat', 34.20))
    lon = float(data.get('lon', -79.76))
    date_str = data.get('date')
    start_str = data.get('start', '00:00')
    end_str = data.get('end', '03:00')

    location = EarthLocation(lat=lat * u.deg, lon=lon * u.deg, height=0 * u.m)
    
    # 24-hour track for plotting (1-minute resolution)
    times_plot_utc = Time(f"{date_str} 00:00:00", scale='utc') + np.arange(0, 24 * 60, 1) * u.minute
    altaz_plot = SGR_A.transform_to(AltAz(obstime=times_plot_utc, location=location))
    
    altitudes = altaz_plot.alt.deg
    time_iso_strings = [t.to_datetime().isoformat() for t in times_plot_utc]

    # Find Rise, Peak, Set
    above_horizon = altitudes > 0
    if np.any(above_horizon):
        visible_indices = np.where(above_horizon)[0]
        rise_time = times_plot_utc[visible_indices[0]].to_datetime().strftime('%H:%M UTC')
        set_time = times_plot_utc[visible_indices[-1]].to_datetime().strftime('%H:%M UTC')
        max_alt_idx = int(np.argmax(altitudes))
        peak_time = times_plot_utc[max_alt_idx].to_datetime().strftime('%H:%M UTC')
        peak_alt = round(altitudes[max_alt_idx], 2)
    else:
        rise_time = set_time = peak_time = "Never"
        peak_alt = "N/A"

    # Define Observing Window bounds
    obs_start = Time(f"{date_str} {start_str}:00", scale='utc')
    obs_end = Time(f"{date_str} {end_str}:00", scale='utc')
    
    # Handle rollover past midnight
    if obs_end < obs_start:
        obs_end += 24 * u.hour

    # Wire Angle Optimization based strictly on the observing window (5-minute resolution)
    window_duration_mins = int((obs_end - obs_start).to_value('minute'))
    if window_duration_mins <= 0: window_duration_mins = 60 # failsafe
    
    times_opt = obs_start + np.arange(0, window_duration_mins + 1, 5) * u.minute
    altaz_opt = SGR_A.transform_to(AltAz(obstime=times_opt, location=location))
    
    visible_mask = altaz_opt.alt.deg > 0
    sgr_az_rad = altaz_opt.az.rad[visible_mask]
    sgr_elev_rad = altaz_opt.alt.rad[visible_mask]

    best_score = -1.0
    best_w1_angle = "N/A"

    if len(sgr_elev_rad) > 0:
        h_over_lambda = h_meters / (c / freq_hz)
        ground_factor = np.abs(np.sin(2 * np.pi * h_over_lambda * np.sin(sgr_elev_rad)))

        for w1_deg in range(0, 95, 5):
            w1_rad = np.radians(w1_deg)
            w2_rad = np.radians(w1_deg + 90)
            
            dot1 = np.cos(sgr_elev_rad) * np.cos(sgr_az_rad - w1_rad)
            gain_w1 = np.sqrt(np.maximum(0, 1 - dot1**2))
            
            dot2 = np.cos(sgr_elev_rad) * np.cos(sgr_az_rad - w2_rad)
            gain_w2 = np.sqrt(np.maximum(0, 1 - dot2**2))
            
            total_gain = np.sqrt(gain_w1**2 + gain_w2**2) * ground_factor
            score = np.sum(total_gain)
            
            if score > best_score:
                best_score = score
                best_w1_angle = w1_deg

    return jsonify({
        "best_wire1_deg": best_w1_angle,
        "best_wire2_deg": best_w1_angle + 90 if isinstance(best_w1_angle, int) else "N/A",
        "rise_time": rise_time,
        "peak_time": peak_time,
        "set_time": set_time,
        "peak_altitude": peak_alt,
        "times": time_iso_strings,
        "altitudes": altitudes.tolist(),
        "window_start_iso": obs_start.to_datetime().isoformat(),
        "window_end_iso": obs_end.to_datetime().isoformat()
    })

if __name__ == '__main__':
    app.run(port=5000)
