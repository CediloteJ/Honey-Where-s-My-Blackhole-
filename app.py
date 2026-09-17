from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import numpy as np
from astropy.coordinates import EarthLocation, SkyCoord, AltAz
from astropy.time import Time, TimeDelta
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
        button { background: #238636; color: white; border: none; padding: 10px 18px; border-radius: 6px; cursor: pointer; font-size: 16px; }
        button.secondary { background: #1f6feb; }
        input[type="date"], input[type="time"], input[type="number"] { padding: 8px; border-radius: 4px; border: 1px solid #30363d; background: #0d1117; color: white; }
        .hidden { display: none; }
        .warn { color: #f0883e; }
        label { color: #8b949e; margin-right: 4px; }
    </style>
</head>
<body>
    <h1>🕳️ Honey, where's my black hole?</h1>
    <p>Dipole Array & Horizon Tracking for Sagittarius A*</p>

    <!-- STEP 1: date + location -->
    <div class="card">
        <h3>Step 1: Find the path</h3>
        <label for="obsDate">Date:</label>
        <input type="date" id="obsDate">
        <br><br>
        <label for="latInput">Lat:</label>
        <input type="number" step="0.01" id="latInput" value="0">
        <label for="lonInput">Lon:</label>
        <input type="number" step="0.01" id="lonInput" value="0">
        <br><br>
        <button onclick="findPath()">Find Sgr A*</button>
        <p id="status" style="color: #8b949e; margin-top: 10px;"></p>
    </div>

    <div class="card">
        <h3>📈 Sky Path</h3>
        <p>Rises: <strong id="riseTime" style="color: #58a6ff;">--</strong> UTC</p>
        <p>Peak Time: <strong id="peakTime" style="color: #3fb950;">--</strong> UTC (<strong id="peakAlt">--</strong>°)</p>
        <p>Sets: <strong id="setTime" style="color: #58a6ff;">--</strong> UTC</p>
    </div>

    <div class="card">
        <div id="altitudePlot" style="width:100%; height:320px;"></div>
    </div>

    <!-- STEP 2: observing hours, hidden until step 1 runs -->
    <div class="card hidden" id="windowCard">
        <h3>Step 2: When will you actually be there?</h3>
        <label for="startTime">Start (UTC):</label>
        <input type="time" id="startTime" value="00:00">
        <label for="endTime">End (UTC):</label>
        <input type="time" id="endTime" value="03:00">
        <p style="color:#8b949e; font-size: 13px;">If your end time is earlier than your start time, it's assumed to roll into the next day.</p>
        <button class="secondary" onclick="optimizeWindow()">Calculate Best Wire Orientation</button>
        <p id="optStatus" style="margin-top: 10px;"></p>
    </div>

    <div class="card hidden" id="resultCard">
        <h3>📡 Optimal Dipole Setup For Your Window</h3>
        <p>Wire 1: <strong id="w1" style="color: #58a6ff;">--</strong>° from North</p>
        <p>Wire 2: <strong id="w2" style="color: #58a6ff;">--</strong>° from North</p>
        <p>Altitude Range In Window: <strong id="altRange">--</strong></p>
    </div>

    <script>
        document.getElementById('obsDate').valueAsDate = new Date();

        window.onload = function() {
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition((pos) => {
                    document.getElementById('latInput').value = pos.coords.latitude.toFixed(2);
                    document.getElementById('lonInput').value = pos.coords.longitude.toFixed(2);
                    document.getElementById('status').innerText = `Location auto-detected: ${pos.coords.latitude.toFixed(2)}°, ${pos.coords.longitude.toFixed(2)}°`;
                });
            }
        };

        let lastTrack = null; // cache of the full-day track so step 2 doesn't refetch it

        async function findPath() {
            const dateVal = document.getElementById('obsDate').value;
            const lat = parseFloat(document.getElementById('latInput').value);
            const lon = parseFloat(document.getElementById('lonInput').value);

            document.getElementById('status').innerText = "Calculating sky track...";
            document.getElementById('windowCard').classList.add('hidden');
            document.getElementById('resultCard').classList.add('hidden');

            const response = await fetch('/api/track', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ lat, lon, date: dateVal })
            });
            const data = await response.json();

            if (data.error) {
                document.getElementById('status').innerText = data.error;
                return;
            }

            lastTrack = { lat, lon, date: dateVal };

            if (!data.above_horizon) {
                document.getElementById('status').innerText = "Sgr A* does not rise above the horizon on this date/location.";
                document.getElementById('riseTime').innerText = '--';
                document.getElementById('peakTime').innerText = '--';
                document.getElementById('peakAlt').innerText = '--';
                document.getElementById('setTime').innerText = '--';
            } else {
                document.getElementById('status').innerText = "Path found. Enter your observing hours below.";
                document.getElementById('riseTime').innerText = data.rise_time;
                document.getElementById('peakTime').innerText = data.peak_time;
                document.getElementById('peakAlt').innerText = data.peak_altitude;
                document.getElementById('setTime').innerText = data.set_time;
                document.getElementById('windowCard').classList.remove('hidden');
            }

            drawPlot(data.times, data.altitudes, null, null);
        }

        async function optimizeWindow() {
            if (!lastTrack) {
                document.getElementById('optStatus').innerText = "Click 'Find Sgr A*' first.";
                return;
            }
            const startTime = document.getElementById('startTime').value; // HH:MM
            const endTime = document.getElementById('endTime').value;     // HH:MM

            document.getElementById('optStatus').innerText = "Optimizing...";
            document.getElementById('resultCard').classList.add('hidden');

            const response = await fetch('/api/optimize', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    lat: lastTrack.lat,
                    lon: lastTrack.lon,
                    date: lastTrack.date,
                    start_time: startTime,
                    end_time: endTime
                })
            });
            const data = await response.json();

            if (data.error) {
                document.getElementById('optStatus').innerText = data.error;
                return;
            }

            if (!data.visible_in_window) {
                let msg = "Sgr A* is not above the horizon during that window.";
                if (data.actual_rise && data.actual_set) {
                    msg += ` It's actually visible from ${data.actual_rise} to ${data.actual_set} UTC.`;
                }
                document.getElementById('optStatus').innerText = msg;
                document.getElementById('resultCard').classList.add('hidden');
                return;
            }

            document.getElementById('optStatus').innerText = "Done!";
            document.getElementById('w1').innerText = data.best_wire1_deg;
            document.getElementById('w2').innerText = data.best_wire2_deg;
            document.getElementById('altRange').innerText = `${data.min_alt}° to ${data.max_alt}°`;
            document.getElementById('resultCard').classList.remove('hidden');

            drawPlot(data.times, data.altitudes, data.window_start_time, data.window_end_time);
        }

        function drawPlot(times, altitudes, windowStart, windowEnd) {
            const traceCurve = { x: times, y: altitudes, mode: 'lines', name: 'Sgr A*', line: { color: '#58a6ff' } };
            const traceHorizon = { x: [times[0], times[times.length - 1]], y: [0, 0], mode: 'lines', name: 'Horizon', line: { color: '#f85149', dash: 'dash' } };

            const layout = {
                title: 'Altitude vs. Time (UTC)',
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                font: { color: '#e1e6ed' },
                yaxis: { title: 'Altitude (°)', range: [-90, 90] },
                shapes: []
            };

            if (windowStart && windowEnd) {
                layout.shapes.push({
                    type: 'rect',
                    xref: 'x', yref: 'paper',
                    x0: windowStart, x1: windowEnd,
                    y0: 0, y1: 1,
                    fillcolor: '#f0883e',
                    opacity: 0.25,
                    line: { width: 0 }
                });
            }

            Plotly.newPlot('altitudePlot', [traceCurve, traceHorizon], layout);
        }
    </script>
</body>
</html>
"""


def compute_full_track(lat, lon, date_str):
    """Full 24h altaz track starting at 00:00 UTC on date_str, at 5-min resolution."""
    location = EarthLocation(lat=lat * u.deg, lon=lon * u.deg, height=0 * u.m)
    times_utc = Time(f"{date_str} 00:00:00", scale='utc') + np.arange(0, 24 * 60, 5) * u.minute
    altaz = SGR_A.transform_to(AltAz(obstime=times_utc, location=location))
    return location, times_utc, altaz


def parse_window(date_str, start_hhmm, end_hhmm):
    """Build observe_start/observe_end Time objects from a date + HH:MM start/end.
    If end <= start, the window is assumed to roll into the next day."""
    observe_start = Time(f"{date_str} {start_hhmm}:00", scale='utc')
    observe_end = Time(f"{date_str} {end_hhmm}:00", scale='utc')
    if observe_end <= observe_start:
        observe_end = observe_end + TimeDelta(1 * u.day)
    return observe_start, observe_end


def best_wire_angles(az_rad, elev_rad):
    h_over_lambda = h_meters / (c / freq_hz)
    ground_factor = np.abs(np.sin(2 * np.pi * h_over_lambda * np.sin(elev_rad)))

    best_score = -1.0
    best_w1_angle = 0

    for w1_deg in range(0, 95, 5):
        w1_rad = np.radians(w1_deg)
        w2_rad = np.radians(w1_deg + 90)

        dot1 = np.cos(elev_rad) * np.cos(az_rad - w1_rad)
        gain_w1 = np.sqrt(np.maximum(0, 1 - dot1 ** 2))

        dot2 = np.cos(elev_rad) * np.cos(az_rad - w2_rad)
        gain_w2 = np.sqrt(np.maximum(0, 1 - dot2 ** 2))

        total_gain = np.sqrt(gain_w1 ** 2 + gain_w2 ** 2) * ground_factor
        score = np.sum(total_gain)

        if score > best_score:
            best_score = score
            best_w1_angle = w1_deg

    return best_w1_angle, best_w1_angle + 90


@app.route('/', methods=['GET'])
def home():
    return render_template_string(HTML_PAGE)


@app.route('/api/track', methods=['POST'])
def track_blackhole():
    """Step 1: just report the sky path -- rise/peak/set -- no wire optimization yet."""
    data = request.json
    try:
        lat = float(data.get('lat', 0))
        lon = float(data.get('lon', 0))
        date_str = data.get('date')
        if not date_str:
            return jsonify({"error": "Missing date."}), 400
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid lat/lon/date."}), 400

    location, times_utc, altaz = compute_full_track(lat, lon, date_str)

    altitudes = altaz.alt.deg
    azimuths = altaz.az.deg
    time_labels = [t.to_datetime().strftime('%Y-%m-%dT%H:%M:%S') for t in times_utc]

    above_horizon_indices = np.where(altitudes > 0)[0]

    response = {
        "times": time_labels,
        "altitudes": altitudes.tolist(),
        "azimuths": azimuths.tolist(),
        "above_horizon": bool(len(above_horizon_indices) > 0),
    }

    if len(above_horizon_indices) > 0:
        max_alt_idx = int(np.argmax(altitudes))
        response["rise_time"] = time_labels[above_horizon_indices[0]].split('T')[1][:5]
        response["set_time"] = time_labels[above_horizon_indices[-1]].split('T')[1][:5]
        response["peak_time"] = time_labels[max_alt_idx].split('T')[1][:5]
        response["peak_altitude"] = round(float(altitudes[max_alt_idx]), 2)

    return jsonify(response)


@app.route('/api/optimize', methods=['POST'])
def optimize_window():
    """Step 2: restrict the optimization to the caller's actual observing hours."""
    data = request.json
    try:
        lat = float(data.get('lat', 0))
        lon = float(data.get('lon', 0))
        date_str = data.get('date')
        start_hhmm = data.get('start_time')
        end_hhmm = data.get('end_time')
        if not (date_str and start_hhmm and end_hhmm):
            return jsonify({"error": "Missing date/start_time/end_time."}), 400
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid input."}), 400

    location, times_utc, altaz = compute_full_track(lat, lon, date_str)
    observe_start, observe_end = parse_window(date_str, start_hhmm, end_hhmm)

    above_horizon = altaz.alt.deg > 0
    window_mask = (times_utc >= observe_start) & (times_utc <= observe_end)
    visible_mask = above_horizon & window_mask

    altitudes = altaz.alt.deg
    time_labels = [t.to_datetime().strftime('%Y-%m-%dT%H:%M:%S') for t in times_utc]

    if not np.any(visible_mask):
        result = {"visible_in_window": False}
        if np.any(above_horizon):
            above_idx = np.where(above_horizon)[0]
            result["actual_rise"] = time_labels[above_idx[0]].split('T')[1][:5]
            result["actual_set"] = time_labels[above_idx[-1]].split('T')[1][:5]
        return jsonify(result)

    sgr_az_rad = altaz.az.rad[visible_mask]
    sgr_elev_rad = altaz.alt.rad[visible_mask]
    best_w1_angle, best_w2_angle = best_wire_angles(sgr_az_rad, sgr_elev_rad)

    return jsonify({
        "visible_in_window": True,
        "best_wire1_deg": best_w1_angle,
        "best_wire2_deg": best_w2_angle,
        "min_alt": round(float(np.min(altitudes[visible_mask])), 1),
        "max_alt": round(float(np.max(altitudes[visible_mask])), 1),
        "times": time_labels,
        "altitudes": altitudes.tolist(),
        "window_start_time": observe_start.to_datetime().strftime('%Y-%m-%dT%H:%M:%S'),
        "window_end_time": observe_end.to_datetime().strftime('%Y-%m-%dT%H:%M:%S'),
    })


if __name__ == '__main__':
    app.run(port=5000)
