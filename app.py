from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import numpy as np
from astropy.coordinates import EarthLocation, SkyCoord, AltAz
from astropy.time import Time
import astropy.units as u

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
    <title>Honey, where's my black hole?</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        body { font-family: sans-serif; background: #0b0e14; color: #e1e6ed; padding: 20px; text-align: center; }
        .card { background: #161b22; padding: 20px; border-radius: 8px; margin: 15px auto; max-width: 600px; border: 1px solid #30363d; }
        button { background: #238636; color: white; border: none; padding: 10px 18px; border-radius: 6px; cursor: pointer; font-size: 16px; margin-top: 10px; }
        input[type="date"], input[type="time"] { padding: 8px; border-radius: 4px; border: 1px solid #30363d; background: #0d1117; color: white; margin: 0 5px; }
        .blue-text { color: #58a6ff; font-weight: bold; }
        .green-text { color: #3fb950; font-weight: bold; }
        h3 { margin-top: 0; margin-bottom: 15px; font-size: 1.17em; }
        .time-inputs { display: flex; justify-content: center; align-items: center; gap: 15px; margin: 15px 0; }
    </style>
</head>
<body>
    <h1>🕳️ Honey, where's my black hole?</h1>
    <p>Dipole Array & Horizon Tracking for Sagittarius A*</p>

    <!-- Initial Date Setup -->
    <div class="card">
        <label for="obsDate">Date: </label>
        <input type="date" id="obsDate">
        <button onclick="fetchData()">Find Sgr A*</button>
        <p id="status" style="color: #8b949e; margin-top: 10px;"></p>
    </div>

    <!-- Sky Path Stats -->
    <div class="card">
        <h3>📈 Sky Path</h3>
        <p>Rises: <span id="riseTime" class="blue-text">--:--</span> UTC</p>
        <p style="margin: 15px 0;">Peak Time: <span id="peakTime" class="green-text">--:--</span> UTC (<span id="peakAlt">--</span>°)</p>
        <p>Sets: <span id="setTime" class="blue-text">--:--</span> UTC</p>
    </div>

    <!-- Plotly Graph -->
    <div class="card">
        <div id="altitudePlot" style="width:100%; height:300px;"></div>
    </div>

    <!-- Step 2: Window Selection -->
    <div class="card">
        <h3>Step 2: When will you actually be there?</h3>
        <div class="time-inputs">
            <div>
                <label for="startTime">Start (UTC): </label>
                <input type="time" id="startTime" value="00:00">
            </div>
            <div>
                <label for="endTime">End (UTC): </label>
                <input type="time" id="endTime" value="03:00">
            </div>
        </div>
        <p style="color: #8b949e; font-size: 0.9em; margin-bottom: 15px;">If your end time is earlier than your start time, it's assumed to roll into the next day.</p>
        <button onclick="fetchData()">Update Window</button>
    </div>

    <!-- Optimal Dipole Setup Results -->
    <div class="card">
        <h3>📡 Optimal Dipole Setup</h3>
        <p>Wire 1: <span id="w1" class="blue-text">--</span>° from North</p>
        <p>Wire 2: <span id="w2" class="blue-text">--</span>° from North</p>
    </div>

    <script>
        document.getElementById('obsDate').valueAsDate = new Date();
        let userLat = 0, userLon = 0;

        window.onload = function() {
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(
                    (pos) => {
                        userLat = pos.coords.latitude;
                        userLon = pos.coords.longitude;
                        document.getElementById('status').innerText = `Location auto-detected: ${userLat.toFixed(2)}°, ${userLon.toFixed(2)}°`;
                    },
                    (err) => {
                        // Fallback coordinates for Florence, SC
                        userLat = 34.20; 
                        userLon = -79.76;
                        document.getElementById('status').innerText = `Geolocation blocked, using default: ${userLat.toFixed(2)}°, ${userLon.toFixed(2)}°`;
                    }
                );
            }
        };

        async function fetchData() {
            const dateVal = document.getElementById('obsDate').value;
            const startVal = document.getElementById('startTime').value;
            const endVal = document.getElementById('endTime').value;
            
            document.getElementById('status').innerText = "Calculating sky track & optimizing wires...";

            const response = await fetch('/api/track', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ lat: userLat, lon: userLon, date: dateVal, start: startVal, end: endVal })
            });

            const data = await response.json();

            // Populate UI
            document.getElementById('w1').innerText = data.best_wire1_deg;
            document.getElementById('w2').innerText = data.best_wire2_deg;
            document.getElementById('riseTime').innerText = data.rise_time;
            document.getElementById('peakTime').innerText = data.peak_time;
            document.getElementById('peakAlt').innerText = data.peak_altitude;
            document.getElementById('setTime').innerText = data.set_time;
            document.getElementById('status').innerText = "Updated!";

            // Plotly Configuration
            const traceCurve = { x: data.times, y: data.altitudes, mode: 'lines', name: 'Sgr A*', line: { color: '#58a6ff' } };
            const traceHorizon = { x: [data.times[0], data.times[data.times.length - 1]], y: [0, 0], mode: 'lines', name: 'Horizon', line: { color: '#f85149', dash: 'dash' } };

            const layout = {
                title: 'Altitude vs. Time (UTC)',
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                font: { color: '#e1e6ed' },
                xaxis: { 
                    tickformat: '%H:%M', 
                    gridcolor: '#30363d',
                    showline: true,
                    linecolor: '#30363d'
                },
                yaxis: { 
                    title: 'Altitude (°)', 
                    range: [-90, 90], 
                    gridcolor: '#30363d',
                    showline: true,
                    linecolor: '#30363d'
                },
                shapes: [{
                    type: 'rect',
                    xref: 'x', yref: 'paper',
                    x0: data.window_start_iso, x1: data.window_end_iso,
                    y0: 0, y1: 1,
                    fillcolor: 'rgba(139, 90, 43, 0.4)', // Matches the shaded brown box in the screenshot
                    line: { width: 0 }
                }],
                margin: { l: 50, r: 20, t: 50, b: 40 }
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
    
    # 24-hour track for plotting the graph
    times_plot_utc = Time(f"{date_str} 00:00:00", scale='utc') + np.arange(0, 24 * 60, 1) * u.minute
    altaz_plot = SGR_A.transform_to(AltAz(obstime=times_plot_utc, location=location))
    
    altitudes = altaz_plot.alt.deg
    time_iso_strings = [t.to_datetime().isoformat() for t in times_plot_utc]

    # Calculate Rise, Peak, Set
    above_horizon = altitudes > 0
    if np.any(above_horizon):
        visible_indices = np.where(above_horizon)[0]
        rise_time = times_plot_utc[visible_indices[0]].to_datetime().strftime('%H:%M')
        set_time = times_plot_utc[visible_indices[-1]].to_datetime().strftime('%H:%M')
        max_alt_idx = int(np.argmax(altitudes))
        peak_time = times_plot_utc[max_alt_idx].to_datetime().strftime('%H:%M')
        peak_alt = round(altitudes[max_alt_idx], 2)
    else:
        rise_time = set_time = peak_time = "--:--"
        peak_alt = "--"

    # Define Observing Window bounds
    obs_start = Time(f"{date_str} {start_str}:00", scale='utc')
    obs_end = Time(f"{date_str} {end_str}:00", scale='utc')
    
    # Handle rollover past midnight
    if obs_end < obs_start:
        obs_end += 24 * u.hour

    # Wire Angle Optimization based strictly on the user's observing window
    window_duration_mins = int((obs_end - obs_start).to_value('minute'))
    if window_duration_mins <= 0: 
        window_duration_mins = 60
    
    times_opt = obs_start + np.arange(0, window_duration_mins + 1, 5) * u.minute
    altaz_opt = SGR_A.transform_to(AltAz(obstime=times_opt, location=location))
    
    visible_mask = altaz_opt.alt.deg > 0
    sgr_az_rad = altaz_opt.az.rad[visible_mask]
    sgr_elev_rad = altaz_opt.alt.rad[visible_mask]

    best_score = -1.0
    best_w1_angle = "--"

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
        "best_wire2_deg": best_w1_angle + 90 if isinstance(best_w1_angle, int) else "--",
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
